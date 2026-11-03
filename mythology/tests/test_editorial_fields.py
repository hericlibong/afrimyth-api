"""Tests of the platform fields of `Entity` and of the two managers.

Those fields are **declared, not driven**: no transition, no service and
no permission exists yet. The tests below therefore check the schema, the
default values, the validation of choices and the scope of the managers -
not a workflow. Marking `deleted_at` here is an explicit preparation made
through the ORM, not a call to a business service.
"""

import datetime

import pytest
from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.db import models
from django.test import RequestFactory
from django.utils import timezone

from accounts.models import User
from mythology.admin import EntityAdmin
from mythology.models import Entity, EntityStatus
from mythology.tests.factories import create_entity

pytestmark = pytest.mark.django_db


def create_user(username: str = "contributor") -> User:
    """Create a test account, with no group or role - those come in phase 4."""
    return User.objects.create_user(username=username, password="test-password")


# --- Valeurs par défaut et statuts --------------------------------------


def test_valeurs_par_defaut_des_champs_de_plateforme() -> None:
    """A record is born in `draft`, with no owner and no review trace."""
    entity = create_entity()

    entity.refresh_from_db()

    assert entity.status == EntityStatus.DRAFT
    assert entity.created_by is None
    assert entity.submitted_at is None
    assert entity.reviewed_at is None
    assert entity.reviewed_by is None
    assert entity.review_notes == ""
    assert entity.deleted_at is None
    assert entity.deleted_by is None


@pytest.mark.parametrize("status", EntityStatus.values)
def test_les_quatre_statuts_sont_acceptes(status: str) -> None:
    """The four intended values pass `full_clean()`."""
    entity = create_entity(status=status)

    entity.full_clean()

    assert entity.status == status


def test_statut_inconnu_refuse_par_full_clean() -> None:
    """A status outside the list is rejected by Django validation.

    Exact scope: `full_clean()` only. No PostgreSQL constraint limits the
    values of `status` - a direct create with an unknown status would be
    accepted by the database, which the next test pins down.
    """
    entity = create_entity(status="archived")

    with pytest.raises(ValidationError) as excinfo:
        entity.full_clean()

    assert "status" in excinfo.value.message_dict


def test_statut_inconnu_passe_en_ecriture_directe() -> None:
    """Document the limit: the database does not enumerate the statuses.

    This test pins the real behaviour down rather than letting a structural
    guarantee be assumed.
    """
    entity = create_entity(status="archived")

    entity.refresh_from_db()

    assert entity.status == "archived"


def test_aucun_statut_deleted() -> None:
    """Logical deletion is not an editorial status.

    A deleted record keeps the state it had: the two notions are carried
    separately.
    """
    assert "deleted" not in EntityStatus.values
    assert EntityStatus.values == ["draft", "submitted", "published", "rejected"]


# --- Attribution explicite des acteurs ----------------------------------


def test_attribution_explicite_des_trois_acteurs() -> None:
    """The three actors, timestamps and notes are set explicitly.

    Nothing is filled in automatically: the test supplies every value, as the
    phase 4 services will.
    """
    auteur = create_user("author")
    relecteur = create_user("reviewer")
    soumis_le = timezone.now() - datetime.timedelta(days=2)
    revu_le = timezone.now()

    entity = create_entity(
        created_by=auteur,
        status=EntityStatus.PUBLISHED,
        submitted_at=soumis_le,
        reviewed_at=revu_le,
        reviewed_by=relecteur,
        review_notes="Reviewed for demonstration purposes.",
    )

    entity.refresh_from_db()

    assert entity.created_by == auteur
    assert entity.reviewed_by == relecteur
    assert entity.submitted_at == soumis_le
    assert entity.reviewed_at == revu_le
    assert entity.review_notes == "Reviewed for demonstration purposes."
    assert entity.status == EntityStatus.PUBLISHED


def test_related_names_distincts_pour_les_trois_acteurs() -> None:
    """The three user relations are declared and readable separately.

    Two complementary checks: the reverse accessors exist and are distinct -
    otherwise Django would refuse the model - and each one does find the
    expected record.
    """
    utilisateur = create_user()
    create_entity(name="A", slug="a", created_by=utilisateur)
    create_entity(name="B", slug="b", reviewed_by=utilisateur)
    create_entity(name="C", slug="c", deleted_by=utilisateur)

    accesseurs = {
        relation.get_accessor_name()
        for relation in User._meta.related_objects
        if relation.related_model is Entity
    }
    assert accesseurs == {
        "created_entities",
        "reviewed_entities",
        "deleted_entities",
    }

    assert [e.slug for e in Entity.objects.filter(created_by=utilisateur)] == ["a"]
    assert [e.slug for e in Entity.objects.filter(reviewed_by=utilisateur)] == ["b"]
    assert [e.slug for e in Entity.objects.filter(deleted_by=utilisateur)] == ["c"]


def test_aucun_horodatage_metier_n_est_rempli_automatiquement() -> None:
    """Creating then saving a record sets no business date."""
    entity = create_entity()
    entity.status = EntityStatus.SUBMITTED
    entity.save()

    entity.refresh_from_db()

    assert entity.status == EntityStatus.SUBMITTED
    # Changer le statut ne déclenche aucune machine à états.
    assert entity.submitted_at is None
    assert entity.reviewed_at is None


def test_suppression_d_un_utilisateur_conserve_la_fiche() -> None:
    """`SET_NULL`: deleting an account empties the FKs without touching the record.

    A historical date can therefore survive with an actor that became null,
    which is exactly why no constraint ties actor, date and status together.
    """
    utilisateur = create_user()
    revu_le = timezone.now()
    entity = create_entity(
        created_by=utilisateur,
        reviewed_by=utilisateur,
        deleted_by=utilisateur,
        reviewed_at=revu_le,
    )

    utilisateur.delete()
    entity.refresh_from_db()

    assert Entity.objects.filter(pk=entity.pk).exists()
    assert entity.created_by is None
    assert entity.reviewed_by is None
    assert entity.deleted_by is None
    # La trace temporelle survit à la disparition de l'acteur.
    assert entity.reviewed_at == revu_le


# --- Managers -----------------------------------------------------------


def test_manager_par_defaut_est_complet() -> None:
    """`objects`, declared first, is the default manager.

    A consequence intended by ADR 0002: neither the admin, nor the traversal
    of relations, nor a future restoration silently hides rows.
    """
    assert isinstance(Entity._default_manager, models.Manager)
    assert Entity._default_manager.name == "objects"


def test_objects_voit_les_fiches_supprimees() -> None:
    """The full manager includes logically deleted rows."""
    create_entity(name="Visible", slug="visible")
    supprimee = create_entity(name="Supprimée", slug="supprimee")
    supprimee.deleted_at = timezone.now()
    supprimee.save()

    assert Entity.objects.count() == 2


def test_active_exclut_uniquement_les_fiches_supprimees() -> None:
    """`active` filtre `deleted_at`, et rien d'autre."""
    create_entity(name="Visible", slug="visible")
    supprimee = create_entity(name="Supprimée", slug="supprimee")
    supprimee.deleted_at = timezone.now()
    supprimee.save()

    assert [e.slug for e in Entity.active.all()] == ["visible"]


@pytest.mark.parametrize("status", EntityStatus.values)
def test_active_ne_depend_pas_du_statut(status: str) -> None:
    """An active record stays visible to the manager whatever its status.

    Filtering on `published` belongs to phase 3; `active` bears on logical
    deletion only.
    """
    create_entity(status=status)

    assert Entity.active.count() == 1


def test_active_ignore_la_valeur_de_deleted_by() -> None:
    """Only `deleted_at` counts: `deleted_by` alone hides nothing."""
    entity = create_entity()
    entity.deleted_by = create_user()
    entity.save()

    assert Entity.active.count() == 1


# --- Administration -----------------------------------------------------


def test_administration_voit_les_fiches_supprimees() -> None:
    """The queryset of `EntityAdmin` keeps the deleted rows.

    That is the condition for a restoration to be possible in phase 4.
    """
    visible = create_entity(name="Visible", slug="visible")
    supprimee = create_entity(name="Supprimée", slug="supprimee")
    supprimee.deleted_at = timezone.now()
    supprimee.save()

    admin = EntityAdmin(Entity, AdminSite())
    requete = RequestFactory().get("/admin/mythology/entity/")
    requete.user = create_user("staff")

    slugs = sorted(e.slug for e in admin.get_queryset(requete))

    assert slugs == sorted([visible.slug, supprimee.slug])
    # Contraste explicite : la vue publique, elle, ne verrait que la première.
    assert [e.slug for e in Entity.active.all()] == [visible.slug]


def test_champs_en_lecture_seule_de_l_administration() -> None:
    """The workflow timestamps and `deleted_by` cannot be entered."""
    admin = EntityAdmin(Entity, AdminSite())

    assert "submitted_at" in admin.readonly_fields
    assert "reviewed_at" in admin.readonly_fields
    assert "deleted_at" in admin.readonly_fields
    assert "deleted_by" in admin.readonly_fields
    # Restent modifiables pour préparer des jeux de test.
    assert "status" not in admin.readonly_fields
    assert "created_by" not in admin.readonly_fields
