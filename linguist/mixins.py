# -*- coding: utf-8 -*-
import copy

from . import utils
from .cache import CachedTranslation
from .models import Translation


def set_instance_cache(instance, translations):
    """
    Sets Linguist cache for the given instance.
    """
    instance.clear_translations_cache()
    for translation in translations:
        cache_key = utils.make_cache_key(**{'instance': instance, 'translation': translation})
        cached_obj = CachedTranslation(**{'instance': instance, 'translation': translation})
        instance._linguist.translations[cache_key] = cached_obj
    return instance


class ManagerMixin(object):
    """
    Linguist Manager Mixin.
    """

    def with_translations(self, field_names=None, languages=None, chunks_length=None):
        """
        Prefetches translations.
        """
        qs = self.get_queryset()
        object_ids = qs.values_list('id', flat=True)

        chunks_length = chunks_length if chunks_length is not None else 1

        lookup = dict(identifier=self.model._linguist.identifier)

        if field_names is not None:
            if not isinstance(field_names, (list, tuple)):
                field_names = [field_names]
            lookup['field_name__in'] = field_names

        if languages is not None:
            if not isinstance(languages, (list, tuple)):
                languages = [languages]
            lookup['language__in'] = languages

        translations = []

        for ids in utils.chunks(object_ids, chunks_length):
            filter_lookup = copy.copy(lookup)
            filter_lookup['object_id__in'] = ids
            translations += Translation.objects.filter(**filter_lookup)

        for instance in qs:
            instance_translations = [obj for obj in translations if obj.object_id == instance.pk]
            set_instance_cache(instance, instance_translations)


class ModelMixin(object):

    @property
    def linguist_identifier(self):
        """
        Returns Linguist's identifier for this model.
        """
        return self._linguist.identifier

    @property
    def language(self):
        """
        Returns Linguist's current language.
        """
        return self._linguist.language

    @language.setter
    def language(self, value):
        """
        Sets Linguist's current language.
        """
        self._linguist.language = value

    @property
    def default_language(self):
        """
        Returns model default language.
        """
        return self._linguist.default_language

    @default_language.setter
    def default_language(self, value):
        """
        Sets model default language.
        """
        self.language = value
        self._linguist.default_language = value

    @property
    def translatable_fields(self):
        """
        Returns Linguist's translation class fields (translatable fields).
        """
        return self._linguist.fields

    @property
    def available_languages(self):
        """
        Returns available languages.
        """
        return (Translation.objects
                           .filter(identifier=self.linguist_identifier, object_id=self.pk)
                           .values_list('language', flat=True)
                           .distinct()
                           .order_by('language'))

    @property
    def cached_translations_count(self):
        """
        Returns cached translations count.
        """
        return len(self._linguist.translations)

    def clear_translations_cache(self):
        """
        Clears Linguist cache.
        """
        self._linguist.translations.clear()

    def get_translations(self, language=None):
        """
        Returns available (saved) translations for this instance.
        """
        if not self.pk:
            return Translation.objects.none()
        return Translation.objects.get_translations(**{'obj': self, 'language': language})

    def delete_translations(self, language=None):
        """
        Deletes related translations.
        """
        return Translation.objects.delete_translations(**{'obj': self, 'language': language})

    def save(self, *args, **kwargs):
        """
        Overwrites model's ``save`` method to save translations after instance
        has been saved (required to retrieve the object ID for ``Translation``
        model).
        """
        super(ModelMixin, self).save(*args, **kwargs)
        Translation.objects.save_translations([self])
