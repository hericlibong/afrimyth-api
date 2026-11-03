"""Tests of `create_entity_with_profile`.

The existing factories are **not** replaced by the service: several tests
deliberately need entities without a profile, or invalid data, in order
to check limits. This module tests the service itself.

The data used is fictitious. Each test checks the **stored** state - after
`refresh_from_db()` or through a query - and not the in-memory object
alone, nor the presence of an `atomic` decorator.
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from mythology.models import (
    CreatureProfile,
    DivinityProfile,
    Entity,
    EntityStatus,
    EntityType,
    Gender,
    HeroProfile,
    ThreatLevel,
)
from mythology.services import create_entity_with_profile
from mythology.tests.factories import create_country, create_entity

pytestmark = pytest.mark.django_db


def entity_payload(**overrides: object) -> dict[str, object]:
    """Minimal valid payload for the common trunk."""
    data: dict[str, object] = {
        "name": "Shango",
        "slug": "shango",
        "entity_type": EntityType.DIVINITY,
        "gender": Gender.MALE,
    }
    data.update(overrides)
    return data


# --- Les trois types ----------------------------------------------------


def test_creation_d_une_divinite_et_de_son_seul_profil() -> None:
    """A divinity receives a `DivinityProfile`, and neither of the other two."""
    entity = create_entity_with_profile(
        entity_data=entity_payload(),
        profile_data={"cult_offerings": ["Yam"], "cult_taboos": ["Lying"]},
    )

    stored = Entity.objects.get(pk=entity.pk)

    assert stored.entity_type == EntityType.DIVINITY
    assert stored.divinity_profile.cult_offerings == ["Yam"]
    assert stored.divinity_profile.cult_taboos == ["Lying"]
    assert not hasattr(stored, "hero_profile")
    assert not hasattr(stored, "creature_profile")
    assert DivinityProfile.objects.count() == 1
    assert HeroProfile.objects.count() == 0
    assert CreatureProfile.objects.count() == 0


def test_creation_d_un_heros_et_de_son_seul_profil() -> None:
    """A hero receives a `HeroProfile`, and neither of the other two."""
    entity = create_entity_with_profile(
        entity_data=entity_payload(
            name="Soundiata", slug="soundiata", entity_type=EntityType.HERO
        ),
        profile_data={"titles": ["King of Mali"], "legacy": "Founded the empire."},
    )

    stored = Entity.objects.get(pk=entity.pk)

    assert stored.entity_type == EntityType.HERO
    assert stored.hero_profile.titles == ["King of Mali"]
    assert stored.hero_profile.legacy == "Founded the empire."
    assert not hasattr(stored, "divinity_profile")
    assert not hasattr(stored, "creature_profile")
    assert HeroProfile.objects.count() == 1


def test_creation_d_une_creature_et_de_son_seul_profil() -> None:
    """A creature receives a `CreatureProfile`, and neither of the other two."""
    entity = create_entity_with_profile(
        entity_data=entity_payload(
            name="Mokele-mbembe",
            slug="mokele-mbembe",
            entity_type=EntityType.CREATURE,
            gender=Gender.NEUTRAL,
        ),
        profile_data={"habitat": ["Swamps"], "threat_level": ThreatLevel.HIGH},
    )

    stored = Entity.objects.get(pk=entity.pk)

    assert stored.entity_type == EntityType.CREATURE
    assert stored.creature_profile.habitat == ["Swamps"]
    assert stored.creature_profile.threat_level == ThreatLevel.HIGH
    assert not hasattr(stored, "divinity_profile")
    assert not hasattr(stored, "hero_profile")
    assert CreatureProfile.objects.count() == 1


# --- Données conservées -------------------------------------------------


def test_les_donnees_du_tronc_commun_sont_conservees() -> None:
    """The simple fields and the foreign keys do reach the database."""
    country = create_country()
    entity = create_entity_with_profile(
        entity_data=entity_payload(
            category="Orisha of Lightning",
            cultural_role="Thunder deity",
            story_description="Fictional narrative for tests.",
            symbols=["Double-headed axe"],
            primary_country=country,
        ),
    )

    stored = Entity.objects.get(pk=entity.pk)

    assert stored.category == "Orisha of Lightning"
    assert stored.cultural_role == "Thunder deity"
    assert stored.story_description == "Fictional narrative for tests."
    assert stored.symbols == ["Double-headed axe"]
    assert stored.primary_country == country


def test_cle_etrangere_acceptee_sous_sa_forme_id() -> None:
    """`primary_country_id` is accepted, a form that is useful to the import."""
    country = create_country()

    entity = create_entity_with_profile(
        entity_data=entity_payload(primary_country_id=country.pk),
    )

    assert Entity.objects.get(pk=entity.pk).primary_country == country


def test_statut_par_defaut_reste_draft() -> None:
    """The service publishes nothing and assigns no owner."""
    entity = create_entity_with_profile(entity_data=entity_payload())

    stored = Entity.objects.get(pk=entity.pk)

    assert stored.status == EntityStatus.DRAFT
    assert stored.created_by is None
    assert stored.submitted_at is None


# --- Profil absent ou vide ----------------------------------------------


def test_profil_absent_cree_un_profil_par_defaut() -> None:
    """Without `profile_data`, the profile exists with its default values.

    The important point: never an entity **without** a profile.
    """
    entity = create_entity_with_profile(entity_data=entity_payload())

    stored = Entity.objects.get(pk=entity.pk)

    assert stored.divinity_profile.cult_offerings == []
    assert stored.divinity_profile.cult_festivals == []


def test_profil_vide_cree_un_profil_par_defaut() -> None:
    """An empty dictionary is treated as an absence."""
    entity = create_entity_with_profile(
        entity_data=entity_payload(entity_type=EntityType.CREATURE),
        profile_data={},
    )

    stored = Entity.objects.get(pk=entity.pk)

    assert stored.creature_profile.habitat == []
    assert stored.creature_profile.threat_level is None


# --- Type absent ou inconnu ---------------------------------------------


def test_type_absent_est_refuse() -> None:
    """Without a type, no profile can be chosen: nothing is created."""
    data = entity_payload()
    del data["entity_type"]

    with pytest.raises(ValidationError) as excinfo:
        create_entity_with_profile(entity_data=data)

    assert "entity_type" in excinfo.value.message_dict
    assert Entity.objects.count() == 0


def test_type_vide_est_refuse() -> None:
    """An empty string is treated as a missing type."""
    with pytest.raises(ValidationError) as excinfo:
        create_entity_with_profile(entity_data=entity_payload(entity_type=""))

    assert "entity_type" in excinfo.value.message_dict
    assert Entity.objects.count() == 0


def test_type_inconnu_est_refuse() -> None:
    """A type outside the three values is refused before any write."""
    with pytest.raises(ValidationError) as excinfo:
        create_entity_with_profile(entity_data=entity_payload(entity_type="titan"))

    assert "entity_type" in excinfo.value.message_dict
    assert Entity.objects.count() == 0


# --- Champs refusés -----------------------------------------------------


def test_champ_de_profil_incompatible_est_refuse() -> None:
    """A field of another profile does not pass, and nothing is created.

    `habitat` belongs to the creature profile: asking for it on a divinity is
    a call error, not a value to ignore.
    """
    with pytest.raises(ValidationError) as excinfo:
        create_entity_with_profile(
            entity_data=entity_payload(),
            profile_data={"habitat": ["Swamps"]},
        )

    assert "habitat" in str(excinfo.value)
    assert Entity.objects.count() == 0
    assert DivinityProfile.objects.count() == 0


def test_champ_d_entite_inconnu_est_refuse() -> None:
    """A non-existent field is reported rather than partially written."""
    with pytest.raises(ValidationError) as excinfo:
        create_entity_with_profile(entity_data=entity_payload(pantheon="Orisha"))

    assert "pantheon" in str(excinfo.value)
    assert Entity.objects.count() == 0


@pytest.mark.parametrize(
    "champ",
    [
        "secondary_countries",
        "secondary_ethnicities",
        "secondary_cultural_areas",
        "domains",
        "sources",
        "relations_from",
    ],
)
def test_collections_hors_perimetre_sont_refusees(champ: str) -> None:
    """Many-to-many relations are explicitly out of scope.

    They require an already saved entity: the import attaches them after the
    call, without compromising the atomicity of the entity/profile pair.
    """
    with pytest.raises(ValidationError) as excinfo:
        create_entity_with_profile(entity_data=entity_payload(**{champ: []}))

    assert champ in excinfo.value.message_dict
    assert Entity.objects.count() == 0


@pytest.mark.parametrize("champ", ["id", "pk"])
def test_identifiant_impose_est_refuse(champ: str) -> None:
    """A supplied identifier is refused: the function creates, it does not overwrite."""
    with pytest.raises(ValidationError) as excinfo:
        create_entity_with_profile(entity_data=entity_payload(**{champ: 1}))

    assert champ in excinfo.value.message_dict
    assert Entity.objects.count() == 0


def test_identifiant_existant_ne_peut_pas_ecraser_une_fiche() -> None:
    """Reusing the `id` of an existing record does not overwrite it."""
    existante = create_entity(name="Existante", slug="existante")

    with pytest.raises(ValidationError):
        create_entity_with_profile(entity_data=entity_payload(id=existante.pk))

    existante.refresh_from_db()
    assert existante.name == "Existante"
    assert Entity.objects.count() == 1


@pytest.mark.parametrize("champ", ["entity", "entity_id"])
def test_rattachement_du_profil_ne_peut_pas_etre_detourne(champ: str) -> None:
    """The profile is attached to the created entity, never to another one."""
    autre = create_entity(name="Autre", slug="autre")

    with pytest.raises(ValidationError) as excinfo:
        create_entity_with_profile(
            entity_data=entity_payload(),
            profile_data={champ: autre.pk if champ == "entity_id" else autre},
        )

    assert champ in excinfo.value.message_dict
    assert DivinityProfile.objects.count() == 0
    assert Entity.objects.count() == 1


# --- Atomicité ----------------------------------------------------------


def test_echec_du_profil_n_laisse_aucun_residu() -> None:
    """If the profile fails after the entity, both creations are rolled back.

    This is the heart of the guarantee: an invalid `threat_level` is caught by
    the `full_clean()` of the profile, hence **after** the entity has been
    saved. Without a transaction, an orphan entity would remain.
    """
    with pytest.raises(ValidationError):
        create_entity_with_profile(
            entity_data=entity_payload(
                name="Mokele-mbembe",
                slug="mokele-mbembe",
                entity_type=EntityType.CREATURE,
            ),
            profile_data={"threat_level": "apocalyptic"},
        )

    assert Entity.objects.count() == 0
    assert CreatureProfile.objects.count() == 0


def test_echec_preserve_les_donnees_prealables() -> None:
    """A failure does not touch the records already in the database."""
    existante = create_entity(name="Existante", slug="existante")

    with pytest.raises(ValidationError):
        create_entity_with_profile(
            entity_data=entity_payload(entity_type=EntityType.CREATURE),
            profile_data={"threat_level": "apocalyptic"},
        )

    assert [e.slug for e in Entity.objects.all()] == [existante.slug]


def test_entite_invalide_ne_cree_ni_entite_ni_profil() -> None:
    """A failure on the entity itself writes nothing either."""
    with pytest.raises(ValidationError):
        create_entity_with_profile(entity_data=entity_payload(gender="plasma"))

    assert Entity.objects.count() == 0
    assert DivinityProfile.objects.count() == 0


# --- Contraintes d'unicité ---------------------------------------------


def test_slug_duplique_est_refuse() -> None:
    """Slug uniqueness is still enforced, and nothing remains."""
    create_entity_with_profile(entity_data=entity_payload())

    with pytest.raises(ValidationError):
        create_entity_with_profile(entity_data=entity_payload(name="Autre nom"))

    assert Entity.objects.count() == 1
    assert DivinityProfile.objects.count() == 1


def test_couple_nom_type_duplique_est_refuse() -> None:
    """The `(name, entity_type)` constraint is still enforced."""
    create_entity_with_profile(entity_data=entity_payload())

    with pytest.raises(ValidationError):
        create_entity_with_profile(entity_data=entity_payload(slug="shango-2"))

    assert Entity.objects.count() == 1


def test_meme_nom_sous_deux_types_reste_possible() -> None:
    """The constraint bears on the pair, not on the name alone."""
    create_entity_with_profile(entity_data=entity_payload())
    create_entity_with_profile(
        entity_data=entity_payload(
            slug="shango-creature",
            entity_type=EntityType.CREATURE,
        )
    )

    assert Entity.objects.filter(name="Shango").count() == 2


# --- Entrées de l'appelant ---------------------------------------------


def test_les_dictionnaires_fournis_ne_sont_pas_modifies() -> None:
    """The service does not mutate the data of the caller."""
    entity_data = entity_payload()
    profile_data: dict[str, object] = {"cult_offerings": ["Yam"]}
    attendu_entite = dict(entity_data)
    attendu_profil = dict(profile_data)

    create_entity_with_profile(entity_data=entity_data, profile_data=profile_data)

    assert entity_data == attendu_entite
    assert profile_data == attendu_profil


# --- Portée de la garantie ---------------------------------------------


def test_l_orm_direct_contourne_encore_le_service() -> None:
    """Document the limit: the service covers its own calls only.

    A direct `objects.create()` - as the admin or a badly written import does
    - still produces an entity without a profile. Covering those paths
    belongs to phase 4; this test pins the real state down so that it is not
    mistaken for a global guarantee.
    """
    orpheline = Entity.objects.create(
        name="Orpheline",
        slug="orpheline",
        entity_type=EntityType.DIVINITY,
        gender=Gender.MALE,
    )

    assert not hasattr(orpheline, "divinity_profile")
    assert DivinityProfile.objects.count() == 0


def test_le_type_peut_encore_changer_apres_creation() -> None:
    """Another limit: the service does not lock `entity_type`.

    After creation, changing the type leaves the original profile in place.
    Consistency over time is not guaranteed by this function.
    """
    entity = create_entity_with_profile(entity_data=entity_payload())

    entity.entity_type = EntityType.HERO
    entity.save()
    stored = Entity.objects.get(pk=entity.pk)

    assert stored.entity_type == EntityType.HERO
    # Le profil de divinité subsiste, désormais incohérent avec le type.
    assert hasattr(stored, "divinity_profile")
    assert not hasattr(stored, "hero_profile")


def test_un_second_profil_reste_impossible_par_le_onetoone() -> None:
    """The `OneToOneField` prevents a second profile of the same type."""
    entity = create_entity_with_profile(entity_data=entity_payload())

    with pytest.raises(IntegrityError), transaction.atomic():
        DivinityProfile.objects.create(entity=entity)
