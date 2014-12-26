# -*- coding: utf-8 -*-
from .cache import make_cache_key, CachedTranslation
from .models import Translation


def get_translation_lookups(instance, fields=None, languages=None):
    """
    Returns a dict to pass to Translation.objects.filter().
    """
    lookups = dict(
        identifier=instance.linguist_identifier,
        object_id=instance.pk)

    if fields is not None:
        lookups['field_name__in'] = fields

    if languages is not None:
        lookups['language__in'] = languages

    return lookups


def set_instance_cache(instance, translations):
    """
    Sets Linguist cache for the given instance.
    """
    for translation in translations:
        cache_key = make_cache_key(instance, translation)
        if cache_key not in instance._linguist.translations:
            cached_obj = CachedTranslation(**{'instance': instance, 'translation': translation})
            instance._linguist.translation[cache_key] = cached_obj
    return instance


class ManagerMixin(object):
    """
    Linguist Manager Mixin.
    """

    def with_translations(self, fields=None, languages=None):
        """
        Prefetches translations.
        """
        for instance in self.get_queryset():
            lookups = get_translation_lookups(instance, fields, languages)
            translations = Translation.objects.filter(**lookups)
            set_instance_cache(instance, translations)


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
        return Translation.objects.get_object_translations(**{'obj': self, 'language': language})

    def delete_translations(self, language=None):
        """
        Deletes related translations.
        """
        return Translation.objects.delete_object_translations(**{'obj': self, 'language': language})

    def _cache_translation(self, language, field_name, value):
        """
        Caches a translation.
        """
        is_new = bool(self.pk is None)

        cache_key = make_cache_key(**{
            'instance': self,
            'language': language,
            'field_name': field_name,
        })

        if cache_key in self._linguist.translations:
            self._linguist.translations[cache_key].field_value = value
            return

        cached_obj = CachedTranslation(**{
            'instance': self,
            'language': language,
            'field_name': field_name,
            'field_value': value,
        })

        obj = None

        if not is_new:
            try:
                obj = Translation.objects.get(**cached_obj.attrs)
            except Translation.DoesNotExist:
                pass

        if obj is not None:
            cached_obj.update_from_object(obj)

        self._linguist.translations[cache_key] = cached_obj

    def _get_translated_value(self, language, field_name):
        """
        Takes a language and a field name and returns the cached
        Translation instance if found, otherwise retrieves it from the database
        and cached it.
        """
        is_new = bool(self.pk is None)

        cache_key = make_cache_key(**{
            'instance': self,
            'language': language,
            'field_name': field_name
        })

        if cache_key in self._linguist.translations:
            return self._linguist.translations[cache_key].field_value

        cached_obj = CachedTranslation(**{
            'instance': self,
            'language': language,
            'field_name': field_name,
        })

        obj = None

        if not is_new:
            try:
                obj = Translation.objects.get(**cached_obj.attrs)
            except Translation.DoesNotExist:
                pass

        if obj is not None:
            cached_obj.update_from_object(obj)
            return obj.field_value

        return None

    def save(self, *args, **kwargs):
        """
        Overwrites model's ``save`` method to save translations after instance
        has been saved (required to retrieve the object ID for ``Translation``
        model).
        """
        super(ModelMixin, self).save(*args, **kwargs)
        Translation.objects.save_translations([self])
