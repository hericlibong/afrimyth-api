from collections.abc import Callable
from contextlib import AbstractContextManager

import pytest
from django.test import Client
from django.urls import reverse

from mythology.models import CulturalAreaKind, Entity, EntityType, ThreatLevel
from mythology.serializers import EntityDetailSerializer
from mythology.tests.factories import (
    create_country,
    create_creature,
    create_creature_profile,
    create_cultural_area,
    create_divinity_profile,
    create_domain,
    create_entity,
    create_ethnicity,
    create_hero,
    create_hero_profile,
)
from mythology.views import EntityViewSet

pytestmark = pytest.mark.django_db

PROFILE_KEYS = {"divinity_profile", "hero_profile", "creature_profile"}

REFERENCE_KEYS = {
    "primary_country",
    "secondary_countries",
    "primary_ethnicity",
    "secondary_ethnicities",
    "primary_cultural_area",
    "secondary_cultural_areas",
    "domains",
}


def entity_entierement_reliee() -> Entity:
    """Crée une entité rattachée à chacun des quatre référentiels.

    Deux valeurs par collection permettent de vérifier le contenu des listes.
    """
    entity = create_entity(
        primary_country=create_country(),
        primary_ethnicity=create_ethnicity(),
        primary_cultural_area=create_cultural_area(),
    )
    entity.secondary_countries.add(
        create_country(name="Benin", slug="benin", iso_code="BJ"),
        create_country(name="Togo", slug="togo", iso_code="TG"),
    )
    entity.secondary_ethnicities.add(
        create_ethnicity(name="Fon", slug="fon"),
        create_ethnicity(name="Ewe", slug="ewe"),
    )
    entity.secondary_cultural_areas.add(
        create_cultural_area(
            name="Pan-African",
            slug="pan-african",
            kind=CulturalAreaKind.TRANSREGIONAL,
        ),
        create_cultural_area(
            name="Caribbean diaspora",
            slug="caribbean-diaspora",
            kind=CulturalAreaKind.DIASPORIC,
        ),
    )
    entity.domains.add(
        create_domain(),
        create_domain(name="Justice", slug="justice"),
    )
    return entity


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


def test_liste_n_expose_aucun_referentiel(client: Client) -> None:
    """Le contrat de la collection est inchangé par l'ajout des référentiels.

    Non-régression : une entité entièrement rattachée ne doit pas élargir la
    réponse de liste d'un seul champ.
    """
    entity_entierement_reliee()

    response = client.get(reverse("entity-list"))

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert set(payload[0]) == {"id", "slug", "name", "entity_type", "category"}
    assert not REFERENCE_KEYS & set(payload[0])


def test_detail_expose_les_referentiels(client: Client) -> None:
    """Le détail porte les sept clés de référentiel, objets et listes."""
    entity = entity_entierement_reliee()

    response = client.get(reverse("entity-detail", kwargs={"slug": entity.slug}))

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) >= REFERENCE_KEYS

    assert payload["primary_country"]["name"] == "Nigeria"
    assert payload["primary_country"]["iso_code"] == "NG"
    assert set(payload["primary_country"]) == {"id", "slug", "name", "iso_code"}

    assert payload["primary_ethnicity"]["name"] == "Yoruba"
    assert set(payload["primary_ethnicity"]) == {"id", "slug", "name"}

    assert payload["primary_cultural_area"]["name"] == "West Africa"
    assert payload["primary_cultural_area"]["kind"] == CulturalAreaKind.AFRICAN_REGION
    assert set(payload["primary_cultural_area"]) == {"id", "slug", "name", "kind"}

    assert [item["name"] for item in payload["secondary_countries"]] == [
        "Benin",
        "Togo",
    ]
    assert [item["name"] for item in payload["secondary_ethnicities"]] == [
        "Ewe",
        "Fon",
    ]
    assert [item["name"] for item in payload["secondary_cultural_areas"]] == [
        "Caribbean diaspora",
        "Pan-African",
    ]
    assert [item["name"] for item in payload["domains"]] == ["Justice", "Thunder"]


def test_detail_sans_referentiel(client: Client) -> None:
    """Sans rattachement, les ancrages sont `null` et les listes vides."""
    entity = create_entity()

    response = client.get(reverse("entity-detail", kwargs={"slug": entity.slug}))

    assert response.status_code == 200
    payload = response.json()
    assert payload["primary_country"] is None
    assert payload["primary_ethnicity"] is None
    assert payload["primary_cultural_area"] is None
    assert payload["secondary_countries"] == []
    assert payload["secondary_ethnicities"] == []
    assert payload["secondary_cultural_areas"] == []
    assert payload["domains"] == []


def test_detail_n_imbrique_pas_le_graphe_des_referentiels(client: Client) -> None:
    """Les représentations de référence restent plates.

    Ni `parent`, ni `children`, ni le `primary_cultural_area` d'une ethnie ne
    sont sérialisés : c'est ce qui évite des cascades de requêtes sans besoin
    client établi.
    """
    parent = create_cultural_area(name="Africa", slug="africa")
    area = create_cultural_area(name="West Africa", slug="west-africa-2", parent=parent)
    ethnicity = create_ethnicity(primary_cultural_area=area)
    entity = create_entity(primary_cultural_area=area, primary_ethnicity=ethnicity)

    response = client.get(reverse("entity-detail", kwargs={"slug": entity.slug}))

    payload = response.json()
    assert "parent" not in payload["primary_cultural_area"]
    assert "children" not in payload["primary_cultural_area"]
    assert "primary_cultural_area" not in payload["primary_ethnicity"]


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


def test_detail_a_un_cout_constant_quel_que_soit_le_type(
    client: Client,
    django_assert_num_queries: Callable[[int], AbstractContextManager[None]],
) -> None:
    """Le détail coûte 5 requêtes pour chacun des trois types.

    Les trois profils et les trois ancrages principaux sont joints à la
    requête de l'entité par `select_related` ; les quatre requêtes restantes
    sont celles des `prefetch_related`, que Django exécute même lorsque les
    collections sont vides.

    Ce que le test protège : qu'aucun profil ne déclenche de requête
    supplémentaire, et que le coût ne dépende pas du type de l'entité.
    """
    divinity = create_entity()
    create_divinity_profile(divinity)
    hero = create_hero()
    create_hero_profile(hero)
    creature = create_creature()
    create_creature_profile(creature)

    for entity in (divinity, hero, creature):
        with django_assert_num_queries(5):
            client.get(reverse("entity-detail", kwargs={"slug": entity.slug}))


def test_detail_entierement_relie_ne_provoque_pas_de_n_plus_un(
    client: Client,
    django_assert_num_queries: Callable[[int], AbstractContextManager[None]],
) -> None:
    """Le détail d'une entité entièrement rattachée coûte 5 requêtes.

    Décompte : 1 requête pour l'entité, qui ramène par `select_related` les
    trois profils et les trois ancrages principaux, puis 1 requête par
    collection `prefetch_related` — pays, ethnies et aires secondaires, et
    domaines.

    Ce test fixe le budget global de requêtes du détail. À lui seul, il ne
    prouve pas le préchargement : une collection non préchargée demande aussi
    une seule requête pour cette unique entité, quel que soit son contenu.
    """
    entity = entity_entierement_reliee()
    create_divinity_profile(entity)

    with django_assert_num_queries(5):
        response = client.get(reverse("entity-detail", kwargs={"slug": entity.slug}))

    assert response.status_code == 200


def test_detail_precharge_se_serialise_sans_requete(
    django_assert_num_queries: Callable[[int], AbstractContextManager[None]],
) -> None:
    """Le queryset de la vue fournit toutes les données au serializer.

    Retirer un préchargement provoque une requête pendant la sérialisation,
    même si le budget global de l'endpoint reste identique.
    """
    entity = entity_entierement_reliee()
    create_divinity_profile(entity)
    view = EntityViewSet()
    view.action = "retrieve"
    loaded = view.get_queryset().get(pk=entity.pk)

    with django_assert_num_queries(0):
        payload = EntityDetailSerializer(loaded).data

    assert len(payload["secondary_countries"]) == 2
    assert len(payload["domains"]) == 2


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
