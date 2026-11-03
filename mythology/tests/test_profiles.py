"""Tests of the `HeroProfile` and `CreatureProfile` profiles.

The divinity profile is covered by `test_models.py`; this module adds the
two profiles of phase 2 and checks that the three coexist without
regression.
"""

import pytest
from django import forms
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from mythology.models import CreatureProfile, HeroProfile, ThreatLevel
from mythology.tests.factories import (
    create_creature,
    create_creature_profile,
    create_entity,
    create_hero,
    create_hero_profile,
)

pytestmark = pytest.mark.django_db


def test_creation_d_un_profil_de_heros() -> None:
    """The hero profile is linked to its entity both ways."""
    hero = create_hero()
    profile = create_hero_profile(
        hero,
        titles=["Roi du Mali"],
        achievements=["Victoire de Kirina"],
        quests=["Unifier le Manden"],
        weapons_or_artifacts=["Arc de Soundiata"],
        legacy="Fondateur de l'empire du Mali.",
        historical_context="XIIIe siècle.",
    )

    hero.refresh_from_db()

    assert hero.hero_profile == profile
    assert profile.entity == hero
    assert profile.titles == ["Roi du Mali"]
    assert profile.legacy == "Fondateur de l'empire du Mali."
    assert str(profile) == "Hero profile — Soundiata"


def test_profil_de_heros_vide_par_defaut() -> None:
    """The four lists are empty and the two texts are empty strings."""
    profile = create_hero_profile(create_hero())

    assert profile.titles == []
    assert profile.achievements == []
    assert profile.quests == []
    assert profile.weapons_or_artifacts == []
    assert profile.legacy == ""
    assert profile.historical_context == ""


def test_creation_d_un_profil_de_creature() -> None:
    """The creature profile is linked to its entity both ways."""
    creature = create_creature()
    profile = create_creature_profile(
        creature,
        habitat=["Marais du bassin du Congo"],
        powers=["Renverser les pirogues"],
        strengths=["Force colossale"],
        weaknesses=["Lenteur"],
        encounter_omens=["Eaux troubles"],
        encounter_rules=["Ne pas prononcer son nom"],
        known_sightings=["Lac Télé, 1776"],
        diet="Herbivore",
        size="Gigantesque",
        appearance_notes="Long cou et queue puissante.",
        threat_level=ThreatLevel.HIGH,
    )

    creature.refresh_from_db()

    assert creature.creature_profile == profile
    assert profile.entity == creature
    assert profile.habitat == ["Marais du bassin du Congo"]
    assert profile.threat_level == ThreatLevel.HIGH
    assert str(profile) == "Creature profile — Mokele-mbembe"


def test_profil_de_creature_vide_par_defaut() -> None:
    """The seven lists are empty and `threat_level` is `None` on creation.

    `None` is indeed the default of a nullable field without an explicit
    `default`; this says nothing about an empty string supplied explicitly.
    """
    profile = create_creature_profile(create_creature())

    assert profile.habitat == []
    assert profile.known_sightings == []
    assert profile.diet == ""
    assert profile.appearance_notes == ""
    assert profile.threat_level is None


def test_champ_de_formulaire_de_threat_level_utilise_none_comme_valeur_vide() -> None:
    """The **form** field of `threat_level` has `empty_value=None`.

    Exact scope of this test: Django imposes `empty_value=None` on the form of
    a nullable field with `choices`, so a choice left blank in a form or in
    the admin is stored as `NULL`.

    This is **not** a general database guarantee: a direct ORM call or a
    future write serializer can still store an empty string. Since the API is
    read-only, that case is not exposed today; normalising an empty string to
    `None` will be imposed in the write serializers or services of phase 4.
    """
    form_field = CreatureProfile._meta.get_field("threat_level").formfield()

    assert isinstance(form_field, forms.TypedChoiceField)
    assert form_field.empty_value is None


def test_profil_de_heros_refuse_une_divinite() -> None:
    """Validation rejects a hero profile on a divinity."""
    divinity = create_entity()

    with pytest.raises(ValidationError) as excinfo:
        HeroProfile(entity=divinity).full_clean()

    assert "entity" in excinfo.value.message_dict


def test_profil_de_creature_refuse_un_heros() -> None:
    """Validation rejects a creature profile on a hero."""
    hero = create_hero()

    with pytest.raises(ValidationError) as excinfo:
        CreatureProfile(entity=hero).full_clean()

    assert "entity" in excinfo.value.message_dict


def test_profils_acceptent_leur_propre_type() -> None:
    """The same validation lets the expected type through."""
    HeroProfile(entity=create_hero()).full_clean()
    CreatureProfile(entity=create_creature()).full_clean()


def test_un_seul_profil_de_heros_par_entite() -> None:
    """The `OneToOneField` forbids a second profile on the same entity."""
    hero = create_hero()
    create_hero_profile(hero)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_hero_profile(hero)


def test_un_seul_profil_de_creature_par_entite() -> None:
    """The `OneToOneField` forbids a second profile on the same entity."""
    creature = create_creature()
    create_creature_profile(creature)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_creature_profile(creature)


def test_suppression_de_l_entite_supprime_les_profils() -> None:
    """The `CASCADE` takes the hero profile as well as the creature one."""
    hero = create_hero()
    create_hero_profile(hero)
    creature = create_creature()
    create_creature_profile(creature)

    hero.delete()
    creature.delete()

    assert HeroProfile.objects.count() == 0
    assert CreatureProfile.objects.count() == 0
