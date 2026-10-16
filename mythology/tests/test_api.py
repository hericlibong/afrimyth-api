from collections.abc import Callable
from contextlib import AbstractContextManager

import pytest
from django.test import Client
from django.urls import reverse

from mythology.models import EntityType, ThreatLevel
from mythology.tests.factories import (
    create_creature,
    create_creature_profile,
    create_divinity_profile,
    create_entity,
    create_hero,
    create_hero_profile,
)

pytestmark = pytest.mark.django_db

PROFILE_KEYS = {"divinity_profile", "hero_profile", "creature_profile"}


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


def test_liste_n_expose_aucun_profil(client: Client) -> None:
    """La collection reste compacte pour les trois types, profils exclus."""
    create_divinity_profile(create_entity())
    create_hero_profile(create_hero())
    create_creature_profile(create_creature())

    response = client.get(reverse("entity-list"))

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 3
    for item in payload:
        assert set(item) == {"id", "slug", "name", "entity_type", "category"}
        assert not PROFILE_KEYS & set(item)


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
    assert payload["hero_profile"] is None
    assert payload["creature_profile"] is None


def test_detail_imbrique_le_profil_de_heros(client: Client) -> None:
    """Le détail d'un héros porte son profil, les deux autres restant `null`."""
    hero = create_hero()
    create_hero_profile(
        hero,
        titles=["Roi du Mali"],
        quests=["Unifier le Manden"],
        legacy="Fondateur de l'empire du Mali.",
    )

    response = client.get(reverse("entity-detail", kwargs={"slug": hero.slug}))

    assert response.status_code == 200
    payload = response.json()
    assert payload["entity_type"] == EntityType.HERO
    assert payload["hero_profile"]["titles"] == ["Roi du Mali"]
    assert payload["hero_profile"]["quests"] == ["Unifier le Manden"]
    assert payload["hero_profile"]["legacy"] == "Fondateur de l'empire du Mali."
    assert payload["hero_profile"]["achievements"] == []
    assert payload["divinity_profile"] is None
    assert payload["creature_profile"] is None


def test_detail_imbrique_le_profil_de_creature(client: Client) -> None:
    """Le détail d'une créature porte son profil, les deux autres `null`."""
    creature = create_creature()
    create_creature_profile(
        creature,
        habitat=["Marais du bassin du Congo"],
        diet="Herbivore",
        threat_level=ThreatLevel.HIGH,
    )

    response = client.get(reverse("entity-detail", kwargs={"slug": creature.slug}))

    assert response.status_code == 200
    payload = response.json()
    assert payload["entity_type"] == EntityType.CREATURE
    assert payload["creature_profile"]["habitat"] == ["Marais du bassin du Congo"]
    assert payload["creature_profile"]["diet"] == "Herbivore"
    assert payload["creature_profile"]["threat_level"] == ThreatLevel.HIGH
    assert payload["creature_profile"]["known_sightings"] == []
    assert payload["divinity_profile"] is None
    assert payload["hero_profile"] is None


def test_detail_sans_profil(client: Client) -> None:
    """Sans profil, les trois clés sont présentes et toutes à `null`."""
    create_entity(name="Soundiata", slug="soundiata", entity_type=EntityType.HERO)

    response = client.get(reverse("entity-detail", kwargs={"slug": "soundiata"}))

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) >= PROFILE_KEYS
    assert all(payload[key] is None for key in PROFILE_KEYS)


def test_threat_level_absent_est_null(client: Client) -> None:
    """Un `threat_level` non renseigné est sérialisé en `null`, non en `""`."""
    creature = create_creature()
    create_creature_profile(creature)

    response = client.get(reverse("entity-detail", kwargs={"slug": creature.slug}))

    assert response.json()["creature_profile"]["threat_level"] is None


def test_detail_charge_les_trois_profils_en_une_requete(
    client: Client,
    django_assert_num_queries: Callable[[int], AbstractContextManager[None]],
) -> None:
    """`select_related` joint les trois profils sans requête supplémentaire.

    Le détail reste à une seule requête quel que soit le type de l'entité :
    c'est ce que vérifie ce test, et non un quelconque temps de réponse.
    """
    divinity = create_entity()
    create_divinity_profile(divinity)
    hero = create_hero()
    create_hero_profile(hero)
    creature = create_creature()
    create_creature_profile(creature)

    for entity in (divinity, hero, creature):
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
