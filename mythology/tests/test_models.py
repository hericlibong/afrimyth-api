import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from mythology.models import DivinityProfile, Entity, EntityType
from mythology.tests.factories import create_divinity_profile, create_entity

pytestmark = pytest.mark.django_db


def test_creation_d_une_divinite_et_de_son_profil() -> None:
    """Une divinité et son profil sont reliés dans les deux sens."""
    entity = create_entity(
        name="Shango",
        slug="shango",
        category="Orisha of Lightning",
        cultural_role="Dieu du tonnerre",
        symbols=["Hache à double tranchant"],
    )
    profile = create_divinity_profile(
        entity,
        cult_offerings=["Igname", "Rhum"],
        cult_taboos=["Mensonge"],
    )

    entity.refresh_from_db()

    assert entity.entity_type == EntityType.DIVINITY
    assert entity.divinity_profile == profile
    assert profile.entity == entity
    assert profile.cult_offerings == ["Igname", "Rhum"]
    assert profile.cult_rituals == []
    assert str(profile) == "Profil de divinité — Shango"


def test_uuid_est_la_cle_primaire() -> None:
    """La clé primaire est un UUID généré automatiquement."""
    entity = create_entity()

    assert entity.pk is not None
    assert entity.id == entity.pk
    assert Entity._meta.pk is not None
    assert Entity._meta.pk.name == "id"


def test_profil_refuse_une_entite_d_un_autre_type() -> None:
    """La validation rejette un profil de divinité sur un héros."""
    hero = create_entity(
        name="Soundiata", slug="soundiata", entity_type=EntityType.HERO
    )
    profile = DivinityProfile(entity=hero)

    with pytest.raises(ValidationError) as excinfo:
        profile.full_clean()

    assert "entity" in excinfo.value.message_dict


def test_profil_accepte_une_divinite() -> None:
    """La même validation laisse passer une entité de type `divinity`."""
    entity = create_entity()

    DivinityProfile(entity=entity).full_clean()


def test_nom_unique_par_type() -> None:
    """Deux entités de même type ne peuvent pas porter le même nom."""
    create_entity(name="Mami Wata", slug="mami-wata")

    with pytest.raises(IntegrityError), transaction.atomic():
        create_entity(name="Mami Wata", slug="mami-wata-bis")


def test_meme_nom_autorise_pour_deux_types_differents() -> None:
    """La contrainte porte sur le couple, pas sur le nom seul."""
    create_entity(name="Mami Wata", slug="mami-wata")
    create_entity(
        name="Mami Wata",
        slug="mami-wata-creature",
        entity_type=EntityType.CREATURE,
    )

    assert Entity.objects.filter(name="Mami Wata").count() == 2


def test_suppression_de_l_entite_supprime_le_profil() -> None:
    """Le `CASCADE` du `OneToOneField` emporte le profil."""
    entity = create_entity()
    create_divinity_profile(entity)

    entity.delete()

    assert DivinityProfile.objects.count() == 0
