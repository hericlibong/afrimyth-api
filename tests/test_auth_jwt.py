"""Tests for the three JWT endpoints.

All accounts are synthetic and isolated in the test database. No real
credential is used. Expiration is manufactured in token payloads rather than
waiting for wall-clock time.
"""

from datetime import timedelta
from typing import Any

import jwt
import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from accounts.models import User

pytestmark = pytest.mark.django_db

TOKEN_URL = reverse("token-obtain-pair")
REFRESH_URL = reverse("token-refresh")
ME_URL = reverse("current-user")

PASSWORD = "synthetic-test-passphrase-7421"


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def account() -> User:
    """An active account without administrative privileges."""
    return User.objects.create_user(
        username="test-contributor",
        password=PASSWORD,
        email="test-contributor@example.invalid",
    )


def obtain(api: APIClient, username: str, password: str) -> Any:
    return api.post(
        TOKEN_URL, {"username": username, "password": password}, format="json"
    )


def bearer(api: APIClient, token: str) -> None:
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


# --- Obtention de jetons ------------------------------------------------


def test_identifiants_valides_renvoient_une_paire_de_jetons(
    api: APIClient, account: User
) -> None:
    response = obtain(api, account.username, PASSWORD)

    assert response.status_code == 200
    assert set(response.data) == {"access", "refresh"}
    assert response.data["access"]
    assert response.data["refresh"]


def test_le_jeton_d_acces_porte_le_bon_compte(api: APIClient, account: User) -> None:
    response = obtain(api, account.username, PASSWORD)
    token = AccessToken(response.data["access"])

    # Simple JWT 5.5 sérialise l'identifiant en chaîne dans la charge, quel
    # que soit le type de la clé primaire : on compare donc sur `str`.
    assert token["user_id"] == str(account.pk)


def test_la_reponse_de_jeton_ne_contient_aucune_donnee_de_compte(
    api: APIClient, account: User
) -> None:
    """Token issuance must not expose account profile data."""
    response = obtain(api, account.username, PASSWORD)
    body = response.content.decode()

    assert "example.invalid" not in body
    assert PASSWORD not in body


@pytest.mark.parametrize(
    "payload",
    [
        {"username": "test-contributor", "password": "mauvais-mot-de-passe"},
        {"username": "compte-inexistant", "password": PASSWORD},
    ],
    ids=["mot-de-passe-errone", "compte-inconnu"],
)
def test_identifiants_invalides_sont_refuses(
    api: APIClient, account: User, payload: dict[str, str]
) -> None:
    response = api.post(TOKEN_URL, payload, format="json")

    assert response.status_code == 401
    assert "access" not in response.data


def test_un_compte_inconnu_et_un_mot_de_passe_errone_sont_indistinguables(
    api: APIClient, account: User
) -> None:
    """The response must not reveal whether a username exists."""
    errone = obtain(api, account.username, "mauvais-mot-de-passe")
    inconnu = obtain(api, "compte-inexistant", PASSWORD)

    assert errone.status_code == inconnu.status_code
    assert errone.data == inconnu.data


@pytest.mark.parametrize(
    "payload",
    [{}, {"username": "test-contributor"}, {"password": PASSWORD}],
    ids=["corps-vide", "mot-de-passe-absent", "nom-absent"],
)
def test_champs_manquants_donnent_400(
    api: APIClient, account: User, payload: dict[str, str]
) -> None:
    """A missing field is a malformed request, not an identity failure."""
    response = api.post(TOKEN_URL, payload, format="json")

    assert response.status_code == 400


def test_un_compte_desactive_ne_peut_pas_obtenir_de_jeton(
    api: APIClient, account: User
) -> None:
    account.is_active = False
    account.save(update_fields=["is_active"])

    response = obtain(api, account.username, PASSWORD)

    assert response.status_code == 401


def test_la_route_de_jetons_refuse_get(api: APIClient) -> None:
    assert api.get(TOKEN_URL).status_code == 405


def test_la_route_de_jetons_est_ouverte_malgre_le_defaut_ferme(
    api: APIClient,
) -> None:
    """Token issuance must remain reachable without prior authentication."""
    response = api.post(TOKEN_URL, {}, format="json")

    # 400 — la requête est atteinte et validée. Un 401 ou 403 signalerait que
    # la permission a bloqué avant d'y arriver.
    assert response.status_code == 400


def test_la_route_de_renouvellement_est_ouverte_malgre_le_defaut_ferme(
    api: APIClient,
) -> None:
    """The refresh token is the credential; no authorization header is needed."""
    response = api.post(REFRESH_URL, {}, format="json")

    assert response.status_code == 400


# --- Identité -----------------------------------------------------------


def test_me_renvoie_l_identite_du_porteur(api: APIClient, account: User) -> None:
    bearer(api, str(AccessToken.for_user(account)))

    response = api.get(ME_URL)

    assert response.status_code == 200
    assert response.data == {"id": account.pk, "username": account.username}


def test_me_n_expose_que_l_identifiant_et_le_nom(api: APIClient, account: User) -> None:
    """Identity must expose no email, password hash or administrative flag."""
    account.is_staff = True
    account.is_superuser = True
    account.save(update_fields=["is_staff", "is_superuser"])
    bearer(api, str(AccessToken.for_user(account)))

    response = api.get(ME_URL)
    body = response.content.decode()

    assert set(response.data) == {"id", "username"}
    assert "example.invalid" not in body
    assert account.password not in body


def test_me_sans_jeton_est_refuse(api: APIClient) -> None:
    response = api.get(ME_URL)

    assert response.status_code == 401


def test_me_refuse_une_session_django(api: APIClient, account: User) -> None:
    """The identity endpoint accepts JWT, not a Django session."""
    api.force_login(account)

    response = api.get(ME_URL)

    assert response.status_code == 401


@pytest.mark.parametrize(
    "header",
    [
        "Bearer pas-un-jeton",
        "Bearer ",
        "Token abcdef",
        "eyJhbGciOiJIUzI1NiJ9.e30.signature",
    ],
    ids=["jeton-malforme", "jeton-vide", "schema-inattendu", "sans-schema"],
)
def test_me_refuse_un_en_tete_invalide(api: APIClient, header: str) -> None:
    api.credentials(HTTP_AUTHORIZATION=header)

    response = api.get(ME_URL)

    assert response.status_code == 401


def test_me_refuse_un_jeton_expire(api: APIClient, account: User) -> None:
    token = AccessToken.for_user(account)
    # On recule l'expiration dans le passé plutôt que d'attendre : le jeton
    # est signé après modification, donc valide en tout point sauf la date.
    token.set_exp(from_time=token.current_time - timedelta(hours=2))
    bearer(api, str(token))

    response = api.get(ME_URL)

    assert response.status_code == 401


def test_me_refuse_un_jeton_signe_avec_une_autre_cle(
    api: APIClient, account: User
) -> None:
    """Reject an otherwise valid payload signed with a different key."""
    authentique = AccessToken.for_user(account)
    forge = jwt.encode(
        authentique.payload,
        "synthetic-invalid-signing-key-for-tests-7421",
        algorithm="HS256",
    )
    assert forge != str(authentique)

    bearer(api, forge)

    response = api.get(ME_URL)

    assert response.status_code == 401


def test_me_refuse_un_jeton_de_renouvellement(api: APIClient, account: User) -> None:
    """Access and refresh tokens are not interchangeable."""
    bearer(api, str(RefreshToken.for_user(account)))

    response = api.get(ME_URL)

    assert response.status_code == 401


def test_un_compte_desactive_apres_emission_ne_peut_plus_lire_me(
    api: APIClient, account: User
) -> None:
    """A signed token must not authenticate an inactive account."""
    bearer(api, str(AccessToken.for_user(account)))
    assert api.get(ME_URL).status_code == 200

    account.is_active = False
    account.save(update_fields=["is_active"])

    assert api.get(ME_URL).status_code == 401


def test_un_compte_supprime_apres_emission_ne_peut_plus_lire_me(
    api: APIClient, account: User
) -> None:
    bearer(api, str(AccessToken.for_user(account)))
    assert api.get(ME_URL).status_code == 200

    account.delete()

    assert api.get(ME_URL).status_code == 401


def test_me_refuse_post(api: APIClient, account: User) -> None:
    bearer(api, str(AccessToken.for_user(account)))

    assert api.post(ME_URL, {}, format="json").status_code == 405


# --- Renouvellement -----------------------------------------------------


def test_un_renouvellement_valide_donne_un_nouvel_acces(
    api: APIClient, account: User
) -> None:
    refresh = str(RefreshToken.for_user(account))

    response = api.post(REFRESH_URL, {"refresh": refresh}, format="json")

    assert response.status_code == 200
    assert "access" in response.data
    assert AccessToken(response.data["access"])["user_id"] == str(account.pk)


def test_l_acces_renouvele_est_accepte_par_me(api: APIClient, account: User) -> None:
    refresh = str(RefreshToken.for_user(account))
    renewed = api.post(REFRESH_URL, {"refresh": refresh}, format="json")

    bearer(api, renewed.data["access"])

    assert api.get(ME_URL).status_code == 200


def test_sans_rotation_le_renouvellement_ne_renvoie_pas_de_refresh(
    api: APIClient, account: User
) -> None:
    """Without rotation the client keeps the original refresh token."""
    refresh = str(RefreshToken.for_user(account))

    response = api.post(REFRESH_URL, {"refresh": refresh}, format="json")

    assert set(response.data) == {"access"}


def test_un_refresh_reste_utilisable_plusieurs_fois(
    api: APIClient, account: User
) -> None:
    """The configured refresh token can be reused until expiration."""
    refresh = str(RefreshToken.for_user(account))

    premier = api.post(REFRESH_URL, {"refresh": refresh}, format="json")
    second = api.post(REFRESH_URL, {"refresh": refresh}, format="json")

    assert premier.status_code == 200
    assert second.status_code == 200


def test_le_renouvellement_n_invalide_pas_l_acces_precedent(
    api: APIClient, account: User
) -> None:
    """Refreshing does not revoke the previously issued access token."""
    precedent = str(AccessToken.for_user(account))
    refresh = str(RefreshToken.for_user(account))
    api.post(REFRESH_URL, {"refresh": refresh}, format="json")

    bearer(api, precedent)

    assert api.get(ME_URL).status_code == 200


@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [({}, 400), ({"refresh": ""}, 400), ({"refresh": "pas-un-jeton"}, 401)],
    ids=["corps-vide", "valeur-vide", "jeton-malforme"],
)
def test_un_renouvellement_invalide_est_refuse(
    api: APIClient, payload: dict[str, str], expected_status: int
) -> None:
    response = api.post(REFRESH_URL, payload, format="json")

    assert response.status_code == expected_status
    assert "access" not in response.data


def test_un_refresh_expire_est_refuse(api: APIClient, account: User) -> None:
    refresh = RefreshToken.for_user(account)
    refresh.set_exp(from_time=refresh.current_time - timedelta(days=3))

    response = api.post(REFRESH_URL, {"refresh": str(refresh)}, format="json")

    assert response.status_code == 401


def test_un_jeton_d_acces_n_est_pas_accepte_comme_refresh(
    api: APIClient, account: User
) -> None:
    """An access token cannot be used as a refresh token."""
    access = str(AccessToken.for_user(account))

    response = api.post(REFRESH_URL, {"refresh": access}, format="json")

    assert response.status_code == 401


def test_les_deux_types_de_jetons_sont_distingues_a_la_lecture(
    account: User,
) -> None:
    """Token types are validated independently of endpoint permissions."""
    access = str(AccessToken.for_user(account))

    with pytest.raises(TokenError):
        # Le paramètre est annoté `Token | None` par la bibliothèque, alors
        # qu'il reçoit la forme encodée, c'est-à-dire une chaîne. Annotation
        # inexacte en amont, pas erreur d'appel.
        RefreshToken(access)  # type: ignore[arg-type]


def test_la_route_de_renouvellement_refuse_get(api: APIClient) -> None:
    assert api.get(REFRESH_URL).status_code == 405


@pytest.mark.parametrize("deleted", [False, True], ids=["inactive", "deleted"])
def test_refresh_refuses_an_unavailable_account(
    api: APIClient, account: User, deleted: bool
) -> None:
    """An unavailable account must produce a refusal, never a server error."""
    refresh = str(RefreshToken.for_user(account))
    if deleted:
        account.delete()
    else:
        account.is_active = False
        account.save(update_fields=["is_active"])

    response = api.post(REFRESH_URL, {"refresh": refresh}, format="json")

    assert response.status_code == 401
    assert "access" not in response.data
