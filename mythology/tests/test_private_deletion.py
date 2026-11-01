"""Soft deletion and restoration of a record.

Covers `DELETE /api/manage/entities/{slug}/` and
`POST /api/manage/entities/{slug}/restore/`: the rights, distinct from those of
an ordinary update; the columns written and those kept; the disappearance from
every read and write once deleted; the protection a reference draws from its
active variants, in both directions; and the coordination of that protection
with the concurrent writes that assign `variant_of`.

The role matrix of the ordinary writes, the JWT mechanics and the public read
contract have their own suites and are only sampled here.
"""

from collections.abc import Iterable
from typing import Any

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from rest_framework.generics import get_object_or_404
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from accounts.roles import ADMINISTRATOR, CONTRIBUTOR, REVIEWER
from mythology.deletion import locked_in_pk_order
from mythology.models import (
    CreatureProfile,
    DivinityProfile,
    Entity,
    EntityRelation,
    EntityStatus,
    EntityType,
    Gender,
    HeroProfile,
    RelationKind,
    Source,
    SourceKind,
)
from mythology.tests.factories import (
    create_divinity_profile,
    create_entity,
    create_relation,
    create_source,
)

pytestmark = pytest.mark.django_db

PASSWORD = "synthetic-test-passphrase-4418"


def detail_url(slug: str) -> str:
    return reverse("managed-entity-detail", kwargs={"slug": slug})


def restore_url(slug: str) -> str:
    return reverse("managed-entity-restore", kwargs={"slug": slug})


def public_detail_url(slug: str) -> str:
    return reverse("entity-detail", kwargs={"slug": slug})


def account(username: str, *, groups: Iterable[str] = (), **flags: Any) -> User:
    """Create a synthetic account and reuse or create its requested groups."""
    user = User.objects.create_user(username=username, password=PASSWORD, **flags)
    for name in groups:
        user.groups.add(Group.objects.get_or_create(name=name)[0])
    return user


def api(user: User | None = None) -> APIClient:
    """Build a JWT client, or an anonymous client when no account is given."""
    client = APIClient()
    if user is not None:
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


def record(slug: str, name: str, **extra: Any) -> Entity:
    """Create a consistent divinity record with its profile."""
    entity = create_entity(name=name, slug=slug, **extra)
    create_divinity_profile(entity)
    return entity


@pytest.fixture
def owner() -> User:
    return account("contributrice-suppression", groups=(CONTRIBUTOR,))


@pytest.fixture
def reviewer() -> User:
    return account("relectrice-suppression", groups=(REVIEWER,))


@pytest.fixture
def admin() -> User:
    return account("administratrice-suppression", groups=(ADMINISTRATOR,))


# --- Suppression autorisée et marques posées ----------------------------


def test_la_suppression_est_logique_et_conserve_toutes_les_lignes(
    owner: User, reviewer: User
) -> None:
    """Write only the deletion marks; remove no row at all."""
    cible = record("sup-cible", "Sup Cible", status=EntityStatus.PUBLISHED)
    fiche = record(
        "sup-logique",
        "Sup Logique",
        created_by=owner,
        status=EntityStatus.REJECTED,
        submitted_at=timezone.now(),
        reviewed_at=timezone.now(),
        reviewed_by=reviewer,
        review_notes="Kept review note.",
        category="Kept subtitle",
    )
    create_source(fiche, label="Kept Reference")
    create_relation(fiche, RelationKind.PARENT, to_entity=cible)
    avant = Entity.objects.get(pk=fiche.pk)

    response = api(owner).delete(detail_url(fiche.slug))

    assert response.status_code == 204
    assert response.content == b""
    apres = Entity.objects.get(pk=fiche.pk)
    assert apres.deleted_at is not None
    assert apres.deleted_by_id == owner.pk
    assert apres.updated_at > avant.updated_at
    # Rien d'autre n'a bougé, et aucun enfant n'est orphelin.
    assert apres.status == EntityStatus.REJECTED
    assert apres.created_by_id == owner.pk
    assert apres.submitted_at == avant.submitted_at
    assert apres.reviewed_by_id == reviewer.pk
    assert apres.review_notes == "Kept review note."
    assert apres.category == "Kept subtitle"
    assert DivinityProfile.objects.filter(entity=fiche).count() == 1
    assert Source.objects.filter(entity=fiche).count() == 1
    assert EntityRelation.objects.filter(from_entity=fiche).count() == 1


@pytest.mark.parametrize(
    ("role", "statut", "attendu"),
    [
        ("owner", EntityStatus.DRAFT, 204),
        ("owner", EntityStatus.REJECTED, 204),
        ("owner", EntityStatus.SUBMITTED, 403),
        ("owner", EntityStatus.PUBLISHED, 403),
        ("other", EntityStatus.PUBLISHED, 403),
        ("reviewer", EntityStatus.DRAFT, 204),
        ("reviewer", EntityStatus.REJECTED, 204),
        ("reviewer", EntityStatus.SUBMITTED, 403),
        ("reviewer", EntityStatus.PUBLISHED, 403),
        ("admin", EntityStatus.SUBMITTED, 204),
        ("admin", EntityStatus.PUBLISHED, 204),
    ],
)
def test_le_droit_de_supprimer_suit_la_matrice_et_non_celui_du_patch(
    owner: User, request: pytest.FixtureRequest, role: str, statut: str, attendu: int
) -> None:
    """Separate the deletion right from the ordinary update right.

    A reviewer updates a submitted record but must not delete it, and a
    contributor never deletes a published one.
    """
    fiche = record("sup-matrice", "Sup Matrice", created_by=owner, status=statut)
    caller: User = (
        account(f"contributeur-b-{statut}", groups=(CONTRIBUTOR,))
        if role == "other"
        else request.getfixturevalue(role)
    )

    response = api(caller).delete(detail_url(fiche.slug))

    assert response.status_code == attendu
    assert (Entity.objects.get(pk=fiche.pk).deleted_at is None) is (attendu != 204)


def test_un_relecteur_peut_modifier_un_submitted_sans_le_supprimer(
    owner: User, reviewer: User
) -> None:
    """Prove the two rights really differ on the same record."""
    fiche = record(
        "sup-submitted",
        "Sup Submitted",
        created_by=owner,
        status=EntityStatus.SUBMITTED,
    )
    client = api(reviewer)

    patch = client.patch(detail_url(fiche.slug), {"category": "Edited"}, format="json")
    suppression = client.delete(detail_url(fiche.slug))

    assert patch.status_code == 200
    assert suppression.status_code == 403
    assert Entity.objects.get(pk=fiche.pk).deleted_at is None


def test_un_administrateur_supprime_une_fiche_sans_proprietaire(admin: User) -> None:
    fiche = record("sup-orpheline", "Sup Orpheline", status=EntityStatus.PUBLISHED)

    assert api(admin).delete(detail_url(fiche.slug)).status_code == 204
    assert Entity.objects.get(pk=fiche.pk).deleted_by_id == admin.pk


def test_un_second_delete_donne_404_sans_remplacer_la_premiere_marque(
    owner: User, admin: User
) -> None:
    fiche = record("sup-deux-fois", "Sup Deux Fois", created_by=owner)
    client = api(owner)

    assert client.delete(detail_url(fiche.slug)).status_code == 204
    premiere = Entity.objects.get(pk=fiche.pk)

    assert client.delete(detail_url(fiche.slug)).status_code == 404
    assert api(admin).delete(detail_url(fiche.slug)).status_code == 404

    apres = Entity.objects.get(pk=fiche.pk)
    assert apres.deleted_at == premiere.deleted_at
    assert apres.deleted_by_id == owner.pk


def test_un_appelant_anonyme_ou_sans_role_est_refuse(owner: User) -> None:
    fiche = record("sup-refus", "Sup Refus", created_by=owner)
    sans_role = api(account("staff-seul-suppression", is_staff=True))

    assert api().delete(detail_url(fiche.slug)).status_code == 401
    assert sans_role.delete(detail_url(fiche.slug)).status_code == 403
    assert Entity.objects.get(pk=fiche.pk).deleted_at is None


def test_une_fiche_inconnue_non_lisible_ou_supprimee_donne_le_meme_404(
    owner: User, admin: User
) -> None:
    autre = account("contributeur-c-suppression", groups=(CONTRIBUTOR,))
    interdite = record("sup-interdite", "Sup Interdite", created_by=autre)
    supprimee = record(
        "sup-deja", "Sup Deja", created_by=owner, deleted_at=timezone.now()
    )
    client = api(owner)

    refus = [
        client.delete(detail_url(interdite.slug)),
        client.delete(detail_url(supprimee.slug)),
        client.delete(detail_url("jamais-vue")),
        api(admin).delete(detail_url(supprimee.slug)),
    ]

    assert [reponse.status_code for reponse in refus] == [404, 404, 404, 404]
    assert refus[0].json() == refus[1].json() == refus[2].json()
    assert "Sup Interdite" not in str(refus[0].json())


@pytest.mark.parametrize(
    "body", [{"deleted_at": "2026-11-01T09:00:00Z"}, {"reason": "x"}, [], "text"]
)
def test_un_corps_de_suppression_est_refuse_sans_mutation(
    owner: User, body: Any
) -> None:
    fiche = record("sup-corps", "Sup Corps", created_by=owner)

    response = api(owner).delete(detail_url(fiche.slug), body, format="json")

    assert response.status_code == 400
    assert Entity.objects.get(pk=fiche.pk).deleted_at is None


def test_le_corps_n_est_examine_qu_apres_la_visibilite_et_le_droit(
    owner: User, reviewer: User
) -> None:
    """Refuse the actor first: no diagnosis on a record it may not delete."""
    interdite = record(
        "sup-ordre",
        "Sup Ordre",
        created_by=owner,
        status=EntityStatus.SUBMITTED,
    )

    refus = api(reviewer).delete(
        detail_url(interdite.slug), {"deleted_at": "now"}, format="json"
    )
    inconnue = api(owner).delete(detail_url("jamais-vue"), {"x": 1}, format="json")

    assert refus.status_code == 403
    assert inconnue.status_code == 404


# --- Invisibilité et écritures fermées après suppression ----------------


def test_une_fiche_supprimee_disparait_de_toutes_les_lectures(
    client: Client, owner: User, admin: User
) -> None:
    """Hide a deleted record from the public and from every private read."""
    fiche = record(
        "sup-invisible",
        "Sup Invisible",
        created_by=owner,
        status=EntityStatus.PUBLISHED,
    )

    assert client.get(public_detail_url(fiche.slug)).status_code == 200
    assert api(admin).delete(detail_url(fiche.slug)).status_code == 204

    assert client.get(public_detail_url(fiche.slug)).status_code == 404
    assert client.get(reverse("entity-list")).json()["count"] == 0
    for user in (owner, admin):
        assert api(user).get(detail_url(fiche.slug)).status_code == 404
        slugs = {
            item["slug"]
            for item in api(user).get(reverse("managed-entity-list")).json()["results"]
        }
        assert fiche.slug not in slugs


def test_une_fiche_supprimee_n_accepte_plus_aucune_ecriture(
    owner: User, admin: User
) -> None:
    """Close every earlier write and transition on a deleted record."""
    fiche = record("sup-fermee", "Sup Fermee", created_by=owner)
    create_source(fiche, label="Existing Reference")
    assert api(owner).delete(detail_url(fiche.slug)).status_code == 204
    client = api(admin)
    sources = reverse("managed-entity-sources", kwargs={"slug": fiche.slug})

    assert (
        client.patch(
            detail_url(fiche.slug), {"category": "x"}, format="json"
        ).status_code
        == 404
    )
    assert (
        client.post(
            sources, {"label": "New", "kind": SourceKind.BOOK}, format="json"
        ).status_code
        == 404
    )
    for operation in ("submit", "withdraw", "resume", "publish", "reject", "reopen"):
        url = reverse(f"managed-entity-{operation}", kwargs={"slug": fiche.slug})
        assert client.post(url).status_code == 404, operation


def test_les_references_vers_une_fiche_supprimee_sont_masquees(
    owner: User, admin: User
) -> None:
    """Hide the deleted target without copying its name anywhere.

    The deletion mark is set directly here: the API refuses to delete a figure
    that still has an active variant, so this state only exists on records
    deleted before the invariant applied, or outside the API.
    """
    cible = record(
        "sup-cible-masquee",
        "Sup Cible Masquee",
        created_by=owner,
        deleted_at=timezone.now(),
        deleted_by=admin,
    )
    variante = record("sup-variante", "Sup Variante", created_by=owner)
    variante.variant_of = cible
    variante.save(update_fields=["variant_of"])
    create_relation(variante, RelationKind.PARENT, to_entity=cible)

    lue = api(owner).get(detail_url(variante.slug))

    assert lue.status_code == 200
    assert lue.json()["variant_of"] is None
    assert lue.json()["relations"] == []
    assert "Sup Cible Masquee" not in lue.content.decode()


# --- Protection des variantes -------------------------------------------


@pytest.mark.parametrize(
    "statut",
    [EntityStatus.DRAFT, EntityStatus.SUBMITTED, EntityStatus.PUBLISHED],
)
def test_une_variante_active_protege_sa_reference(admin: User, statut: str) -> None:
    """Protect the reference whatever the status of the variant."""
    reference = record("sup-reference", "Sup Reference", status=EntityStatus.PUBLISHED)
    autre = account(f"contributeur-variante-{statut}", groups=(CONTRIBUTOR,))
    variante = record(
        "sup-variante-active",
        "Sup Variante Active",
        created_by=autre,
        status=statut,
        variant_of=reference,
    )

    response = api(admin).delete(detail_url(reference.slug))

    assert response.status_code == 400
    assert "active cultural variant" in str(response.json())
    # Ni le nom, ni l'identifiant, ni le nombre de variantes ne fuient.
    assert "Sup Variante Active" not in str(response.json())
    assert str(variante.pk) not in str(response.json())
    assert Entity.objects.get(pk=reference.pk).deleted_at is None


def test_une_variante_supprimee_ne_protege_plus_sa_reference(admin: User) -> None:
    reference = record("sup-ref-libre", "Sup Ref Libre")
    record(
        "sup-variante-supprimee",
        "Sup Variante Supprimee",
        variant_of=reference,
        deleted_at=timezone.now(),
    )

    assert api(admin).delete(detail_url(reference.slug)).status_code == 204


def test_une_relation_ne_protege_pas_sa_cible(admin: User) -> None:
    """Keep the protection to `variant_of`, as the ADR says."""
    cible = record("sup-ref-relation", "Sup Ref Relation")
    source = record("sup-source-relation", "Sup Source Relation")
    create_relation(source, RelationKind.PARENT, to_entity=cible)

    assert api(admin).delete(detail_url(cible.slug)).status_code == 204


def test_detacher_puis_supprimer_la_reference_fonctionne(
    owner: User, admin: User
) -> None:
    reference = record("sup-ref-detachee", "Sup Ref Detachee")
    variante = record(
        "sup-variante-detachee",
        "Sup Variante Detachee",
        created_by=owner,
        variant_of=reference,
    )
    client = api(admin)

    assert client.delete(detail_url(reference.slug)).status_code == 400
    assert (
        client.patch(
            detail_url(variante.slug), {"variant_of": None}, format="json"
        ).status_code
        == 200
    )
    assert client.delete(detail_url(reference.slug)).status_code == 204


# --- Restauration -------------------------------------------------------


def test_la_restauration_efface_les_marques_et_conserve_le_reste(
    owner: User, reviewer: User, admin: User
) -> None:
    fiche = record(
        "res-conservee",
        "Res Conservee",
        created_by=owner,
        status=EntityStatus.REJECTED,
        submitted_at=timezone.now(),
        reviewed_at=timezone.now(),
        reviewed_by=reviewer,
        review_notes="Kept review note.",
        deleted_at=timezone.now(),
        deleted_by=admin,
    )
    avant = Entity.objects.get(pk=fiche.pk)

    response = api(admin).post(restore_url(fiche.slug))

    assert response.status_code == 200
    assert response.json()["slug"] == fiche.slug
    apres = Entity.objects.get(pk=fiche.pk)
    assert apres.deleted_at is None
    assert apres.deleted_by_id is None
    assert apres.updated_at > avant.updated_at
    assert apres.status == EntityStatus.REJECTED
    assert apres.created_by_id == owner.pk
    assert apres.submitted_at == avant.submitted_at
    assert apres.reviewed_by_id == reviewer.pk
    assert apres.review_notes == "Kept review note."


def test_la_restauration_d_une_fiche_publiee_la_rend_publique(
    client: Client, admin: User
) -> None:
    """Keep the previous status: a published record becomes public again."""
    fiche = record(
        "res-publiee",
        "Res Publiee",
        status=EntityStatus.PUBLISHED,
        deleted_at=timezone.now(),
        deleted_by=admin,
    )

    assert client.get(public_detail_url(fiche.slug)).status_code == 404

    assert api(admin).post(restore_url(fiche.slug)).status_code == 200

    assert client.get(public_detail_url(fiche.slug)).status_code == 200
    assert client.get(reverse("entity-list")).json()["count"] == 1
    assert Entity.objects.get(pk=fiche.pk).status == EntityStatus.PUBLISHED


def test_la_restauration_d_un_brouillon_le_laisse_prive(
    client: Client, owner: User, admin: User
) -> None:
    fiche = record(
        "res-brouillon",
        "Res Brouillon",
        created_by=owner,
        deleted_at=timezone.now(),
        deleted_by=admin,
    )

    assert api(admin).post(restore_url(fiche.slug)).status_code == 200

    assert client.get(public_detail_url(fiche.slug)).status_code == 404
    assert api(owner).get(detail_url(fiche.slug)).status_code == 200


@pytest.mark.parametrize("role", ["owner", "reviewer", "sans-role", "anonyme"])
def test_la_restauration_est_reservee_a_l_administrateur(
    owner: User, admin: User, request: pytest.FixtureRequest, role: str
) -> None:
    """Refuse every other account, for an existing slug as for an unknown one."""
    fiche = record(
        "res-reservee",
        "Res Reservee",
        created_by=owner,
        deleted_at=timezone.now(),
        deleted_by=admin,
    )
    caller: User | None = None
    if role in {"owner", "reviewer"}:
        caller = request.getfixturevalue(role)
    elif role == "sans-role":
        caller = account("sans-role-restauration")
    client = api(caller)
    attendu = 401 if role == "anonyme" else 403

    existante = client.post(restore_url(fiche.slug))
    inconnue = client.post(restore_url("jamais-vue"))

    assert existante.status_code == inconnue.status_code == attendu
    assert existante.json() == inconnue.json()
    assert Entity.objects.get(pk=fiche.pk).deleted_at is not None


def test_une_fiche_non_supprimee_ou_inconnue_est_distinguee(admin: User) -> None:
    """Answer 400 on a live record and 404 on an unknown slug."""
    vivante = record("res-vivante", "Res Vivante")
    avant = Entity.objects.get(pk=vivante.pk)
    client = api(admin)

    non_supprimee = client.post(restore_url(vivante.slug))
    inconnue = client.post(restore_url("jamais-vue"))

    assert non_supprimee.status_code == 400
    assert inconnue.status_code == 404
    apres = Entity.objects.get(pk=vivante.pk)
    assert apres.updated_at == avant.updated_at


def test_une_seconde_restauration_est_refusee_sans_mutation(admin: User) -> None:
    fiche = record(
        "res-deux-fois", "Res Deux Fois", deleted_at=timezone.now(), deleted_by=admin
    )
    client = api(admin)

    assert client.post(restore_url(fiche.slug)).status_code == 200
    premiere = Entity.objects.get(pk=fiche.pk)

    assert client.post(restore_url(fiche.slug)).status_code == 400
    assert Entity.objects.get(pk=fiche.pk).updated_at == premiere.updated_at


@pytest.mark.parametrize("body", [{"deleted_at": None}, {"x": 1}, [], "text"])
def test_un_corps_de_restauration_est_refuse_sans_mutation(
    admin: User, body: Any
) -> None:
    fiche = record(
        "res-corps", "Res Corps", deleted_at=timezone.now(), deleted_by=admin
    )

    response = api(admin).post(restore_url(fiche.slug), body, format="json")

    assert response.status_code == 400
    assert Entity.objects.get(pk=fiche.pk).deleted_at is not None


def test_la_restauration_n_accepte_que_post(admin: User) -> None:
    fiche = record(
        "res-methodes", "Res Methodes", deleted_at=timezone.now(), deleted_by=admin
    )
    client = api(admin)

    for method in ("get", "put", "patch", "delete"):
        assert getattr(client, method)(restore_url(fiche.slug)).status_code == 405


def test_une_variante_ne_se_restaure_pas_avant_sa_reference(admin: User) -> None:
    """Keep the invariant: no active variant under a deleted reference."""
    reference = record(
        "res-reference", "Res Reference", deleted_at=timezone.now(), deleted_by=admin
    )
    variante = record(
        "res-variante",
        "Res Variante",
        variant_of=reference,
        deleted_at=timezone.now(),
        deleted_by=admin,
    )
    client = api(admin)

    refus = client.post(restore_url(variante.slug))

    assert refus.status_code == 400
    assert "reference first" in str(refus.json())
    apres = Entity.objects.get(pk=variante.pk)
    assert apres.deleted_at is not None
    assert apres.variant_of_id == reference.pk

    # L'ordre imposé : la référence d'abord, la variante ensuite.
    assert client.post(restore_url(reference.slug)).status_code == 200
    assert client.post(restore_url(variante.slug)).status_code == 200
    assert Entity.objects.get(pk=variante.pk).deleted_at is None


# --- Coordination avec les affectations concurrentes de variant_of ------


def write_between_selection_and_lock(
    monkeypatch: pytest.MonkeyPatch, work: Any
) -> None:
    """Run `work` between the private selection and the locked read.

    That gap is the window a concurrent transaction would use. This is a
    simulation inside one transaction, not a multithreaded test: it proves the
    re-read and the lock discipline exist, not that PostgreSQL serialises two
    live sessions.
    """

    def act_then_lock(queryset: Any, *args: Any, **kwargs: Any) -> Any:
        work()
        return get_object_or_404(queryset, *args, **kwargs)

    monkeypatch.setattr("mythology.views.get_object_or_404", act_then_lock)


def test_une_variante_creee_entre_temps_bloque_la_suppression(
    admin: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-read the variant protection after the lock, not before it."""
    reference = record("sup-course", "Sup Course")

    def create_variant() -> None:
        variante = create_entity(
            name="Sup Course Variante",
            slug="sup-course-variante",
            entity_type=EntityType.HERO,
            gender=Gender.NEUTRAL,
            variant_of=reference,
        )
        HeroProfile.objects.create(entity=variante)

    write_between_selection_and_lock(monkeypatch, create_variant)

    response = api(admin).delete(detail_url(reference.slug))

    assert response.status_code == 400
    assert Entity.objects.get(pk=reference.pk).deleted_at is None


def test_un_patch_de_variant_of_verrouille_la_reference(
    owner: User, admin: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refuse a patch that would make a record a variant of a deleted figure.

    The reference is locked and re-read inside the write transaction, after
    the field validation that resolved it, so a deletion landing in that
    window is seen instead of being overtaken.
    """
    reference = record("pat-reference", "Pat Reference", status=EntityStatus.PUBLISHED)
    fiche = record("pat-variante", "Pat Variante", created_by=owner)
    original = Entity.objects.select_for_update

    def delete_then_lock(*args: Any, **kwargs: Any) -> Any:
        # La suppression intervient après validation du champ, avant
        # l'acquisition ordonnée de la fiche et de sa référence.
        Entity.objects.filter(pk=reference.pk).update(
            deleted_at=timezone.now(), deleted_by=admin
        )
        monkeypatch.setattr(Entity.objects, "select_for_update", original)
        return original(*args, **kwargs)

    monkeypatch.setattr(Entity.objects, "select_for_update", delete_then_lock)

    response = api(owner).patch(
        detail_url(fiche.slug), {"variant_of": str(reference.pk)}, format="json"
    )

    assert response.status_code == 400
    assert "variant_of" in response.json()
    assert Entity.objects.get(pk=fiche.pk).variant_of_id is None


def test_une_creation_verrouille_la_reference(
    owner: User, admin: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refuse a creation whose reference was deleted in the same window."""
    reference = record("cre-reference", "Cre Reference", status=EntityStatus.PUBLISHED)

    def delete_then_lock(identifiers: Iterable[Any]) -> dict[Any, Entity]:
        Entity.objects.filter(pk=reference.pk).update(
            deleted_at=timezone.now(), deleted_by=admin
        )
        return locked_in_pk_order(identifiers)

    # Laisser d'abord le serializer résoudre une référence encore active ;
    # simuler sa suppression juste avant la lecture verrouillée.
    monkeypatch.setattr("mythology.serializers.locked_in_pk_order", delete_then_lock)

    response = api(owner).post(
        reverse("managed-entity-list"),
        {
            "name": "Cre Variante",
            "slug": "cre-variante",
            "entity_type": EntityType.CREATURE,
            "gender": Gender.NEUTRAL,
            "variant_of": str(reference.pk),
        },
        format="json",
    )

    assert response.status_code == 400
    assert "variant_of" in response.json()
    assert not Entity.objects.filter(slug="cre-variante").exists()
    assert CreatureProfile.objects.count() == 0


def test_le_droit_de_supprimer_est_relu_sur_la_ligne_verrouillee(
    owner: User, reviewer: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refuse a reviewer whose record was submitted before the lock."""
    fiche = record("sup-droit", "Sup Droit", created_by=owner)

    def submit() -> None:
        Entity.objects.filter(pk=fiche.pk).update(status=EntityStatus.SUBMITTED)

    write_between_selection_and_lock(monkeypatch, submit)

    response = api(reviewer).delete(detail_url(fiche.slug))

    assert response.status_code == 403
    assert Entity.objects.get(pk=fiche.pk).deleted_at is None


# --- Garde-fou de configuration de la vue -------------------------------


def test_la_vue_privee_n_ouvre_pas_le_remplacement_complet(owner: User) -> None:
    """Keep `PUT` closed on the private detail, next to the new `DELETE`."""
    fiche = record("sup-put", "Sup Put", created_by=owner)

    assert api(owner).put(detail_url(fiche.slug)).status_code == 405
