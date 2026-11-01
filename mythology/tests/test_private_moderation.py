"""Moderation decisions: publish, reject and reopen.

Covers the three POST actions added under `/api/manage/entities/{slug}/`: the
actor each one requires — ownership grants none of them — the required
starting status, the review marks and notes written, the refusal of any other
input, and the public visibility that follows a publication or a reopening.

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
from mythology.models import Entity, EntityStatus, RelationKind, SourceKind
from mythology.tests.factories import (
    create_divinity_profile,
    create_entity,
    create_relation,
)
from mythology.transitions import (
    PUBLISH,
    REJECT,
    REOPEN,
    RESUME,
    SUBMIT,
    WITHDRAW,
)

pytestmark = pytest.mark.django_db

PASSWORD = "synthetic-test-passphrase-6214"

REASON = "Please clarify the source of this claim."
APPROVAL = "Reviewed and approved."

#: Action → statut de départ qui la fait réussir.
START_STATUS = {
    PUBLISH: EntityStatus.SUBMITTED,
    REJECT: EntityStatus.SUBMITTED,
    REOPEN: EntityStatus.PUBLISHED,
}

DECISIONS = [PUBLISH, REJECT]
MODERATION_ACTIONS = sorted(START_STATUS)

#: Corps minimal valide de chaque action : le rejet exige son motif.
VALID_BODY: dict[str, dict[str, Any]] = {PUBLISH: {}, REJECT: {"review_notes": REASON}}


def action_url(action: str, slug: str) -> str:
    return reverse(f"managed-entity-{action}", kwargs={"slug": slug})


def detail_url(slug: str) -> str:
    return reverse("managed-entity-detail", kwargs={"slug": slug})


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


def submitted(slug: str, name: str, owner: User | None = None, **extra: Any) -> Entity:
    """Create a record in the state a decision starts from."""
    return record(
        slug,
        name,
        created_by=owner,
        status=EntityStatus.SUBMITTED,
        submitted_at=timezone.now(),
        **extra,
    )


def decide(user: User, action: str, slug: str, body: Any = None) -> Any:
    client = api(user)
    if body is None:
        return client.post(action_url(action, slug))
    return client.post(action_url(action, slug), body, format="json")


@pytest.fixture
def owner() -> User:
    return account("contributrice-moderation", groups=(CONTRIBUTOR,))


@pytest.fixture
def reviewer() -> User:
    return account("relectrice-moderation", groups=(REVIEWER,))


@pytest.fixture
def admin() -> User:
    return account("administratrice-moderation", groups=(ADMINISTRATOR,))


# --- Succès et état enregistré ------------------------------------------


@pytest.mark.parametrize("acteur", ["reviewer", "admin"])
def test_la_publication_enregistre_la_revue_cote_serveur(
    owner: User, request: pytest.FixtureRequest, acteur: str
) -> None:
    """Record the status, the server date, the calling reviewer and the note."""
    fiche = submitted("mod-publiee", "Mod Publiee", owner)
    soumise_le = fiche.submitted_at
    user: User = request.getfixturevalue(acteur)

    response = decide(user, PUBLISH, fiche.slug, {"review_notes": APPROVAL})

    assert response.status_code == 200
    assert response.json()["status"] == EntityStatus.PUBLISHED
    apres = Entity.objects.get(pk=fiche.pk)
    assert apres.status == EntityStatus.PUBLISHED
    assert apres.reviewed_by_id == user.pk
    assert apres.reviewed_at is not None
    assert apres.review_notes == APPROVAL
    assert apres.submitted_at == soumise_le
    assert apres.created_by_id == owner.pk


def test_le_rejet_enregistre_le_motif(owner: User, reviewer: User) -> None:
    fiche = submitted("mod-rejetee", "Mod Rejetee", owner)
    soumise_le = fiche.submitted_at

    response = decide(reviewer, REJECT, fiche.slug, {"review_notes": REASON})

    assert response.status_code == 200
    assert response.json()["review_notes"] == REASON
    apres = Entity.objects.get(pk=fiche.pk)
    assert apres.status == EntityStatus.REJECTED
    assert apres.reviewed_by_id == reviewer.pk
    assert apres.reviewed_at is not None
    assert apres.review_notes == REASON
    assert apres.submitted_at == soumise_le


@pytest.mark.parametrize("body", [None, {}, {"review_notes": ""}])
def test_une_note_de_publication_omise_ou_vide_enregistre_une_note_vide(
    owner: User, reviewer: User, body: Any
) -> None:
    """Store an empty note rather than keeping an earlier one."""
    fiche = submitted(
        "mod-note-vide",
        "Mod Note Vide",
        owner,
        review_notes="Earlier note that must not survive.",
    )

    response = decide(reviewer, PUBLISH, fiche.slug, body)

    assert response.status_code == 200
    assert Entity.objects.get(pk=fiche.pk).review_notes == ""


def test_la_publication_conserve_une_date_de_soumission_nulle(
    owner: User, reviewer: User
) -> None:
    """Never invent a submission date on a record prepared by hand."""
    fiche = record(
        "mod-sans-date",
        "Mod Sans Date",
        created_by=owner,
        status=EntityStatus.SUBMITTED,
    )

    assert decide(reviewer, PUBLISH, fiche.slug, {}).status_code == 200
    assert Entity.objects.get(pk=fiche.pk).submitted_at is None


def test_la_reouverture_conserve_la_revue_et_n_enregistre_pas_son_auteur(
    owner: User, reviewer: User, admin: User
) -> None:
    """Reopening is not giving a review."""
    revue = timezone.now()
    fiche = record(
        "mod-rouverte",
        "Mod Rouverte",
        created_by=owner,
        status=EntityStatus.PUBLISHED,
        submitted_at=timezone.now(),
        reviewed_at=revue,
        reviewed_by=reviewer,
        review_notes="Kept publication note.",
    )

    response = decide(admin, REOPEN, fiche.slug)

    assert response.status_code == 200
    apres = Entity.objects.get(pk=fiche.pk)
    assert apres.status == EntityStatus.DRAFT
    assert apres.submitted_at is None
    assert apres.reviewed_at == revue
    assert apres.reviewed_by_id == reviewer.pk
    assert apres.review_notes == "Kept publication note."


@pytest.mark.parametrize("action", MODERATION_ACTIONS)
def test_seul_l_etat_editorial_est_ecrit(owner: User, admin: User, action: str) -> None:
    """Leave the owner, the type, the business fields and the profile alone."""
    fiche = record(
        "mod-intacte",
        "Mod Intacte",
        created_by=owner,
        status=START_STATUS[action],
        submitted_at=timezone.now(),
        category="Kept subtitle",
        characteristics=["Kept trait"],
    )
    avant = Entity.objects.get(pk=fiche.pk)

    assert decide(admin, action, fiche.slug, VALID_BODY.get(action)).status_code == 200

    apres = Entity.objects.get(pk=fiche.pk)
    assert apres.category == "Kept subtitle"
    assert apres.characteristics == ["Kept trait"]
    assert apres.created_by_id == owner.pk
    assert apres.entity_type == avant.entity_type
    assert apres.created_at == avant.created_at
    assert apres.deleted_at is None
    assert apres.updated_at > avant.updated_at
    assert apres.divinity_profile is not None


@pytest.mark.parametrize("action", MODERATION_ACTIONS)
def test_la_reponse_est_le_detail_prive(owner: User, admin: User, action: str) -> None:
    fiche = record(
        "mod-reponse",
        "Mod Reponse",
        created_by=owner,
        status=START_STATUS[action],
        submitted_at=timezone.now(),
    )

    response = decide(admin, action, fiche.slug, VALID_BODY.get(action))
    relue = api(admin).get(detail_url(fiche.slug))

    assert response.status_code == 200
    assert response.json() == relue.json()


# --- Droits propres à chaque action -------------------------------------


@pytest.mark.parametrize("action", DECISIONS)
def test_le_proprietaire_ne_modere_jamais_sa_propre_fiche(
    owner: User, action: str
) -> None:
    """Ownership never opens a decision, even on a record one may submit."""
    fiche = submitted("mod-propre", "Mod Propre", owner)

    response = decide(owner, action, fiche.slug, VALID_BODY[action])

    assert response.status_code == 403
    assert "owning the record grants nothing" in response.json()["detail"]
    assert Entity.objects.get(pk=fiche.pk).status == EntityStatus.SUBMITTED


def test_un_relecteur_ne_rouvre_pas_une_fiche_publiee(
    owner: User, reviewer: User
) -> None:
    """Reopening is reserved to an administrator."""
    fiche = record(
        "mod-publiee-relecteur",
        "Mod Publiee Relecteur",
        created_by=owner,
        status=EntityStatus.PUBLISHED,
    )

    response = decide(reviewer, REOPEN, fiche.slug)

    assert response.status_code == 403
    assert "requires an administrator" in response.json()["detail"]
    assert Entity.objects.get(pk=fiche.pk).status == EntityStatus.PUBLISHED


def test_un_contributeur_ne_rouvre_pas_une_fiche_publiee(
    owner: User,
) -> None:
    fiche = record(
        "mod-publiee-contrib",
        "Mod Publiee Contrib",
        created_by=owner,
        status=EntityStatus.PUBLISHED,
    )

    assert decide(owner, REOPEN, fiche.slug).status_code == 403


def test_un_superutilisateur_sans_groupe_modere_comme_administrateur(
    owner: User,
) -> None:
    root = account("secours-moderation", is_staff=True, is_superuser=True)
    fiche = submitted("mod-secours", "Mod Secours", owner)

    assert decide(root, PUBLISH, fiche.slug, {}).status_code == 200
    assert decide(root, REOPEN, fiche.slug).status_code == 200


@pytest.mark.parametrize("action", MODERATION_ACTIONS)
def test_une_fiche_sans_proprietaire_est_moderable(admin: User, action: str) -> None:
    fiche = record(
        "mod-orpheline",
        "Mod Orpheline",
        status=START_STATUS[action],
        submitted_at=timezone.now(),
    )

    assert decide(admin, action, fiche.slug, VALID_BODY.get(action)).status_code == 200


def test_un_acteur_refuse_ne_recoit_aucun_diagnostic_sur_le_corps(
    owner: User,
) -> None:
    """Refuse the actor before any look at the body or the status."""
    fiche = submitted("mod-diagnostic", "Mod Diagnostic", owner)

    sans_motif = decide(owner, REJECT, fiche.slug, {})
    champ_interdit = decide(owner, PUBLISH, fiche.slug, {"status": "published"})

    assert sans_motif.status_code == champ_interdit.status_code == 403
    assert "review_notes" not in str(sans_motif.json())
    assert "status" not in str(champ_interdit.json())


def test_un_appelant_anonyme_est_refuse_en_401(owner: User) -> None:
    fiche = submitted("mod-anonyme", "Mod Anonyme", owner)

    assert api().post(action_url(PUBLISH, fiche.slug)).status_code == 401


def test_un_compte_sans_role_metier_est_refuse_en_403(owner: User) -> None:
    fiche = submitted("mod-sans-role", "Mod Sans Role", owner)
    client = api(account("staff-seul-moderation", is_staff=True))

    assert client.post(action_url(PUBLISH, fiche.slug)).status_code == 403


def test_une_fiche_supprimee_inconnue_ou_interdite_donne_le_meme_404(
    owner: User, admin: User
) -> None:
    """Never let a refusal reveal that a record exists, deleted included."""
    supprimee = submitted(
        "mod-supprimee", "Mod Supprimee", owner, deleted_at=timezone.now()
    )

    par_admin = decide(admin, PUBLISH, supprimee.slug, {})
    par_proprietaire = decide(owner, PUBLISH, supprimee.slug, {})
    inconnue = decide(admin, PUBLISH, "jamais-vue", {})

    assert par_admin.status_code == 404
    assert par_proprietaire.status_code == inconnue.status_code == 404
    assert par_admin.json() == inconnue.json()
    assert Entity.objects.get(pk=supprimee.pk).status == EntityStatus.SUBMITTED


# --- Statuts de départ interdits ----------------------------------------


@pytest.mark.parametrize(
    ("action", "statut"),
    [
        (action, statut)
        for action in MODERATION_ACTIONS
        for statut in sorted(EntityStatus.values)
        if statut != START_STATUS[action]
    ],
)
def test_un_statut_de_depart_interdit_est_refuse_sans_mutation(
    owner: User, admin: User, action: str, statut: str
) -> None:
    """Accept exactly one starting status per action, and write nothing else."""
    fiche = record(
        "mod-statuts",
        "Mod Statuts",
        created_by=owner,
        status=statut,
        submitted_at=timezone.now(),
        review_notes="Untouched note.",
    )
    avant = Entity.objects.get(pk=fiche.pk)

    response = decide(admin, action, fiche.slug, VALID_BODY.get(action))

    assert response.status_code == 400
    apres = Entity.objects.get(pk=fiche.pk)
    assert apres.status == statut
    assert apres.reviewed_at is None
    assert apres.review_notes == "Untouched note."
    assert apres.updated_at == avant.updated_at


@pytest.mark.parametrize("action", MODERATION_ACTIONS)
def test_une_decision_repetee_est_refusee_sans_nouvelle_ecriture(
    owner: User, admin: User, action: str
) -> None:
    fiche = record(
        "mod-repetee",
        "Mod Repetee",
        created_by=owner,
        status=START_STATUS[action],
        submitted_at=timezone.now(),
    )

    premiere = decide(admin, action, fiche.slug, VALID_BODY.get(action))
    apres_premiere = Entity.objects.get(pk=fiche.pk)
    seconde = decide(admin, action, fiche.slug, VALID_BODY.get(action))

    assert premiere.status_code == 200
    assert seconde.status_code == 400
    apres_seconde = Entity.objects.get(pk=fiche.pk)
    assert apres_seconde.reviewed_at == apres_premiere.reviewed_at
    assert apres_seconde.review_notes == apres_premiere.review_notes
    assert apres_seconde.updated_at == apres_premiere.updated_at


# --- Contrat d'entrée ---------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [None, {}, {"review_notes": ""}, {"review_notes": "   "}, {"review_notes": None}],
    ids=["absent", "vide", "note-vide", "note-blanche", "note-nulle"],
)
def test_le_rejet_exige_un_motif_non_blanc(
    owner: User, reviewer: User, body: Any
) -> None:
    fiche = submitted("mod-motif", "Mod Motif", owner)

    response = decide(reviewer, REJECT, fiche.slug, body)

    assert response.status_code == 400
    assert "review_notes" in response.json()
    assert Entity.objects.get(pk=fiche.pk).status == EntityStatus.SUBMITTED


def test_une_note_de_publication_nulle_est_refusee(owner: User, reviewer: User) -> None:
    fiche = submitted("mod-note-nulle", "Mod Note Nulle", owner)

    response = decide(reviewer, PUBLISH, fiche.slug, {"review_notes": None})

    assert response.status_code == 400
    assert "review_notes" in response.json()
    assert Entity.objects.get(pk=fiche.pk).status == EntityStatus.SUBMITTED


@pytest.mark.parametrize("action", DECISIONS)
@pytest.mark.parametrize(
    "champ",
    ["status", "reviewed_at", "reviewed_by", "submitted_at", "created_by", "name"],
)
def test_un_champ_impose_par_le_serveur_est_refuse(
    owner: User, admin: User, action: str, champ: str
) -> None:
    """Name every refused key instead of dropping it."""
    fiche = submitted("mod-champs", "Mod Champs", owner)

    response = decide(admin, action, fiche.slug, {**VALID_BODY[action], champ: 1})

    assert response.status_code == 400
    assert champ in response.json()
    assert Entity.objects.get(pk=fiche.pk).status == EntityStatus.SUBMITTED


@pytest.mark.parametrize("action", MODERATION_ACTIONS)
@pytest.mark.parametrize("body", [[], "text"], ids=["tableau", "chaine"])
def test_un_corps_json_non_objet_est_refuse(
    owner: User, admin: User, action: str, body: Any
) -> None:
    fiche = record(
        "mod-corps",
        "Mod Corps",
        created_by=owner,
        status=START_STATUS[action],
        submitted_at=timezone.now(),
    )

    response = decide(admin, action, fiche.slug, body)

    assert response.status_code == 400
    assert Entity.objects.get(pk=fiche.pk).status == START_STATUS[action]


def test_la_reouverture_n_accepte_aucune_note(owner: User, admin: User) -> None:
    """Keep the empty-body contract of the four non-decision actions."""
    fiche = record(
        "mod-reouverture-note",
        "Mod Reouverture Note",
        created_by=owner,
        status=EntityStatus.PUBLISHED,
    )

    response = decide(admin, REOPEN, fiche.slug, {"review_notes": "Not here."})

    assert response.status_code == 400
    assert Entity.objects.get(pk=fiche.pk).status == EntityStatus.PUBLISHED


# --- Parcours complet et droits d'écriture ------------------------------


def test_le_parcours_soumission_rejet_reprise_publication_reouverture(
    owner: User, reviewer: User, admin: User
) -> None:
    """Follow one record through the whole editorial loop."""
    fiche = record("mod-parcours", "Mod Parcours", created_by=owner)
    contributeur = api(owner)
    sources = reverse("managed-entity-sources", kwargs={"slug": fiche.slug})
    source_body = {"label": "Synthetic Reference Work", "kind": SourceKind.BOOK}

    assert contributeur.post(action_url(SUBMIT, fiche.slug)).status_code == 200
    assert contributeur.post(sources, source_body, format="json").status_code == 403

    assert (
        decide(reviewer, REJECT, fiche.slug, {"review_notes": REASON}).status_code
        == 200
    )

    rejetee = Entity.objects.get(pk=fiche.pk)
    assert rejetee.status == EntityStatus.REJECTED
    assert rejetee.review_notes == REASON

    # Le rejet rend la main au propriétaire : il reprend, corrige, resoumet.
    assert contributeur.post(action_url(RESUME, fiche.slug)).status_code == 200
    reprise = Entity.objects.get(pk=fiche.pk)
    assert reprise.status == EntityStatus.DRAFT
    assert reprise.review_notes == REASON
    assert (
        contributeur.patch(
            detail_url(fiche.slug), {"category": "Corrected"}, format="json"
        ).status_code
        == 200
    )
    assert contributeur.post(sources, source_body, format="json").status_code == 201

    assert contributeur.post(action_url(SUBMIT, fiche.slug)).status_code == 200
    resoumise = Entity.objects.get(pk=fiche.pk)
    assert resoumise.review_notes == ""
    assert resoumise.reviewed_by_id is None

    assert (
        decide(reviewer, PUBLISH, fiche.slug, {"review_notes": APPROVAL}).status_code
        == 200
    )

    publiee = Entity.objects.get(pk=fiche.pk)
    assert publiee.status == EntityStatus.PUBLISHED
    # Une fiche publiée échappe au contributeur comme au relecteur.
    assert (
        contributeur.patch(
            detail_url(fiche.slug), {"category": "Too late"}, format="json"
        ).status_code
        == 403
    )
    assert (
        api(reviewer)
        .patch(detail_url(fiche.slug), {"category": "Too late"}, format="json")
        .status_code
        == 403
    )
    assert contributeur.post(action_url(WITHDRAW, fiche.slug)).status_code == 400

    assert decide(admin, REOPEN, fiche.slug).status_code == 200

    rouverte = Entity.objects.get(pk=fiche.pk)
    assert rouverte.status == EntityStatus.DRAFT
    assert rouverte.review_notes == APPROVAL
    assert (
        contributeur.patch(
            detail_url(fiche.slug), {"category": "Again"}, format="json"
        ).status_code
        == 200
    )
    assert contributeur.post(action_url(WITHDRAW, fiche.slug)).status_code == 400


def test_la_prochaine_soumission_efface_la_revue_conservee_par_la_reouverture(
    owner: User, reviewer: User, admin: User
) -> None:
    fiche = record(
        "mod-revue-effacee",
        "Mod Revue Effacee",
        created_by=owner,
        status=EntityStatus.PUBLISHED,
        reviewed_at=timezone.now(),
        reviewed_by=reviewer,
        review_notes="Publication note.",
    )

    assert decide(admin, REOPEN, fiche.slug).status_code == 200
    assert api(owner).post(action_url(SUBMIT, fiche.slug)).status_code == 200

    apres = Entity.objects.get(pk=fiche.pk)
    assert apres.review_notes == ""
    assert apres.reviewed_by_id is None
    assert apres.reviewed_at is None


# --- Visibilité publique ------------------------------------------------


def test_la_publication_rend_la_fiche_publique_sans_fuite_de_revue(
    client: Client, owner: User, reviewer: User, admin: User
) -> None:
    """Rely on the existing public selection, and leak no editorial field."""
    masquee = record("mod-cible-masquee", "Mod Cible Masquee")
    fiche = submitted("mod-publique", "Mod Publique", owner)
    fiche.variant_of = masquee
    fiche.save(update_fields=["variant_of"])
    create_relation(fiche, RelationKind.PARENT, to_entity=masquee)
    public_detail = reverse("entity-detail", kwargs={"slug": fiche.slug})
    public_list = reverse("entity-list")

    assert client.get(public_detail).status_code == 404
    assert client.get(public_list).json()["count"] == 0

    assert (
        decide(reviewer, PUBLISH, fiche.slug, {"review_notes": APPROVAL}).status_code
        == 200
    )

    publiee = client.get(public_detail)
    assert publiee.status_code == 200
    assert client.get(public_list).json()["count"] == 1
    corps = publiee.content.decode()
    assert APPROVAL not in corps
    for interdit in ("review_notes", "reviewed_by", "reviewed_at", "status"):
        assert interdit not in publiee.json()
    # La cible non publique reste masquée, et son nom n'est pas recopié.
    assert publiee.json()["variant_of"] is None
    assert publiee.json()["relations"] == []
    assert "Mod Cible Masquee" not in corps

    assert decide(admin, REOPEN, fiche.slug).status_code == 200

    assert client.get(public_detail).status_code == 404
    assert client.get(public_list).json()["count"] == 0


def test_un_rejet_laisse_la_fiche_absente_du_public(
    client: Client, owner: User, reviewer: User
) -> None:
    fiche = submitted("mod-rejet-public", "Mod Rejet Public", owner)

    assert (
        decide(reviewer, REJECT, fiche.slug, {"review_notes": REASON}).status_code
        == 200
    )

    assert (
        client.get(reverse("entity-detail", kwargs={"slug": fiche.slug})).status_code
        == 404
    )
    assert client.get(reverse("entity-list")).json()["count"] == 0


# --- Réévaluation sous verrou -------------------------------------------


def mutate_before_locked_read(monkeypatch: pytest.MonkeyPatch, **changes: Any) -> None:
    """Change the record between the private selection and the locked read.

    That gap is the window a concurrent transaction would use. This is a
    simulation, not a real multithreaded test: it proves the re-read happens,
    not that PostgreSQL serialises two live transactions.
    """

    def change_then_lock(queryset: Any, *args: Any, **kwargs: Any) -> Any:
        Entity.objects.filter(pk=kwargs["pk"]).update(**changes)
        return get_object_or_404(queryset, *args, **kwargs)

    monkeypatch.setattr("mythology.views.get_object_or_404", change_then_lock)


def test_deux_decisions_concurrentes_ne_reussissent_pas_toutes_les_deux(
    owner: User, reviewer: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refuse the second decision on a submission already decided."""
    fiche = submitted("mod-verrou", "Mod Verrou", owner)
    mutate_before_locked_read(monkeypatch, status=EntityStatus.PUBLISHED)

    response = decide(reviewer, PUBLISH, fiche.slug, {"review_notes": APPROVAL})

    assert response.status_code == 400
    assert Entity.objects.get(pk=fiche.pk).reviewed_by_id is None


def test_une_fiche_supprimee_avant_la_lecture_verrouillee_est_masquee(
    owner: User, reviewer: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Recheck visibility when a readable record is deleted before the lock."""
    fiche = submitted("mod-droit", "Mod Droit", owner)
    mutate_before_locked_read(monkeypatch, deleted_at=timezone.now())

    response = decide(reviewer, PUBLISH, fiche.slug)

    assert response.status_code == 404
    assert Entity.objects.get(pk=fiche.pk).reviewed_by_id is None


# --- Les autres méthodes restent fermées --------------------------------


@pytest.mark.parametrize("action", MODERATION_ACTIONS)
@pytest.mark.parametrize("method", ["get", "put", "patch", "delete"])
def test_les_routes_de_moderation_n_acceptent_que_post(
    owner: User, admin: User, action: str, method: str
) -> None:
    fiche = submitted("mod-methodes", "Mod Methodes", owner)

    response = getattr(api(admin), method)(action_url(action, fiche.slug))

    assert response.status_code == 405
