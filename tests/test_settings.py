from typing import Any

from django.conf import settings
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.settings import api_settings
from rest_framework.views import APIView


def test_modele_utilisateur_personnalise_est_actif() -> None:
    """Le projet utilise bien le modèle utilisateur de l'app `accounts`."""
    assert settings.AUTH_USER_MODEL == "accounts.User"


def test_drf_defaults_are_loaded_before_view_classes() -> None:
    """DRF settings and view defaults must not cache the early import fallback."""
    # DRF résout ces chemins en classes ; les stubs les décrivent en chaînes.
    permissions: Any = api_settings.DEFAULT_PERMISSION_CLASSES
    authentication: Any = api_settings.DEFAULT_AUTHENTICATION_CLASSES
    assert permissions == [IsAuthenticated]
    assert authentication == [SessionAuthentication]
    assert APIView.permission_classes == [IsAuthenticated]
    assert APIView.authentication_classes == [SessionAuthentication]
