from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "catalog"

    def ready(self) -> None:
        # Importing for the side effect of registering the signal receivers
        # that announce stock levels.
        from catalog import events  # noqa: F401
