"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.permissions import AllowAny

from config.views import health

# Les trois routes documentaires décrivent une API publique : elles sont donc
# consultables sans connexion. `AllowAny` est posé vue par vue, afin de ne
# pas toucher au défaut `IsAuthenticated` du projet, qui protège tout ce qui
# ne l'ouvre pas explicitement.
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    path(
        "api/schema/",
        SpectacularAPIView.as_view(permission_classes=[AllowAny]),
        name="schema",
    ),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(
            url_name="schema", permission_classes=[AllowAny]
        ),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema", permission_classes=[AllowAny]),
        name="redoc",
    ),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("mythology.urls")),
]
