"""Tests of the public visibility rule and of the read contract.

Completes `test_api.py` on three points it does not cover: the
centralised selection of `selectors.py`, the absence of any bypass by an
authenticated user or a superuser, and the language of the messages
rendered by the API.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager

import pytest
from django.contrib.admin.sites import AdminSite
from django.test import Client, RequestFactory
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from mythology.admin import EntityAdmin
from mythology.models import Entity, EntityStatus, RelationKind
from mythology.selectors import (
    is_publicly_visible,
    public_entities,
    public_entity_detail,
    public_relations,
)
from mythology.tests.factories import (
    create_entity,
    create_published_entity,
    create_relation,
)

pytestmark = pytest.mark.django_db


def deleted_published_entity(**extra: object) -> Entity:
    """A published record then marked as logically deleted, through the ORM."""
    entity = create_published_entity(**extra)
    entity.deleted_at = timezone.now()
    entity.save()
    return entity


# --- Sélection centralisée ---------------------------------------------


@pytest.mark.parametrize(
    "status",
    [EntityStatus.DRAFT, EntityStatus.SUBMITTED, EntityStatus.REJECTED],
)
def test_public_entities_exclut_les_statuts_non_publies(status: str) -> None:
    create_entity(status=status)

    assert public_entities().count() == 0


def test_public_entities_exclut_une_publiee_supprimee() -> None:
    """Both conditions are necessary: published **and** not deleted."""
    deleted_published_entity()

    assert public_entities().count() == 0


def test_public_entities_retient_une_publiee_active() -> None:
    entity = create_published_entity()

    assert list(public_entities()) == [entity]


def test_les_managers_conservent_leur_portee() -> None:
    """Editorial visibility has not been pushed into the managers.

    `objects` stays complete, `active` filters deletion only: that is what
    decision 7 of ADR 0002 requires, and what lets the admin and a future
    restoration reach every row.
    """
    create_entity(name="Brouillon", slug="brouillon")
    deleted_published_entity(name="Supprimée", slug="supprimee")
    create_published_entity(name="Publiée", slug="publiee")

    assert Entity.objects.count() == 3
    assert Entity.active.count() == 2
    assert public_entities().count() == 1


def test_public_relations_filtre_les_cibles_non_publiques() -> None:
    """Unresolved links and public targets kept, the rest discarded."""
    source = create_published_entity(name="Source", slug="source")
    publique = create_published_entity(name="Publique", slug="publique")
    brouillon = create_entity(name="Brouillon", slug="brouillon")
    supprimee = deleted_published_entity(name="Supprimée", slug="supprimee")

    conservee = create_relation(source, RelationKind.CONSORT, to_entity=publique)
    create_relation(source, RelationKind.PARENT, to_entity=brouillon)
    create_relation(source, RelationKind.ENEMY, to_entity=supprimee)
    citee = create_relation(source, RelationKind.ALLY, to_name="Sans fiche")

    assert set(public_relations()) == {conservee, citee}


def test_is_publicly_visible() -> None:
    """The serializer guard applies the same rule, in Python."""
    assert is_publicly_visible(create_published_entity()) is True
    assert is_publicly_visible(create_entity(name="B", slug="b")) is False
    assert is_publicly_visible(deleted_published_entity(name="C", slug="c")) is False
    assert is_publicly_visible(None) is False


# --- Aucun contournement par l'utilisateur ------------------------------


def test_un_utilisateur_connecte_ne_contourne_pas_la_regle(client: Client) -> None:
    """Signing in grants no access to unpublished records."""
    cache = create_entity(name="Brouillon", slug="brouillon")
    User.objects.create_user(username="contributor", password="test-password")
    client.login(username="contributor", password="test-password")

    liste = client.get(reverse("entity-list"))
    detail = client.get(reverse("entity-detail", kwargs={"slug": cache.slug}))

    assert liste.json()["count"] == 0
    assert liste.json()["results"] == []
    assert detail.status_code == 404


def test_un_superutilisateur_ne_contourne_pas_la_regle(client: Client) -> None:
    """Even a superuser sees no more: these routes are public.

    They are not private management routes; the admin remains the way to
    reach unpublished records.
    """
    cache = create_entity(name="Brouillon", slug="brouillon")
    User.objects.create_superuser(username="root", password="test-password")
    client.login(username="root", password="test-password")

    liste = client.get(reverse("entity-list"))
    detail = client.get(reverse("entity-detail", kwargs={"slug": cache.slug}))

    assert liste.json()["count"] == 0
    assert liste.json()["results"] == []
    assert detail.status_code == 404


def test_l_administration_conserve_ses_acces() -> None:
    """The admin still sees drafts and deleted records."""
    create_entity(name="Brouillon", slug="brouillon")
    deleted_published_entity(name="Supprimée", slug="supprimee")
    create_published_entity(name="Publiée", slug="publiee")

    admin = EntityAdmin(Entity, AdminSite())
    requete = RequestFactory().get("/admin/mythology/entity/")
    requete.user = User.objects.create_superuser(
        username="staff", password="test-password"
    )

    assert admin.get_queryset(requete).count() == 3


# --- Indistinguabilité du 404 ------------------------------------------


def test_404_identique_pour_slug_inconnu_et_fiche_masquee(client: Client) -> None:
    """Both responses are identical: nothing reveals the existence.

    A client must not be able to deduce that a record exists but is not
    published, nor to learn its status.
    """
    cache = create_entity(name="Brouillon", slug="brouillon")

    inconnu = client.get(reverse("entity-detail", kwargs={"slug": "jamais-vu"}))
    masque = client.get(reverse("entity-detail", kwargs={"slug": cache.slug}))

    assert inconnu.status_code == masque.status_code == 404
    assert inconnu.json() == masque.json()
    for interdit in ("draft", "status", "brouillon", "Brouillon"):
        assert interdit not in masque.content.decode()


# --- Langue publique ----------------------------------------------------


def test_message_404_est_en_anglais(client: Client) -> None:
    """The standard errors rendered by the API are in English (ADR 0003)."""
    response = client.get(reverse("entity-detail", kwargs={"slug": "jamais-vu"}))

    assert response.status_code == 404
    assert response.json() == {"detail": "No Entity matches the given query."}


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_message_405_est_en_anglais(client: Client, method: str) -> None:
    """Writes stay refused, with an English message."""
    response = getattr(client, method)(reverse("entity-list"))

    assert response.status_code == 405
    assert response.json()["detail"] == f'Method "{method.upper()}" not allowed.'


def test_libelles_de_choix_sont_en_anglais() -> None:
    """The public labels of the domain enumerations are in English."""
    from mythology.models import EntityType, Gender, ThreatLevel

    assert EntityType.DIVINITY.label == "Divinity"
    assert EntityType.HERO.label == "Hero"
    assert EntityType.CREATURE.label == "Creature"
    assert Gender.FEMALE.label == "Female"
    assert Gender.ANDROGYNOUS.label == "Androgynous"
    assert ThreatLevel.HIGH.label == "High"


def test_verbose_names_sont_en_anglais() -> None:
    """The `verbose_name` values of the domain are in English."""
    assert Entity._meta.verbose_name == "entity"
    assert Entity._meta.verbose_name_plural == "entities"


def test_message_de_validation_de_profil_est_en_anglais() -> None:
    """The profile attachment error is rendered in English."""
    from django.core.exceptions import ValidationError

    from mythology.models import HeroProfile

    with pytest.raises(ValidationError) as excinfo:
        HeroProfile(entity=create_published_entity()).full_clean()

    message = excinfo.value.message_dict["entity"][0]
    assert message == (
        "A hero profile can only be attached to an entity of type 'hero'."
    )


# --- Coût du détail -----------------------------------------------------


def test_aucune_requete_pour_une_reference_masquee(
    django_assert_num_queries: Callable[[int], AbstractContextManager[None]],
) -> None:
    """Hiding a reference costs no extra query.

    `variant_of` is joined by the queryset and the relations are prefetched
    already filtered: the serializer guard runs on in-memory objects, even
    when it decides to hide.
    """
    reference = create_entity(name="Référence cachée", slug="reference-cachee")
    cible = create_entity(name="Cible cachée", slug="cible-cachee")
    entity = create_published_entity(name="Shango", slug="shango", variant_of=reference)
    create_relation(entity, RelationKind.PARENT, to_entity=cible)
    create_relation(entity, RelationKind.ALLY, to_name="Sans fiche")

    from mythology.serializers import EntityDetailSerializer

    loaded = public_entity_detail().get(slug="shango")

    with django_assert_num_queries(0):
        payload = EntityDetailSerializer(loaded).data

    assert payload["variant_of"] is None
    assert len(payload["relations"]) == 1
    assert payload["relations"][0]["to_name"] == "Sans fiche"


def test_le_serializer_filtre_meme_sans_queryset_prepare() -> None:
    """The guard does not depend on the queryset: no fallback path leaks.

    On a bare queryset the filtering costs queries but stays correct - that
    is what guarantees that a careless internal call does not republish a
    hidden reference.
    """
    reference = create_entity(name="Référence cachée", slug="reference-cachee")
    cible = create_entity(name="Cible cachée", slug="cible-cachee")
    entity = create_published_entity(name="Shango", slug="shango", variant_of=reference)
    create_relation(entity, RelationKind.PARENT, to_entity=cible)

    from mythology.serializers import EntityDetailSerializer

    nu = Entity.objects.get(slug="shango")
    payload = EntityDetailSerializer(nu).data

    assert payload["variant_of"] is None
    assert payload["relations"] == []
