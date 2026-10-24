"""Authentication views.

Token issuance and refresh reuse Simple JWT. Refresh adds only a narrow
missing-account error translation; signing and credential checks remain
delegated to the library. The identity endpoint returns the current account.
"""

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.models import User
from accounts.schema import (
    INVALID_CREDENTIALS_RESPONSE,
    INVALID_REFRESH_RESPONSE,
    MISSING_FIELDS_RESPONSE,
    TOKEN_OBTAIN_DESCRIPTION,
    TOKEN_OBTAIN_EXAMPLE,
    TOKEN_REFRESH_DESCRIPTION,
    TOKEN_REFRESH_EXAMPLE,
    UNAUTHENTICATED_RESPONSE,
    AccessTokenSerializer,
    TokenPairSerializer,
)
from accounts.serializers import CurrentUserSerializer, TokenRefreshSerializer

# Les deux vues de jetons sont des sous-classes **minimales** des vues de
# Simple JWT : annotations et traitement ciblé du compte supprimé au
# renouvellement, sans réécriture de signature ou d'authentification. Le décorateur
# doit porter sur la classe, et non sur le résultat de `as_view()`, que
# drf-spectacular ne sait pas lire.
#
# Ces vues sont accessibles sans jeton, et c'est voulu : un client ne peut pas
# s'authentifier avant d'en détenir un. L'ouverture n'est pas redéclarée ici,
# car `TokenViewBase` pose déjà `permission_classes = ()`, ce qui neutralise
# le défaut fermé du projet. La redéclarer en `[AllowAny]` serait un
# changement de type d'un attribut hérité, que mypy refuse à juste titre. Deux
# tests gardent le comportement effectif plutôt que cette intention.


@extend_schema_view(
    post=extend_schema(
        operation_id="auth_token_obtain",
        tags=["authentication"],
        summary="Obtain an access and refresh token pair",
        description=TOKEN_OBTAIN_DESCRIPTION,
        examples=[TOKEN_OBTAIN_EXAMPLE],
        responses={
            200: TokenPairSerializer,
            400: MISSING_FIELDS_RESPONSE,
            401: INVALID_CREDENTIALS_RESPONSE,
        },
        auth=[],
    )
)
class TokenObtainView(TokenObtainPairView):
    """Exchange a username and password for a token pair."""


@extend_schema_view(
    post=extend_schema(
        operation_id="auth_token_refresh",
        tags=["authentication"],
        summary="Refresh an access token",
        description=TOKEN_REFRESH_DESCRIPTION,
        examples=[TOKEN_REFRESH_EXAMPLE],
        responses={
            200: AccessTokenSerializer,
            400: MISSING_FIELDS_RESPONSE,
            401: INVALID_REFRESH_RESPONSE,
        },
        auth=[],
    )
)
class TokenRefreshAccessView(TokenRefreshView):
    """Exchange a valid refresh token for a new access token."""

    serializer_class = TokenRefreshSerializer


@extend_schema_view(
    get=extend_schema(
        operation_id="auth_me",
        tags=["authentication"],
        summary="Who am I",
        description=(
            "Returns the identity of the account carried by the access token."
            "\n\n"
            "Send the **access** token — not the refresh token — in the "
            "`Authorization` header:\n\n"
            "```\nAuthorization: Bearer <access token>\n```\n\n"
            "Only JWT is accepted here. An administration session is "
            "deliberately not enough: this endpoint exists to prove that a "
            "token works.\n\n"
            "The response carries `id` and `username` only. It says nothing "
            "about what the account may do — authentication is not "
            "authorisation, and being authenticated grants no additional "
            "access to entities at this stage."
        ),
        responses={
            200: OpenApiResponse(
                response=CurrentUserSerializer,
                description="The token is valid and its account is active.",
                examples=[
                    OpenApiExample(
                        "Authenticated account (synthetic)",
                        description=(
                            "Invented account, shown to illustrate the shape."
                        ),
                        response_only=True,
                        value={"id": 1, "username": "example-contributor"},
                    )
                ],
            ),
            401: UNAUTHENTICATED_RESPONSE,
        },
    )
)
class CurrentUserView(RetrieveAPIView[User]):
    """Return the authenticated account's own identity."""

    serializer_class = CurrentUserSerializer
    # `authentication_classes` est restreint à JWT, alors que le projet
    # accepte aussi la session : cette vue sert à vérifier un jeton, et une
    # session d'administration ouverte la ferait répondre sans qu'aucun JWT
    # soit valide.
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_object(self) -> User:
        """Return the requesting account itself.

        There is no lookup by identifier: this endpoint can only ever return
        the caller, never another account.
        """
        assert isinstance(self.request.user, User)
        return self.request.user
