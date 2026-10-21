import datetime
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from mythology.models import (
    CulturalAreaKind,
    Entity,
    EntityStatus,
    EntityType,
    RelationKind,
    SourceKind,
    ThreatLevel,
)
from mythology.serializers import EntityDetailSerializer
from mythology.tests.factories import (
    create_country,
    create_creature_profile,
    create_cultural_area,
    create_divinity_profile,
    create_domain,
    create_entity,
    create_ethnicity,
    create_hero_profile,
    create_published_entity,
    create_relation,
    create_source,
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

# Champs de plateforme : internes à cet incrément, aucun ne doit apparaître
# dans l'API publique. Le contrat destiné aux contributeurs sera préparé avec
# les permissions, en phase 4.
INTERNAL_KEYS = {
    "created_by",
    "status",
    "submitted_at",
    "reviewed_at",
    "reviewed_by",
    "review_notes",
    "deleted_at",
    "deleted_by",
}


def published_hero(**extra: Any) -> Entity:
    """Héros **publié**, donc lisible par l'API publique."""
    return create_published_entity(
        name="Soundiata", slug="soundiata", entity_type=EntityType.HERO, **extra
    )


def published_creature(**extra: Any) -> Entity:
    """Créature **publiée**, donc lisible par l'API publique."""
    return create_published_entity(
        name="Mokele-mbembe",
        slug="mokele-mbembe",
        entity_type=EntityType.CREATURE,
        **extra,
    )


def entity_entierement_reliee() -> Entity:
    """Crée une entité rattachée à chacun des quatre référentiels.

    Deux valeurs par collection permettent de vérifier le contenu des listes.
    """
    entity = create_published_entity(
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
    create_published_entity(
        name="Shango", slug="shango", category="Orisha of Lightning"
    )

    response = client.get(reverse("entity-list"))

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert set(payload[0]) == {"id", "slug", "name", "entity_type", "category"}
    assert payload[0]["slug"] == "shango"
    assert payload[0]["entity_type"] == EntityType.DIVINITY


def test_liste_n_expose_aucun_profil(client: Client) -> None:
    """La collection reste compacte pour les trois types, profils exclus."""
    create_divinity_profile(create_published_entity())
    create_hero_profile(
        create_published_entity(
            name="Soundiata", slug="soundiata", entity_type=EntityType.HERO
        )
    )
    create_creature_profile(
        create_published_entity(
            name="Mokele", slug="mokele", entity_type=EntityType.CREATURE
        )
    )

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
    entity = create_published_entity()

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
    entity = create_published_entity(
        primary_cultural_area=area, primary_ethnicity=ethnicity
    )

    response = client.get(reverse("entity-detail", kwargs={"slug": entity.slug}))

    payload = response.json()
    assert "parent" not in payload["primary_cultural_area"]
    assert "children" not in payload["primary_cultural_area"]
    assert "primary_cultural_area" not in payload["primary_ethnicity"]


def test_liste_n_expose_ni_variante_ni_relations(client: Client) -> None:
    """Le contrat de la collection reste strictement inchangé."""
    reference = create_published_entity(name="Mami Wata", slug="mami-wata")
    variante = create_published_entity(
        name="Mami Wata (Caribbean)",
        slug="mami-wata-caribbean",
        variant_of=reference,
    )
    create_relation(variante, RelationKind.PARENT, to_name="Yemoja")

    response = client.get(reverse("entity-list"))

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    for item in payload:
        assert set(item) == {"id", "slug", "name", "entity_type", "category"}


def test_detail_expose_la_figure_de_reference(client: Client) -> None:
    """`variant_of` est une référence synthétique à quatre champs."""
    reference = create_published_entity(
        name="Mami Wata", slug="mami-wata", entity_type=EntityType.CREATURE
    )
    variante = create_published_entity(
        name="Mami Wata (Vodun)",
        slug="mami-wata-vodun",
        variant_of=reference,
    )

    response = client.get(reverse("entity-detail", kwargs={"slug": variante.slug}))

    assert response.status_code == 200
    payload = response.json()
    assert set(payload["variant_of"]) == {"id", "slug", "name", "entity_type"}
    assert payload["variant_of"]["slug"] == "mami-wata"
    # Le type de la référence peut différer de celui de la variante.
    assert payload["variant_of"]["entity_type"] == EntityType.CREATURE
    assert payload["entity_type"] == EntityType.DIVINITY


def test_detail_sans_variante_ni_relation(client: Client) -> None:
    """Sans lien : `variant_of` vaut `null` et `relations` est vide."""
    entity = create_published_entity()

    response = client.get(reverse("entity-detail", kwargs={"slug": entity.slug}))

    assert response.status_code == 200
    payload = response.json()
    assert payload["variant_of"] is None
    assert payload["relations"] == []


def test_detail_expose_les_relations_sortantes(client: Client) -> None:
    """Chaque relation porte `id`, `kind`, `to_entity`, `to_name`, `notes`.

    Une cible résolue conserve `to_name=""` ; une cible absente porte son nom
    et `to_entity=null`.
    """
    source = create_published_entity(name="Shango", slug="shango")
    cible = create_published_entity(name="Oranyan", slug="oranyan")
    create_relation(
        source,
        RelationKind.PARENT,
        to_entity=cible,
        notes="Lignée royale d'Oyo.",
    )
    create_relation(source, RelationKind.ENEMY, to_name="Figure sans fiche")

    response = client.get(reverse("entity-detail", kwargs={"slug": source.slug}))

    assert response.status_code == 200
    relations = response.json()["relations"]
    assert len(relations) == 2
    for relation in relations:
        assert set(relation) == {"id", "kind", "to_entity", "to_name", "notes"}

    # Ordre déterministe : `kind` d'abord, donc `enemy` avant `parent`.
    non_resolue, resolue = relations
    assert non_resolue["kind"] == RelationKind.ENEMY
    assert non_resolue["to_entity"] is None
    assert non_resolue["to_name"] == "Figure sans fiche"
    assert resolue["kind"] == RelationKind.PARENT
    assert resolue["to_name"] == ""
    assert resolue["notes"] == "Lignée royale d'Oyo."
    assert set(resolue["to_entity"]) == {"id", "slug", "name", "entity_type"}
    assert resolue["to_entity"]["name"] == "Oranyan"


def test_detail_n_imbrique_pas_le_detail_des_cibles(client: Client) -> None:
    """Les cibles restent synthétiques : aucune récursion possible.

    Si la cible était sérialisée en détail, elle exposerait à son tour ses
    propres `relations` et `variant_of`, et la réponse partirait en cascade.
    """
    source = create_published_entity(name="A", slug="a")
    cible = create_published_entity(name="B", slug="b", variant_of=source)
    create_relation(source, RelationKind.ALLY, to_entity=cible)

    response = client.get(reverse("entity-detail", kwargs={"slug": source.slug}))

    cible_json = response.json()["relations"][0]["to_entity"]
    assert "relations" not in cible_json
    assert "variant_of" not in cible_json
    assert "story_description" not in cible_json


def test_detail_n_expose_pas_les_relations_entrantes(client: Client) -> None:
    """Seules les relations sortantes figurent dans la réponse."""
    source = create_published_entity(name="A", slug="a")
    cible = create_published_entity(name="B", slug="b")
    create_relation(source, RelationKind.PARENT, to_entity=cible)

    response = client.get(reverse("entity-detail", kwargs={"slug": cible.slug}))

    payload = response.json()
    assert payload["relations"] == []
    assert "relations_to" not in payload


def test_liste_n_expose_pas_les_sources(client: Client) -> None:
    """Le contrat de la collection reste strictement inchangé.

    Les références employées ici sont fictives.
    """
    entity = create_published_entity()
    create_source(entity)

    response = client.get(reverse("entity-list"))

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert set(payload[0]) == {"id", "slug", "name", "entity_type", "category"}
    assert "sources" not in payload[0]


def test_detail_expose_les_sources(client: Client) -> None:
    """Chaque source porte `id`, `label`, `kind`, `url`, `accessed_at`, `notes`.

    Les références employées ici sont fictives.
    """
    entity = create_published_entity()
    create_source(
        entity,
        label="Fictional Encyclopedia of Imaginary Myths",
        kind=SourceKind.ENCYCLOPEDIA,
        url="https://example.invalid/fictional-entry",
        accessed_at=datetime.date(2026, 5, 20),
        notes="Volume 2, page 118 — fictional reference.",
    )

    response = client.get(reverse("entity-detail", kwargs={"slug": entity.slug}))

    assert response.status_code == 200
    sources = response.json()["sources"]
    assert len(sources) == 1
    source = sources[0]
    assert set(source) == {"id", "label", "kind", "url", "accessed_at", "notes"}
    assert source["label"] == "Fictional Encyclopedia of Imaginary Myths"
    assert source["kind"] == SourceKind.ENCYCLOPEDIA
    assert source["url"] == "https://example.invalid/fictional-entry"
    # Une date renseignée est exposée au format ISO `YYYY-MM-DD`.
    assert source["accessed_at"] == "2026-05-20"
    assert source["notes"] == "Volume 2, page 118 — fictional reference."
    # L'entité n'est pas réimbriquée dans sa propre source.
    assert "entity" not in source


def test_detail_sans_source(client: Client) -> None:
    """Sans source, la clé est présente et vaut une liste vide."""
    entity = create_published_entity()

    response = client.get(reverse("entity-detail", kwargs={"slug": entity.slug}))

    assert response.status_code == 200
    assert response.json()["sources"] == []


def test_detail_source_sans_url_ni_date(client: Client) -> None:
    """Sans URL : `url=""`. Sans date : `accessed_at=null`.

    Les références employées ici sont fictives.
    """
    entity = create_published_entity()
    create_source(
        entity,
        label="Fictional oral testimony, village of Testville",
        kind=SourceKind.ORAL,
    )

    response = client.get(reverse("entity-detail", kwargs={"slug": entity.slug}))

    source = response.json()["sources"][0]
    assert source["url"] == ""
    assert source["accessed_at"] is None
    assert source["notes"] == ""


def test_detail_ordonne_les_sources(client: Client) -> None:
    """L'ordre est déterministe : `label`, puis `id`.

    Les références employées ici sont fictives.
    """
    entity = create_published_entity()
    create_source(entity, label="Zeta Fictional Review", kind=SourceKind.ARTICLE)
    create_source(entity, label="Alpha Fictional Encyclopedia")
    create_source(entity, label="Mu Fictional Museum Catalogue")

    response = client.get(reverse("entity-detail", kwargs={"slug": entity.slug}))

    labels = [source["label"] for source in response.json()["sources"]]
    assert labels == [
        "Alpha Fictional Encyclopedia",
        "Mu Fictional Museum Catalogue",
        "Zeta Fictional Review",
    ]


def test_liste_ne_divulgue_aucun_champ_interne(client: Client) -> None:
    """Aucun champ de plateforme ne fuit dans la collection."""
    create_published_entity(review_notes="Private reviewer note.")

    response = client.get(reverse("entity-list"))

    assert response.status_code == 200
    payload = response.json()
    assert set(payload[0]) == {"id", "slug", "name", "entity_type", "category"}
    assert not INTERNAL_KEYS & set(payload[0])


def test_detail_ne_divulgue_aucun_champ_interne(client: Client) -> None:
    """Ni compte, ni note de relecture, ni champ de suppression dans le détail.

    Les notes de relecture sont privées, et les comptes ne doivent pas
    exposer d'identité. La vérification porte aussi sur la charge utile
    brute, pour attraper une fuite même sous une autre clé.
    """
    entity = create_published_entity(
        review_notes="Private reviewer note.",
        submitted_at=timezone.now(),
    )

    response = client.get(reverse("entity-detail", kwargs={"slug": entity.slug}))

    assert response.status_code == 200
    payload = response.json()
    assert not INTERNAL_KEYS & set(payload)
    assert "Private reviewer note." not in response.content.decode()


@pytest.mark.parametrize("status", EntityStatus.values)
def test_seule_une_fiche_publiee_est_visible(client: Client, status: str) -> None:
    """Seul `published` non supprimé apparaît ; les autres statuts donnent 404.

    Test paramétré sur les quatre statuts : `draft`, `submitted` et
    `rejected` sont invisibles, `published` est visible.
    """
    entity = create_entity(status=status)
    visible = status == EntityStatus.PUBLISHED

    liste = client.get(reverse("entity-list"))
    detail = client.get(reverse("entity-detail", kwargs={"slug": entity.slug}))

    assert len(liste.json()) == (1 if visible else 0)
    assert detail.status_code == (200 if visible else 404)


def test_fiche_supprimee_disparait_de_la_liste(client: Client) -> None:
    """Une fiche marquée supprimée n'est plus listée.

    Le marquage est posé ici par l'ORM : c'est une préparation de test, pas
    l'appel d'un service de suppression, qui n'existe pas encore.
    """
    visible = create_published_entity(name="Visible", slug="visible")
    supprimee = create_published_entity(name="Supprimée", slug="supprimee")
    supprimee.deleted_at = timezone.now()
    supprimee.save()

    response = client.get(reverse("entity-list"))

    slugs = [item["slug"] for item in response.json()]
    assert slugs == [visible.slug]


def test_detail_d_une_fiche_supprimee_renvoie_404(client: Client) -> None:
    """L'URL d'une fiche supprimée logiquement renvoie 404."""
    entity = create_published_entity()
    entity.deleted_at = timezone.now()
    entity.save()

    response = client.get(reverse("entity-detail", kwargs={"slug": entity.slug}))

    assert response.status_code == 404
    # La ligne existe toujours en base : seule la vue l'écarte.
    assert Entity.objects.filter(pk=entity.pk).exists()


def test_cible_imbriquee_supprimee_est_masquee(client: Client) -> None:
    """Une référence supprimée logiquement est masquée, pas exposée.

    C'est le renversement de la limite constatée à l'incrément précédent :
    `variant_of` devient `null` et le lien vers la cible supprimée disparaît
    entièrement.
    """
    reference = create_published_entity(name="Référence", slug="reference")
    cible = create_published_entity(name="Cible", slug="cible")
    entity = create_published_entity(name="Shango", slug="shango", variant_of=reference)
    create_relation(entity, RelationKind.PARENT, to_entity=cible)

    for supprimee in (reference, cible):
        supprimee.deleted_at = timezone.now()
        supprimee.save()

    response = client.get(reverse("entity-detail", kwargs={"slug": entity.slug}))

    payload = response.json()
    assert payload["variant_of"] is None
    assert payload["relations"] == []
    # Aucun fragment d'identité des cibles masquées ne filtre.
    brut = response.content.decode()
    assert "reference" not in brut
    assert "cible" not in brut


@pytest.mark.parametrize(
    "status",
    [EntityStatus.DRAFT, EntityStatus.SUBMITTED, EntityStatus.REJECTED],
)
def test_variante_non_publiee_est_masquee(client: Client, status: str) -> None:
    """`variant_of` vaut `null` si la référence n'est pas publiée.

    Le contenu de la fiche source reste public : seule la référence est
    masquée, sans révéler son identifiant, son slug, son nom ni son type.
    """
    reference = create_entity(
        name="Référence cachée", slug="reference-cachee", status=status
    )
    entity = create_published_entity(
        name="Shango",
        slug="shango",
        story_description="Public narrative.",
        variant_of=reference,
    )

    response = client.get(reverse("entity-detail", kwargs={"slug": entity.slug}))

    payload = response.json()
    assert payload["variant_of"] is None
    assert payload["story_description"] == "Public narrative."
    brut = response.content.decode()
    assert "reference-cachee" not in brut
    assert "Référence cachée" not in brut
    assert str(reference.pk) not in brut


def test_variante_publiee_est_exposee(client: Client) -> None:
    """Une référence publiée reste exposée en objet synthétique."""
    reference = create_published_entity(
        name="Mami Wata", slug="mami-wata", entity_type=EntityType.CREATURE
    )
    entity = create_published_entity(
        name="Mami Wata (Vodun)", slug="mami-wata-vodun", variant_of=reference
    )

    response = client.get(reverse("entity-detail", kwargs={"slug": entity.slug}))

    variante = response.json()["variant_of"]
    assert set(variante) == {"id", "slug", "name", "entity_type"}
    assert variante["slug"] == "mami-wata"
    # Aucune imbrication récursive du détail.
    assert "relations" not in variante
    assert "story_description" not in variante


def test_relations_melangees_seules_les_cibles_publiques_restent(
    client: Client,
) -> None:
    """Cible publique conservée, privée et supprimée omises, nom non résolu gardé.

    Vérifie le JSON brut, et non une simple longueur de liste.
    """
    source = create_published_entity(name="Shango", slug="shango")
    publique = create_published_entity(name="Oya", slug="oya")
    brouillon = create_entity(name="Brouillon", slug="brouillon")
    supprimee = create_published_entity(name="Supprimée", slug="supprimee")
    supprimee.deleted_at = timezone.now()
    supprimee.save()

    create_relation(source, RelationKind.CONSORT, to_entity=publique)
    create_relation(source, RelationKind.PARENT, to_entity=brouillon, notes="secret")
    create_relation(source, RelationKind.ENEMY, to_entity=supprimee, notes="secret")
    create_relation(source, RelationKind.ALLY, to_name="Figure sans fiche")

    response = client.get(reverse("entity-detail", kwargs={"slug": source.slug}))

    relations = response.json()["relations"]
    assert len(relations) == 2
    par_type = {r["kind"]: r for r in relations}
    assert par_type["consort"]["to_entity"]["slug"] == "oya"
    assert par_type["consort"]["to_name"] == ""
    # Le lien non résolu est conservé tel quel.
    assert par_type["ally"]["to_entity"] is None
    assert par_type["ally"]["to_name"] == "Figure sans fiche"

    brut = response.content.decode()
    for masque in ("brouillon", "Brouillon", "supprimee", "Supprimée", "secret"):
        assert masque not in brut
    # Les types des liens masqués n'apparaissent pas non plus.
    assert "parent" not in brut
    assert "enemy" not in brut


def test_une_cible_masquee_ne_bascule_pas_en_to_name(client: Client) -> None:
    """Un lien masqué n'est pas transformé en lien non résolu.

    Recopier le nom de la cible cachée dans `to_name` reviendrait à la
    republier sous une autre forme.
    """
    source = create_published_entity(name="Shango", slug="shango")
    cachee = create_entity(name="Cachée", slug="cachee", status=EntityStatus.SUBMITTED)
    create_relation(source, RelationKind.PARENT, to_entity=cachee)

    response = client.get(reverse("entity-detail", kwargs={"slug": source.slug}))

    assert response.json()["relations"] == []
    assert "Cachée" not in response.content.decode()


def test_to_name_homonyme_d_une_fiche_privee_est_conserve(client: Client) -> None:
    """Un `to_name` saisi reste exposé même si une fiche privée porte ce nom.

    Le lien est réellement non résolu : il n'est pas rapproché d'une fiche
    privée homonyme, ni masqué à cause d'elle.
    """
    create_entity(name="Yemaya", slug="yemaya")
    source = create_published_entity(name="Oya", slug="oya")
    create_relation(source, RelationKind.PARENT, to_name="Yemaya")

    response = client.get(reverse("entity-detail", kwargs={"slug": source.slug}))

    relation = response.json()["relations"][0]
    assert relation["to_entity"] is None
    assert relation["to_name"] == "Yemaya"


def test_detail_imbrique_le_profil_de_divinite(client: Client) -> None:
    """Le détail expose les champs communs et le profil quand il existe."""
    entity = create_published_entity(
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
    hero = published_hero()
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
    creature = published_creature()
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
    create_published_entity(
        name="Soundiata", slug="soundiata", entity_type=EntityType.HERO
    )

    response = client.get(reverse("entity-detail", kwargs={"slug": "soundiata"}))

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) >= PROFILE_KEYS
    assert all(payload[key] is None for key in PROFILE_KEYS)


def test_threat_level_absent_est_null(client: Client) -> None:
    """Un `threat_level` non renseigné est sérialisé en `null`, non en `""`."""
    creature = published_creature()
    create_creature_profile(creature)

    response = client.get(reverse("entity-detail", kwargs={"slug": creature.slug}))

    assert response.json()["creature_profile"]["threat_level"] is None


def test_detail_a_un_cout_constant_quel_que_soit_le_type(
    client: Client,
    django_assert_num_queries: Callable[[int], AbstractContextManager[None]],
) -> None:
    """Le détail coûte 7 requêtes pour chacun des trois types.

    Les trois profils, les trois ancrages principaux et la figure de
    référence sont joints à la requête de l'entité par `select_related` ; les
    six requêtes restantes sont celles des préchargements — quatre
    collections de référentiels, les relations sortantes et les sources — que
    Django exécute même lorsque les collections sont vides.

    Ce que le test protège : qu'aucun profil ne déclenche de requête
    supplémentaire, et que le coût ne dépende pas du type de l'entité.
    """
    divinity = create_published_entity()
    create_divinity_profile(divinity)
    hero = published_hero()
    create_hero_profile(hero)
    creature = published_creature()
    create_creature_profile(creature)

    for entity in (divinity, hero, creature):
        with django_assert_num_queries(7):
            client.get(reverse("entity-detail", kwargs={"slug": entity.slug}))


def test_detail_entierement_relie_ne_provoque_pas_de_n_plus_un(
    client: Client,
    django_assert_num_queries: Callable[[int], AbstractContextManager[None]],
) -> None:
    """Le détail d'une entité entièrement rattachée coûte 7 requêtes.

    Décompte : 1 requête pour l'entité, qui ramène par `select_related` les
    trois profils, les trois ancrages principaux et la figure de référence,
    puis 1 requête par collection préchargée — pays, ethnies et aires
    secondaires, domaines, relations sortantes et sources. Les trois
    relations coûtent une seule requête, leur cible étant jointe dans le
    `Prefetch` ; les deux sources en coûtent une également.

    Ce test fixe le budget global de requêtes du détail. À lui seul, il ne
    prouve pas le préchargement : une collection non préchargée demande aussi
    une seule requête pour cette unique entité, quel que soit son contenu.
    C'est `test_detail_precharge_se_serialise_sans_requete` qui apporte cette
    preuve.

    Les références documentaires employées ici sont fictives.
    """
    entity = entity_entierement_reliee()
    create_divinity_profile(entity)
    entity.variant_of = create_published_entity(name="Référence", slug="reference")
    entity.save()
    cible = create_published_entity(name="Oranyan", slug="oranyan")
    create_relation(entity, RelationKind.PARENT, to_entity=cible)
    create_relation(entity, RelationKind.CONSORT, to_entity=published_hero())
    create_relation(entity, RelationKind.ENEMY, to_name="Figure sans fiche")
    create_source(entity, label="Alpha Fictional Encyclopedia")
    create_source(entity, label="Zeta Fictional Review", kind=SourceKind.ARTICLE)

    with django_assert_num_queries(7):
        response = client.get(reverse("entity-detail", kwargs={"slug": entity.slug}))

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["relations"]) == 3
    assert len(payload["sources"]) == 2


def test_detail_precharge_se_serialise_sans_requete(
    django_assert_num_queries: Callable[[int], AbstractContextManager[None]],
) -> None:
    """Le queryset de la vue fournit toutes les données au serializer.

    Retirer un préchargement provoque une requête pendant la sérialisation,
    même si le budget global de l'endpoint reste identique. C'est donc ce
    test, et non le budget, qui prouve la présence de chaque préchargement.

    Le jeu couvre une figure de référence, deux relations résolues — dont les
    cibles doivent elles aussi être jointes —, une cible absente et plusieurs
    sources documentaires fictives.
    """
    entity = entity_entierement_reliee()
    create_divinity_profile(entity)
    entity.variant_of = create_published_entity(name="Référence", slug="reference")
    entity.save()
    create_relation(
        entity,
        RelationKind.PARENT,
        to_entity=create_published_entity(name="Oranyan", slug="oranyan"),
    )
    create_relation(entity, RelationKind.CONSORT, to_entity=published_hero())
    create_relation(entity, RelationKind.ENEMY, to_name="Figure sans fiche")
    create_source(entity, label="Alpha Fictional Encyclopedia")
    create_source(entity, label="Mu Fictional Museum Catalogue")
    create_source(entity, label="Zeta Fictional Review", kind=SourceKind.ARTICLE)

    view = EntityViewSet()
    view.action = "retrieve"
    loaded = view.get_queryset().get(pk=entity.pk)

    with django_assert_num_queries(0):
        payload = EntityDetailSerializer(loaded).data

    assert len(payload["secondary_countries"]) == 2
    assert len(payload["domains"]) == 2
    assert payload["variant_of"]["slug"] == "reference"
    assert len(payload["relations"]) == 3
    # Les noms des cibles résolues sont lus sans requête supplémentaire :
    # c'est ce que garantit le `select_related("to_entity")` du `Prefetch`.
    assert [
        relation["to_entity"]["name"]
        for relation in payload["relations"]
        if relation["to_entity"] is not None
    ] == ["Soundiata", "Oranyan"]
    assert [source["label"] for source in payload["sources"]] == [
        "Alpha Fictional Encyclopedia",
        "Mu Fictional Museum Catalogue",
        "Zeta Fictional Review",
    ]


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
    entity = create_published_entity()

    response = getattr(client, method)(
        reverse("entity-detail", kwargs={"slug": entity.slug})
    )

    assert response.status_code == 405
