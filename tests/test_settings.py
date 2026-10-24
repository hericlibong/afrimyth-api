from datetime import timedelta
from typing import Any

from django.conf import settings
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.settings import api_settings
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication


def test_modele_utilisateur_personnalise_est_actif() -> None:
    """Le projet utilise bien le modèle utilisateur de l'app `accounts`."""
    assert settings.AUTH_USER_MODEL == "accounts.User"


def test_drf_defaults_are_loaded_before_view_classes() -> None:
    """DRF settings and view defaults must not cache the early import fallback."""
    # Ce test garde une régression déjà constatée : quand le correctif de
    # typage importait DRF depuis `settings.py`, `api_settings` mémorisait un
    # dictionnaire vide et `DEFAULT_PERMISSION_CLASSES` retombait
    # silencieusement sur `AllowAny`. On vérifie donc les valeurs réellement
    # appliquées, et pas seulement le contenu du dictionnaire de réglages.
    #
    # DRF résout ces chemins en classes ; les stubs les décrivent en chaînes.
    permissions: Any = api_settings.DEFAULT_PERMISSION_CLASSES
    authentication: Any = api_settings.DEFAULT_AUTHENTICATION_CLASSES
    assert permissions == [IsAuthenticated]
    # JWT en premier : c'est le mécanisme des clients d'API. La session reste
    # disponible derrière, pour l'API navigable et l'administration.
    assert authentication == [JWTAuthentication, SessionAuthentication]
    assert APIView.permission_classes == [IsAuthenticated]
    assert APIView.authentication_classes == [JWTAuthentication, SessionAuthentication]


def test_les_reglages_drf_ne_sont_pas_le_repli_vide() -> None:
    """DRF must read the project settings rather than cache its fallback."""
    assert api_settings._user_settings != {}
    assert "DEFAULT_PERMISSION_CLASSES" in api_settings._user_settings


def test_durees_de_jetons_jwt() -> None:
    """Use short access tokens, one-day refresh tokens and no rotation."""
    assert api_settings_jwt_lifetime("ACCESS_TOKEN_LIFETIME") == timedelta(minutes=5)
    assert api_settings_jwt_lifetime("REFRESH_TOKEN_LIFETIME") == timedelta(days=1)
    assert settings.SIMPLE_JWT["ROTATE_REFRESH_TOKENS"] is False
    assert settings.SIMPLE_JWT["BLACKLIST_AFTER_ROTATION"] is False
    # Sans application de liste noire installée, aucune révocation n'est
    # possible : c'est une limite assumée de cet incrément, pas un oubli.
    assert "rest_framework_simplejwt.token_blacklist" not in settings.INSTALLED_APPS


def api_settings_jwt_lifetime(name: str) -> timedelta:
    """Return the token lifetime effectively used by Simple JWT."""
    from rest_framework_simplejwt.settings import api_settings as jwt_settings

    value: Any = getattr(jwt_settings, name)
    assert isinstance(value, timedelta)
    return value
