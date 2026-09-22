from django.contrib import admin
from django.urls import include, path

from config.health import healthz, readyz

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("readyz", readyz, name="readyz"),
    path("", include("accounts.urls")),
    path("", include("catalog.urls")),
    path("admin/", admin.site.urls),
]
