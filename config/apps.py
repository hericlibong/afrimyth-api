"""Application configuration carrying the runtime typing patch.

The patch cannot live in `settings.py` any more. Importing
`rest_framework.generics` there evaluates
`api_settings.DEFAULT_AUTHENTICATION_CLASSES`, which now resolves
`JWTAuthentication`, which imports `django.contrib.auth.models` — before the
application registry is populated. Django then raises
`AppRegistryNotReady`.

`ready()` runs after every model module has been imported, and this app is
listed **first** in `INSTALLED_APPS`, so its `ready()` runs before
`django.contrib.admin`'s autodiscover imports `mythology/admin.py`. That is
the latest moment that is still early enough: `ModelAdmin[Entity]`,
`ModelSerializer[Entity]` and `ReadOnlyModelViewSet[Entity]` are evaluated as
class bases, so they need the patch already applied.
"""

from django.apps import AppConfig


class TypingPatchConfig(AppConfig):
    """Apply `django_stubs_ext.monkeypatch()` as early as safely possible."""

    name = "config"
    label = "config_typing_patch"
    verbose_name = "Runtime typing patch"

    def ready(self) -> None:
        """Make Django and DRF generic classes subscriptable at runtime.

        These classes are generic only for the stubs. Without the patch,
        annotating a class base — `ModelAdmin[Entity]` — raises
        `TypeError: type 'ModelAdmin' is not subscriptable`, which is the
        price of running mypy in strict mode over Django code.
        """
        import django_stubs_ext
        from rest_framework.generics import GenericAPIView
        from rest_framework.serializers import BaseSerializer

        django_stubs_ext.monkeypatch(extra_classes=[BaseSerializer, GenericAPIView])
