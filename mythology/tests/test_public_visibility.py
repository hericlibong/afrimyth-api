"""Tests de la règle de visibilité publique et du contrat de lecture.

Complète `test_api.py` sur trois points que celui-ci ne couvre pas : la
sélection centralisée de `selectors.py`, l'absence de contournement par un
utilisateur connecté ou un superutilisateur, et la langue des messages rendus
par l'API.
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
    """Fiche publiée puis marquée supprimée logiquement, par l'ORM."""
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
    """Les deux conditions sont nécessaires : publiée **et** non supprimée."""
    deleted_published_entity()

    assert public_entities().count() == 0


def test_public_entities_retient_une_publiee_active() -> None:
    entity = create_published_entity()

    assert list(public_entities()) == [entity]


def test_les_managers_conservent_leur_portee() -> None:
    """La visibilité éditoriale n'a pas été poussée dans les managers.

    `objects` reste complet, `active` ne filtre que la suppression : c'est ce
    que demande la décision 7 de l'ADR 0002, et ce qui permet à
    l'administration et à une future restauration d'atteindre toutes les
    lignes.
    """
    create_entity(name="Brouillon", slug="brouillon")
    deleted_published_entity(name="Supprimée", slug="supprimee")
    create_published_entity(name="Publiée", slug="publiee")

    assert Entity.objects.count() == 3
    assert Entity.active.count() == 2
    assert public_entities().count() == 1


def test_public_relations_filtre_les_cibles_non_publiques() -> None:
    """Liens non résolus et cibles publiques conservés, le reste écarté."""
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
    """La garde du serializer applique la même règle, en Python."""
    assert is_publicly_visible(create_published_entity()) is True
    assert is_publicly_visible(create_entity(name="B", slug="b")) is False
    assert is_publicly_visible(deleted_published_entity(name="C", slug="c")) is False
    assert is_publicly_visible(None) is False


# --- Aucun contournement par l'utilisateur ------------------------------


def test_un_utilisateur_connecte_ne_contourne_pas_la_regle(client: Client) -> None:
    """Se connecter ne donne pas accès aux fiches non publiées."""
    cache = create_entity(name="Brouillon", slug="brouillon")
    User.objects.create_user(username="contributor", password="test-password")
    client.login(username="contributor", password="test-password")

    liste = client.get(reverse("entity-list"))
    detail = client.get(reverse("entity-detail", kwargs={"slug": cache.slug}))

    assert liste.json() == []
    assert detail.status_code == 404


def test_un_superutilisateur_ne_contourne_pas_la_regle(client: Client) -> None:
    """Même un superutilisateur ne voit pas plus : ces routes sont publiques.

    Ce ne sont pas des routes privées de gestion ; l'administration reste le
    chemin d'accès aux fiches non publiées.
    """
    cache = create_entity(name="Brouillon", slug="brouillon")
    User.objects.create_superuser(username="root", password="test-password")
    client.login(username="root", password="test-password")

    liste = client.get(reverse("entity-list"))
    detail = client.get(reverse("entity-detail", kwargs={"slug": cache.slug}))

    assert liste.json() == []
    assert detail.status_code == 404


def test_l_administration_conserve_ses_acces() -> None:
    """L'administration voit toujours brouillons et fiches supprimées."""
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
    """Les deux réponses sont identiques : rien ne révèle l'existence.

    Un client ne doit pas pouvoir déduire qu'une fiche existe mais n'est pas
    publiée, ni connaître son statut.
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
    """Les erreurs standard rendues par l'API sont en anglais (ADR 0003)."""
    response = client.get(reverse("entity-detail", kwargs={"slug": "jamais-vu"}))

    assert response.status_code == 404
    assert response.json() == {"detail": "No Entity matches the given query."}


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_message_405_est_en_anglais(client: Client, method: str) -> None:
    """Les écritures restent refusées, avec un message anglais."""
    response = getattr(client, method)(reverse("entity-list"))

    assert response.status_code == 405
    assert response.json()["detail"] == f'Method "{method.upper()}" not allowed.'


def test_libelles_de_choix_sont_en_anglais() -> None:
    """Les libellés publics des énumérations du domaine sont anglais."""
    from mythology.models import EntityType, Gender, ThreatLevel

    assert EntityType.DIVINITY.label == "Divinity"
    assert EntityType.HERO.label == "Hero"
    assert EntityType.CREATURE.label == "Creature"
    assert Gender.FEMALE.label == "Female"
    assert Gender.ANDROGYNOUS.label == "Androgynous"
    assert ThreatLevel.HIGH.label == "High"


def test_verbose_names_sont_en_anglais() -> None:
    """Les `verbose_name` du domaine sont anglais."""
    assert Entity._meta.verbose_name == "entity"
    assert Entity._meta.verbose_name_plural == "entities"


def test_message_de_validation_de_profil_est_en_anglais() -> None:
    """L'erreur de rattachement de profil est rendue en anglais."""
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
    """Masquer une référence ne coûte aucune requête supplémentaire.

    `variant_of` est joint par le queryset et les relations sont préchargées
    déjà filtrées : la garde du serializer s'exécute sur des objets en
    mémoire, y compris quand elle décide de masquer.
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
    """La garde ne dépend pas du queryset : aucun chemin de repli ne fuite.

    Sur un queryset nu, le filtrage coûte des requêtes mais reste correct —
    c'est ce qui garantit qu'un appel interne distrait ne republie pas une
    référence masquée.
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
