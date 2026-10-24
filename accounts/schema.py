"""OpenAPI annotations for the authentication endpoints.

Kept apart so the long public descriptions do not crowd out the views. Every
string here is public — rendered in the schema, Swagger UI and ReDoc — and is
therefore written in English, per ADR 0003.

No real credential, token or account name appears in these examples. The
values are obviously synthetic, and the token strings are truncated
placeholders rather than valid signatures.
"""

from drf_spectacular.utils import OpenApiExample, OpenApiResponse
from rest_framework import serializers


# Simple JWT's own serializers declare only the **input** fields, so the
# generated `200` would read "No response body". These two exist purely to
# describe the success payloads; they are never used to validate or produce
# anything.
class TokenPairSerializer(serializers.Serializer[None]):
    """Successful token issuance: a short-lived access token and a refresh token."""

    access = serializers.CharField(
        read_only=True,
        help_text="Short-lived token, sent as `Authorization: Bearer <access>`.",
    )
    refresh = serializers.CharField(
        read_only=True,
        help_text="Longer-lived token, sent only to the refresh endpoint.",
    )


class AccessTokenSerializer(serializers.Serializer[None]):
    """Successful refresh: a new access token, and nothing else."""

    access = serializers.CharField(read_only=True, help_text="New access token.")


class CredentialsErrorSerializer(serializers.Serializer[None]):
    """Error body returned when credentials or a token are refused."""

    detail = serializers.CharField(help_text="Human-readable error message.")
    code = serializers.CharField(
        required=False, help_text="Machine-readable error code."
    )
    messages = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField()), required=False
    )


class FieldErrorSerializer(serializers.Serializer[None]):
    """Validation error body: one key per missing or malformed field."""

    username = serializers.ListField(child=serializers.CharField(), required=False)
    password = serializers.ListField(child=serializers.CharField(), required=False)
    refresh = serializers.ListField(child=serializers.CharField(), required=False)


# Les jetons des exemples sont des chaînes manifestement tronquées : un jeton
# d'exemple complet, même expiré, invite à le coller tel quel dans un client.
PLACEHOLDER_ACCESS = "eyJhbGciOi...<truncated access token>"
PLACEHOLDER_REFRESH = "eyJhbGciOi...<truncated refresh token>"


INVALID_CREDENTIALS_RESPONSE = OpenApiResponse(
    response=CredentialsErrorSerializer,
    description=(
        "The credentials were refused. The same response is returned whether "
        "the account does not exist, the password is wrong, or the account is "
        "inactive: the body never reveals which."
    ),
    examples=[
        OpenApiExample(
            "Refused credentials",
            response_only=True,
            value={"detail": "No active account found with the given credentials"},
        )
    ],
)

MISSING_FIELDS_RESPONSE = OpenApiResponse(
    response=FieldErrorSerializer,
    description="A required field was missing or empty.",
    examples=[
        OpenApiExample(
            "Missing password",
            response_only=True,
            value={"password": ["This field is required."]},
        )
    ],
)

INVALID_REFRESH_RESPONSE = OpenApiResponse(
    response=CredentialsErrorSerializer,
    description=(
        "The refresh token was refused: malformed, expired, wrongly signed, "
        "an access token sent in its place, or an inactive or deleted account."
    ),
    examples=[
        OpenApiExample(
            "Refused refresh token",
            response_only=True,
            value={
                "detail": "Token is invalid",
                "code": "token_not_valid",
            },
        )
    ],
)

UNAUTHENTICATED_RESPONSE = OpenApiResponse(
    response=CredentialsErrorSerializer,
    description=(
        "No usable access token was provided, or the one provided was "
        "malformed, expired, wrongly signed, or belongs to an account that "
        "has since been deactivated. A refresh token is also refused here."
    ),
    examples=[
        OpenApiExample(
            "Missing token",
            response_only=True,
            value={"detail": "Authentication credentials were not provided."},
        ),
        OpenApiExample(
            "Unusable token",
            response_only=True,
            value={
                "detail": ("Given token not valid for any token type"),
                "code": "token_not_valid",
            },
        ),
    ],
)


TOKEN_OBTAIN_DESCRIPTION = (
    "Exchanges a username and password for a token pair.\n\n"
    "This route needs no prior authentication — it is how a client obtains "
    "its first token.\n\n"
    "**The two tokens have different jobs.** `access` is the short-lived one "
    "you send on every request, in the `Authorization: Bearer …` header. "
    "`refresh` is longer-lived, is sent **only** to the refresh route, and is "
    "never accepted as an access token.\n\n"
    "Obtaining a token is authentication, not authorisation: it proves who "
    "the caller is and grants no additional access to entities at this stage."
)

TOKEN_OBTAIN_EXAMPLE = OpenApiExample(
    "Token pair (synthetic)",
    description=(
        "Invented, truncated token strings, shown to illustrate the response "
        "shape. They are not usable."
    ),
    response_only=True,
    value={"access": PLACEHOLDER_ACCESS, "refresh": PLACEHOLDER_REFRESH},
)

TOKEN_REFRESH_DESCRIPTION = (
    "Exchanges a valid refresh token for a new access token.\n\n"
    "This route needs no `Authorization` header: the refresh token in the "
    "request body **is** the credential. Send the refresh token, never an "
    "access token.\n\n"
    "**No revocation.** Rotation and token blacklisting are not enabled. "
    "Refreshing therefore does **not** invalidate the previous access token, "
    "which stays usable until it expires on its own. Deleting a token in your "
    "client does not revoke it server-side either. There is no logout "
    "endpoint, and none is implied."
)

TOKEN_REFRESH_EXAMPLE = OpenApiExample(
    "New access token (synthetic)",
    description="Invented, truncated token string. Not usable.",
    response_only=True,
    value={"access": PLACEHOLDER_ACCESS},
)
