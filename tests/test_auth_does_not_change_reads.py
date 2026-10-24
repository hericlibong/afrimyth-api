"""JWT must preserve anonymous reads, public visibility and read-only content."""

import pytest
from django.test import Client
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from mythology.tests.factories import create_entity, create_published_entity

pytestmark = pytest.mark.django_db

LIST_URL = reverse("entity-list")

PASSWORD = "synthetic-test-passphrase-7421"


@pytest.fixture
def account() -> User:
    return User.objects.create_user(username="test-reader", password=PASSWORD)


@pytest.fixture
def authenticated(account: User) -> APIClient:
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(account)}")
    return api


def detail_url(slug: str) -> str:
    return reverse("entity-detail", kwargs={"slug": slug})


# --- La lecture reste anonyme -------------------------------------------


def test_la_liste_reste_lisible_sans_jeton(client: Client) -> None:
    create_published_entity(slug="lecture-anonyme", name="Lecture anonyme")

    response = client.get(LIST_URL)

    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_le_detail_reste_lisible_sans_jeton(client: Client) -> None:
    create_published_entity(slug="detail-anonyme", name="Detail anonyme")

    response = client.get(detail_url("detail-anonyme"))

    assert response.status_code == 200


def test_la_sante_et_le_schema_restent_lisibles_sans_jeton(client: Client) -> None:
    for name in ("health", "schema", "swagger-ui", "redoc"):
        assert client.get(reverse(name)).status_code == 200, name


# --- Un jeton ne débloque aucune visibilité -----------------------------


def test_un_jeton_valide_ne_revele_pas_les_brouillons(
    authenticated: APIClient,
) -> None:
    create_entity(slug="brouillon-cache", name="Brouillon cache")

    liste = authenticated.get(LIST_URL)
    detail = authenticated.get(detail_url("brouillon-cache"))

    assert liste.status_code == 200
    assert liste.json()["count"] == 0
    assert detail.status_code == 404


def test_un_jeton_valide_voit_exactement_la_meme_liste_qu_un_anonyme(
    client: Client, authenticated: APIClient
) -> None:
    create_published_entity(slug="visible", name="Visible")
    create_entity(slug="invisible", name="Invisible")

    anonyme = client.get(LIST_URL)
    connecte = authenticated.get(LIST_URL)

    assert anonyme.json() == connecte.json()


# --- L'écriture reste refusée ------------------------------------------


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_l_ecriture_est_refusee_sans_jeton(client: Client, method: str) -> None:
    create_published_entity(slug="immuable", name="Immuable")

    collection = getattr(client, method)(LIST_URL)
    fiche = getattr(client, method)(detail_url("immuable"))

    assert collection.status_code == 405
    assert fiche.status_code == 405


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_l_ecriture_reste_refusee_avec_un_jeton(
    authenticated: APIClient, method: str
) -> None:
    """Authentication does not grant permission to write content."""
    create_published_entity(slug="immuable", name="Immuable")

    collection = getattr(authenticated, method)(LIST_URL)
    fiche = getattr(authenticated, method)(detail_url("immuable"))

    assert collection.status_code == 405
    assert fiche.status_code == 405


def test_un_en_tete_bearer_invalide_fait_echouer_meme_une_lecture_publique(
    client: Client,
) -> None:
    """An invalid Bearer header fails before public permissions are evaluated."""
    create_published_entity(slug="visible", name="Visible")

    response = client.get(LIST_URL, HTTP_AUTHORIZATION="Bearer pas-un-jeton")

    assert response.status_code == 401
