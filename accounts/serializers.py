"""Serializers for the authentication endpoints.

These docstrings are public: drf-spectacular turns each class docstring into
the description of the matching OpenAPI component, rendered in Swagger UI and
ReDoc. They are therefore written in English, per ADR 0003.
"""

from typing import Any

from rest_framework import serializers
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import (
    TokenRefreshSerializer as SimpleJWTTokenRefreshSerializer,
)

from accounts.models import User


class TokenRefreshSerializer(SimpleJWTTokenRefreshSerializer):
    """Reject refreshes whose account has been deleted without raising a 500."""

    def validate(self, attrs: dict[str, Any]) -> dict[str, str]:
        """Delegate validation and handle only the missing-account exception."""
        try:
            return super().validate(attrs)
        except User.DoesNotExist as error:
            raise AuthenticationFailed(
                "No active account found for the given token.",
                code="no_active_account",
            ) from error


class CurrentUserSerializer(serializers.ModelSerializer[User]):
    """The authenticated account's own identity.

    Deliberately limited to two fields. Email address, password hash,
    permissions, group membership and administrative flags are **not**
    exposed: this endpoint answers "who am I", not "what may I do". Role-based
    authorisation will be carried by Django groups checked server-side, never
    by what a client reads here.
    """

    class Meta:
        model = User
        fields = ["id", "username"]
        read_only_fields = ["id", "username"]
