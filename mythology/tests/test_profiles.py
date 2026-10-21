"""Tests des profils `HeroProfile` et `CreatureProfile`.

Le profil de divinité est couvert par `test_models.py` ; ce module ajoute les
deux profils de la phase 2 et vérifie que les trois cohabitent sans régression.
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
    """Le profil de héros est relié à son entité dans les deux sens."""
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
    """Les quatre listes sont vides et les deux textes sont des chaînes vides."""
    profile = create_hero_profile(create_hero())

    assert profile.titles == []
    assert profile.achievements == []
    assert profile.quests == []
    assert profile.weapons_or_artifacts == []
    assert profile.legacy == ""
    assert profile.historical_context == ""


def test_creation_d_un_profil_de_creature() -> None:
    """Le profil de créature est relié à son entité dans les deux sens."""
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
    """Les sept listes sont vides et `threat_level` est `None` à la création.

    `None` est bien le défaut d'un champ nullable sans `default` explicite ;
    cela ne dit rien d'une valeur `""` fournie explicitement.
    """
    profile = create_creature_profile(create_creature())

    assert profile.habitat == []
    assert profile.known_sightings == []
    assert profile.diet == ""
    assert profile.appearance_notes == ""
    assert profile.threat_level is None


def test_champ_de_formulaire_de_threat_level_utilise_none_comme_valeur_vide() -> None:
    """Le champ de **formulaire** de `threat_level` a `empty_value=None`.

    Portée exacte de ce test : Django impose `empty_value=None` au formulaire
    d'un champ à `choices` nullable, donc un choix laissé vide dans un
    formulaire ou dans l'administration est enregistré `NULL`.

    Ce n'est **pas** une garantie générale de la base : un appel ORM direct ou
    un futur serializer d'écriture peut encore stocker `""`. L'API étant en
    lecture seule, ce cas n'est pas exposé aujourd'hui ; la normalisation de
    `""` vers `None` sera imposée dans les serializers ou services d'écriture
    de la phase 4.
    """
    form_field = CreatureProfile._meta.get_field("threat_level").formfield()

    assert isinstance(form_field, forms.TypedChoiceField)
    assert form_field.empty_value is None


def test_profil_de_heros_refuse_une_divinite() -> None:
    """La validation rejette un profil de héros sur une divinité."""
    divinity = create_entity()

    with pytest.raises(ValidationError) as excinfo:
        HeroProfile(entity=divinity).full_clean()

    assert "entity" in excinfo.value.message_dict


def test_profil_de_creature_refuse_un_heros() -> None:
    """La validation rejette un profil de créature sur un héros."""
    hero = create_hero()

    with pytest.raises(ValidationError) as excinfo:
        CreatureProfile(entity=hero).full_clean()

    assert "entity" in excinfo.value.message_dict


def test_profils_acceptent_leur_propre_type() -> None:
    """La même validation laisse passer le type attendu."""
    HeroProfile(entity=create_hero()).full_clean()
    CreatureProfile(entity=create_creature()).full_clean()


def test_un_seul_profil_de_heros_par_entite() -> None:
    """Le `OneToOneField` interdit un second profil sur la même entité."""
    hero = create_hero()
    create_hero_profile(hero)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_hero_profile(hero)


def test_un_seul_profil_de_creature_par_entite() -> None:
    """Le `OneToOneField` interdit un second profil sur la même entité."""
    creature = create_creature()
    create_creature_profile(creature)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_creature_profile(creature)


def test_suppression_de_l_entite_supprime_les_profils() -> None:
    """Le `CASCADE` emporte le profil de héros comme celui de créature."""
    hero = create_hero()
    create_hero_profile(hero)
    creature = create_creature()
    create_creature_profile(creature)

    hero.delete()
    creature.delete()

    assert HeroProfile.objects.count() == 0
    assert CreatureProfile.objects.count() == 0
