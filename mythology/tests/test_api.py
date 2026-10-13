from collections.abc import Callable
from contextlib import AbstractContextManager

import pytest
from django.test import Client
from django.urls import reverse

from mythology.models import EntityType
from mythology.tests.factories import create_divinity_profile, create_entity

pytestmark = pytest.mark.django_db


def test_liste_est_compacte_et_publique(client: Client) -> None:
    """La collection est accessible sans authentification et reste compacte."""
    create_entity(name="Shango", slug="shango", category="Orisha of Lightning")

    response = client.get(reverse("entity-list"))

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert set(payload[0]) == {"id", "slug", "name", "entity_type", "category"}
    assert payload[0]["slug"] == "shango"
    assert payload[0]["entity_type"] == EntityType.DIVINITY


def test_detail_imbrique_le_profil_de_divinite(client: Client) -> None:
    """Le détail expose les champs communs et le profil quand il existe."""
    entity = create_entity(
        name="Shango",
        slug="shango",
        story_description="Récit du dieu du tonnerre.",
        characteristics=["Colérique"],
        symbols=["Hache à double tranchant"],
    )
    create_divinity_profile(entity, cult_offerings=["Igname"], cult_taboos=["Mensonge"])

    response = client.get(reverse("entity-detail", kwargs={"slug": "shango"}))

    assert response.status_code == 200
    payload = response.json()
    assert payload["story_description"] == "Récit du dieu du tonnerre."
    assert payload["characteristics"] == ["Colérique"]
    assert payload["divinity_profile"]["cult_offerings"] == ["Igname"]
    assert payload["divinity_profile"]["cult_festivals"] == []


def test_detail_sans_profil(client: Client) -> None:
    """Une entité sans profil expose `divinity_profile` à `null`."""
    create_entity(name="Soundiata", slug="soundiata", entity_type=EntityType.HERO)

    response = client.get(reverse("entity-detail", kwargs={"slug": "soundiata"}))

    assert response.status_code == 200
    assert response.json()["divinity_profile"] is None


def test_detail_charge_le_profil_en_une_requete(
    client: Client,
    django_assert_num_queries: Callable[[int], AbstractContextManager[None]],
) -> None:
    """`select_related` évite la requête supplémentaire vers le profil."""
    entity = create_entity()
    create_divinity_profile(entity)

    with django_assert_num_queries(1):
        client.get(reverse("entity-detail", kwargs={"slug": entity.slug}))


def test_slug_inconnu_renvoie_404(client: Client) -> None:
    response = client.get(reverse("entity-detail", kwargs={"slug": "inexistant"}))

    assert response.status_code == 404


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_ecriture_refusee_sur_la_liste(client: Client, method: str) -> None:
    """La collection est strictement en lecture seule."""
    response = getattr(client, method)(reverse("entity-list"))

    assert response.status_code == 405


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_ecriture_refusee_sur_le_detail(client: Client, method: str) -> None:
    """Le détail est strictement en lecture seule."""
    entity = create_entity()

    response = getattr(client, method)(
        reverse("entity-detail", kwargs={"slug": entity.slug})
    )

    assert response.status_code == 405
