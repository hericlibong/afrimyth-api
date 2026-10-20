"""Tests des champs de plateforme de `Entity` et des deux managers.

Ces champs sont **posés, non pilotés** : aucune transition, aucun service,
aucune permission n'existe encore. Les tests ci-dessous vérifient donc le
schéma, les valeurs par défaut, la validation des choix et la portée des
managers — pas un workflow. Le marquage de `deleted_at` y est une préparation
explicite par l'ORM, pas l'appel d'un service métier.
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
    """Crée un compte de test, sans groupe ni rôle — ceux-ci viendront en phase 4."""
    return User.objects.create_user(username=username, password="test-password")


# --- Valeurs par défaut et statuts --------------------------------------


def test_valeurs_par_defaut_des_champs_de_plateforme() -> None:
    """Une fiche naît en `draft`, sans propriétaire ni trace de revue."""
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
    """Les quatre valeurs prévues passent `full_clean()`."""
    entity = create_entity(status=status)

    entity.full_clean()

    assert entity.status == status


def test_statut_inconnu_refuse_par_full_clean() -> None:
    """Un statut hors liste est rejeté par la validation Django.

    Portée exacte : `full_clean()` seulement. Aucune contrainte PostgreSQL ne
    limite les valeurs de `status` — `objects.create(status="archived")`
    serait accepté en base, ce que fixe le test suivant.
    """
    entity = create_entity(status="archived")

    with pytest.raises(ValidationError) as excinfo:
        entity.full_clean()

    assert "status" in excinfo.value.message_dict


def test_statut_inconnu_passe_en_ecriture_directe() -> None:
    """Documente la limite : la base n'énumère pas les statuts.

    Ce test fixe le comportement réel plutôt que de laisser croire à une
    garantie structurelle.
    """
    entity = create_entity(status="archived")

    entity.refresh_from_db()

    assert entity.status == "archived"


def test_aucun_statut_deleted() -> None:
    """La suppression logique n'est pas un statut éditorial.

    Une fiche supprimée conserve l'état qu'elle avait : les deux notions sont
    portées séparément.
    """
    assert "deleted" not in EntityStatus.values
    assert EntityStatus.values == ["draft", "submitted", "published", "rejected"]


# --- Attribution explicite des acteurs ----------------------------------


def test_attribution_explicite_des_trois_acteurs() -> None:
    """Les trois acteurs, horodatages et notes se posent explicitement.

    Rien n'est rempli automatiquement : c'est le test qui fournit chaque
    valeur, comme le feront les services de la phase 4.
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
    """Les trois relations utilisateur sont déclarées et lisibles séparément.

    Deux vérifications complémentaires : les accesseurs inverses existent et
    sont distincts — sans quoi Django refuserait le modèle —, et chacun
    retrouve bien la fiche attendue.
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
    """Créer puis enregistrer une fiche ne pose aucune date métier."""
    entity = create_entity()
    entity.status = EntityStatus.SUBMITTED
    entity.save()

    entity.refresh_from_db()

    assert entity.status == EntityStatus.SUBMITTED
    # Changer le statut ne déclenche aucune machine à états.
    assert entity.submitted_at is None
    assert entity.reviewed_at is None


def test_suppression_d_un_utilisateur_conserve_la_fiche() -> None:
    """`SET_NULL` : supprimer un compte vide les FK sans toucher la fiche.

    Une date historique peut donc subsister avec un acteur devenu nul, ce qui
    est exactement la raison pour laquelle aucune contrainte ne lie acteur,
    date et statut.
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
    """`objects`, déclaré en premier, est le manager par défaut.

    Conséquence voulue par l'ADR 0002 : ni l'administration, ni le parcours
    des relations, ni une future restauration ne masquent silencieusement de
    lignes.
    """
    assert isinstance(Entity._default_manager, models.Manager)
    assert Entity._default_manager.name == "objects"


def test_objects_voit_les_fiches_supprimees() -> None:
    """Le manager complet comprend les lignes supprimées logiquement."""
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
    """Une fiche active reste visible du manager quel que soit son statut.

    Le filtrage sur `published` appartient à la phase 3 ; `active` ne porte
    que sur la suppression logique.
    """
    create_entity(status=status)

    assert Entity.active.count() == 1


def test_active_ignore_la_valeur_de_deleted_by() -> None:
    """Seule `deleted_at` compte : `deleted_by` seul ne masque rien."""
    entity = create_entity()
    entity.deleted_by = create_user()
    entity.save()

    assert Entity.active.count() == 1


# --- Administration -----------------------------------------------------


def test_administration_voit_les_fiches_supprimees() -> None:
    """Le queryset de `EntityAdmin` conserve les lignes supprimées.

    C'est la condition pour qu'une restauration soit possible en phase 4.
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
    """Les horodatages de workflow et `deleted_by` ne sont pas saisissables."""
    admin = EntityAdmin(Entity, AdminSite())

    assert "submitted_at" in admin.readonly_fields
    assert "reviewed_at" in admin.readonly_fields
    assert "deleted_at" in admin.readonly_fields
    assert "deleted_by" in admin.readonly_fields
    # Restent modifiables pour préparer des jeux de test.
    assert "status" not in admin.readonly_fields
    assert "created_by" not in admin.readonly_fields
