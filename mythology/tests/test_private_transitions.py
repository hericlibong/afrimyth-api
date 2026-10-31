"""Editorial transitions: submit, withdraw and resume.

Covers the three POST actions under `/api/manage/entities/{slug}/`: their
distinct actor rule, the required starting status, the dates and review marks
each one writes, the refusal of any body, and the fact that a submission
suspends the contributor's ordinary writes until it is withdrawn.

The role × ownership × status matrix of the ordinary writes and the JWT
mechanics are proved by their own suites and are not repeated here.
"""

from collections.abc import Iterable
from typing import Any

import pytest
from django.contrib.auth.models import Group
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
from mythology.transitions import RESUME, SUBMIT, WITHDRAW

pytestmark = pytest.mark.django_db

PASSWORD = "synthetic-test-passphrase-7730"

#: Action → statut de départ qui la fait réussir.
START_STATUS = {
    SUBMIT: EntityStatus.DRAFT,
    WITHDRAW: EntityStatus.SUBMITTED,
    RESUME: EntityStatus.REJECTED,
}

ACTIONS = sorted(START_STATUS)


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


def post(user: User, action: str, slug: str, body: Any = None) -> Any:
    client = api(user)
    if body is None:
        return client.post(action_url(action, slug))
    return client.post(action_url(action, slug), body, format="json")


@pytest.fixture
def owner() -> User:
    return account("contributrice-transitions", groups=(CONTRIBUTOR,))


@pytest.fixture
def reviewer() -> User:
    return account("relectrice-transitions", groups=(REVIEWER,))


@pytest.fixture
def admin() -> User:
    return account("administratrice-transitions", groups=(ADMINISTRATOR,))


# --- Les trois transitions réussissent depuis leur statut ---------------


@pytest.mark.parametrize("action", ACTIONS)
def test_chaque_action_part_de_son_statut_et_renvoie_le_detail_prive(
    owner: User, action: str
) -> None:
    """Run the transition and answer with the private detail of the record."""
    fiche = record(
        "tr-depart", "Tr Depart", created_by=owner, status=START_STATUS[action]
    )

    response = post(owner, action, fiche.slug)
    relue = api(owner).get(detail_url(fiche.slug))

    assert response.status_code == 200
    assert response.json() == relue.json()
    attendu = EntityStatus.SUBMITTED if action == SUBMIT else EntityStatus.DRAFT
    assert response.json()["status"] == attendu
    assert Entity.objects.get(pk=fiche.pk).status == attendu


def test_la_soumission_ouvre_une_nouvelle_revue(owner: User, reviewer: User) -> None:
    """Clear the previous decision, so it cannot look like this submission's."""
    fiche = record(
        "tr-resoumise",
        "Tr Resoumise",
        created_by=owner,
        status=EntityStatus.REJECTED,
        reviewed_at=timezone.now(),
        reviewed_by=reviewer,
        review_notes="Earlier rejection note.",
    )

    assert post(owner, RESUME, fiche.slug).status_code == 200

    reprise = Entity.objects.get(pk=fiche.pk)
    assert reprise.status == EntityStatus.DRAFT
    assert reprise.submitted_at is None
    assert reprise.review_notes == "Earlier rejection note."
    assert reprise.reviewed_by_id == reviewer.pk
    assert reprise.reviewed_at is not None

    assert post(owner, SUBMIT, fiche.slug).status_code == 200

    resoumise = Entity.objects.get(pk=fiche.pk)
    assert resoumise.submitted_at is not None
    assert resoumise.review_notes == ""
    assert resoumise.reviewed_by_id is None
    assert resoumise.reviewed_at is None


def test_le_retrait_n_est_pas_un_rejet(owner: User, reviewer: User) -> None:
    """Keep the review marks untouched when a submission is withdrawn."""
    revue = timezone.now()
    fiche = record(
        "tr-retiree",
        "Tr Retiree",
        created_by=owner,
        status=EntityStatus.SUBMITTED,
        submitted_at=timezone.now(),
        reviewed_at=revue,
        reviewed_by=reviewer,
        review_notes="Kept note.",
    )

    response = post(owner, WITHDRAW, fiche.slug)

    assert response.status_code == 200
    fiche.refresh_from_db()
    assert fiche.status == EntityStatus.DRAFT
    assert fiche.submitted_at is None
    assert fiche.reviewed_at == revue
    assert fiche.reviewed_by_id == reviewer.pk
    assert fiche.review_notes == "Kept note."


@pytest.mark.parametrize("action", ACTIONS)
def test_seul_l_etat_editorial_est_ecrit(owner: User, action: str) -> None:
    """Leave the owner, the type, the business fields and the profile alone."""
    fiche = record(
        "tr-intacte",
        "Tr Intacte",
        created_by=owner,
        status=START_STATUS[action],
        category="Kept subtitle",
        characteristics=["Kept trait"],
    )
    avant = Entity.objects.get(pk=fiche.pk)

    assert post(owner, action, fiche.slug).status_code == 200

    apres = Entity.objects.get(pk=fiche.pk)
    assert apres.category == "Kept subtitle"
    assert apres.characteristics == ["Kept trait"]
    assert apres.created_by_id == owner.pk
    assert apres.entity_type == avant.entity_type
    assert apres.created_at == avant.created_at
    assert apres.deleted_at is None
    assert apres.updated_at > avant.updated_at
    assert apres.divinity_profile is not None


# --- Droits distincts de ceux du PATCH ----------------------------------


def test_le_proprietaire_retire_sa_fiche_soumise_que_le_patch_lui_refuse(
    owner: User,
) -> None:
    """Separate the transition right from the ordinary update right.

    This is the case `is_privately_editable()` refuses on purpose, so it must
    not be the rule deciding a withdrawal.
    """
    fiche = record(
        "tr-soumise",
        "Tr Soumise",
        created_by=owner,
        status=EntityStatus.SUBMITTED,
        submitted_at=timezone.now(),
    )
    client = api(owner)

    patch = client.patch(detail_url(fiche.slug), {"category": "x"}, format="json")
    retrait = client.post(action_url(WITHDRAW, fiche.slug))

    assert patch.status_code == 403
    assert retrait.status_code == 200


@pytest.mark.parametrize("action", ACTIONS)
def test_le_relecteur_et_l_administrateur_agissent_sur_une_fiche_sans_proprietaire(
    reviewer: User, admin: User, action: str
) -> None:
    for acteur, slug in ((reviewer, "tr-orpheline-a"), (admin, "tr-orpheline-b")):
        fiche = record(slug, slug.title(), status=START_STATUS[action])

        assert post(acteur, action, fiche.slug).status_code == 200, slug


@pytest.mark.parametrize("action", ACTIONS)
def test_un_contributeur_etranger_est_refuse_en_403_sur_une_fiche_lisible(
    owner: User, action: str
) -> None:
    """Refuse a contributor that is not the record's owner, without a 404."""
    autre = account(f"contributeur-b-{action}", groups=(CONTRIBUTOR,))
    # Une fiche publiée est lisible par tout contributeur : le refus porte donc
    # bien sur l'acteur, pas sur la sélection privée.
    fiche = record(
        "tr-publiee", "Tr Publiee", created_by=owner, status=EntityStatus.PUBLISHED
    )

    response = post(autre, action, fiche.slug)

    assert response.status_code == 403
    assert Entity.objects.get(pk=fiche.pk).status == EntityStatus.PUBLISHED


@pytest.mark.parametrize("action", ACTIONS)
def test_la_fiche_d_un_autre_contributeur_reste_masquee_en_404(
    owner: User, action: str
) -> None:
    autre = account(f"contributeur-c-{action}", groups=(CONTRIBUTOR,))
    fiche = record(
        "tr-masquee",
        "Tr Masquee",
        created_by=autre,
        status=START_STATUS[action],
    )

    response = post(owner, action, fiche.slug)

    assert response.status_code == 404
    assert "Tr Masquee" not in response.content.decode()
    assert Entity.objects.get(pk=fiche.pk).status == START_STATUS[action]


def test_une_fiche_supprimee_inconnue_ou_interdite_donne_le_meme_404(
    owner: User, admin: User
) -> None:
    """Never let a refusal reveal that a record exists, deleted included."""
    supprimee = record(
        "tr-supprimee",
        "Tr Supprimee",
        created_by=owner,
        status=EntityStatus.DRAFT,
        deleted_at=timezone.now(),
    )

    par_admin = post(admin, SUBMIT, supprimee.slug)
    par_proprietaire = post(owner, SUBMIT, supprimee.slug)
    inconnue = post(owner, SUBMIT, "jamais-vue")

    assert par_admin.status_code == 404
    assert par_proprietaire.status_code == inconnue.status_code == 404
    assert par_admin.json() == par_proprietaire.json() == inconnue.json()
    assert Entity.objects.get(pk=supprimee.pk).status == EntityStatus.DRAFT


def test_un_appelant_anonyme_est_refuse_en_401(owner: User) -> None:
    fiche = record("tr-anonyme", "Tr Anonyme", created_by=owner)

    assert api().post(action_url(SUBMIT, fiche.slug)).status_code == 401
    assert Entity.objects.get(pk=fiche.pk).status == EntityStatus.DRAFT


def test_un_compte_sans_role_metier_est_refuse_en_403(owner: User) -> None:
    fiche = record("tr-sans-role", "Tr Sans Role", created_by=owner)
    client = api(account("staff-seul-transitions", is_staff=True))

    assert client.post(action_url(SUBMIT, fiche.slug)).status_code == 403


def test_un_superutilisateur_sans_groupe_agit_comme_administrateur(
    owner: User,
) -> None:
    root = account("secours-transitions", is_staff=True, is_superuser=True)
    fiche = record(
        "tr-secours",
        "Tr Secours",
        created_by=owner,
        status=EntityStatus.SUBMITTED,
        submitted_at=timezone.now(),
    )

    assert post(root, WITHDRAW, fiche.slug).status_code == 200


# --- Statuts de départ interdits ----------------------------------------


@pytest.mark.parametrize(
    ("action", "statut"),
    [
        (action, statut)
        for action in ACTIONS
        for statut in sorted(EntityStatus.values)
        if statut != START_STATUS[action]
    ],
)
def test_un_statut_de_depart_interdit_est_refuse_sans_mutation(
    owner: User, action: str, statut: str
) -> None:
    """Accept exactly one starting status per action, and change nothing else."""
    fiche = record(
        "tr-statuts",
        "Tr Statuts",
        created_by=owner,
        status=statut,
        submitted_at=timezone.now() if statut == EntityStatus.SUBMITTED else None,
    )
    avant = Entity.objects.get(pk=fiche.pk)

    response = post(owner, action, fiche.slug)

    assert response.status_code == 400
    apres = Entity.objects.get(pk=fiche.pk)
    assert apres.status == statut
    assert apres.submitted_at == avant.submitted_at
    assert apres.updated_at == avant.updated_at


def test_une_action_repetee_est_refusee_sans_nouvelle_date(owner: User) -> None:
    """Refuse the second call on the starting status, leaving the date as is."""
    fiche = record("tr-repetee", "Tr Repetee", created_by=owner)

    premiere = post(owner, SUBMIT, fiche.slug)
    fiche.refresh_from_db()
    datee = fiche.submitted_at
    seconde = post(owner, SUBMIT, fiche.slug)

    assert premiere.status_code == 200
    assert seconde.status_code == 400
    fiche.refresh_from_db()
    assert fiche.submitted_at == datee
    assert fiche.status == EntityStatus.SUBMITTED


# --- Le corps est refusé ------------------------------------------------


@pytest.mark.parametrize("action", ACTIONS)
def test_un_objet_json_vide_est_accepte(owner: User, action: str) -> None:
    fiche = record(
        "tr-corps-vide",
        "Tr Corps Vide",
        created_by=owner,
        status=START_STATUS[action],
    )

    assert post(owner, action, fiche.slug, {}).status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"status": "published"},
        {"submitted_at": "2026-10-30T09:00:00Z"},
        {"review_notes": "Injected note."},
        {"unexpected": 1},
        [],
        "text",
    ],
    ids=["statut", "date", "note", "inconnu", "tableau", "chaine"],
)
def test_un_corps_non_vide_est_refuse_sans_mutation(owner: User, body: Any) -> None:
    """Refuse any payload rather than ignoring it."""
    fiche = record("tr-corps", "Tr Corps", created_by=owner)

    response = post(owner, SUBMIT, fiche.slug, body)

    assert response.status_code == 400
    apres = Entity.objects.get(pk=fiche.pk)
    assert apres.status == EntityStatus.DRAFT
    assert apres.submitted_at is None
    assert apres.review_notes == ""


def test_le_corps_est_examine_apres_le_statut_de_depart(owner: User) -> None:
    """Keep the documented order: the starting status is reported first."""
    fiche = record(
        "tr-ordre", "Tr Ordre", created_by=owner, status=EntityStatus.PUBLISHED
    )

    response = post(owner, SUBMIT, fiche.slug, {"status": "draft"})

    assert response.status_code == 400
    assert "currently 'published'" in str(response.json())


# --- Lecture filtrée de la réponse --------------------------------------


def test_la_reponse_filtre_les_references_selon_l_appelant(
    owner: User, reviewer: User
) -> None:
    """Render the private detail with the caller's own reference rule."""
    masquee = record("tr-cible-masquee", "Tr Cible Masquee")
    fiche = record("tr-references", "Tr References", created_by=owner)
    fiche.variant_of = masquee
    fiche.save(update_fields=["variant_of"])
    create_relation(fiche, RelationKind.PARENT, to_entity=masquee)

    par_proprietaire = post(owner, SUBMIT, fiche.slug)
    par_relecteur = post(reviewer, WITHDRAW, fiche.slug)

    assert par_proprietaire.json()["variant_of"] is None
    assert par_proprietaire.json()["relations"] == []
    assert "Tr Cible Masquee" not in par_proprietaire.content.decode()
    assert par_relecteur.json()["variant_of"]["slug"] == "tr-cible-masquee"
    assert len(par_relecteur.json()["relations"]) == 1


# --- Soumission, écritures suspendues, retrait --------------------------


def test_la_soumission_suspend_les_ecritures_du_contributeur_et_le_retrait_les_rend(
    owner: User,
) -> None:
    """Follow one record through submit, the refusals, then withdraw."""
    fiche = record("tr-parcours", "Tr Parcours", created_by=owner)
    client = api(owner)
    sources = reverse("managed-entity-sources", kwargs={"slug": fiche.slug})
    relations = reverse("managed-entity-relations", kwargs={"slug": fiche.slug})
    source_body = {"label": "Synthetic Reference Work", "kind": SourceKind.BOOK}
    relation_body = {"kind": RelationKind.ALLY, "to_name": "Cited Figure"}

    assert (
        client.patch(
            detail_url(fiche.slug), {"category": "Before"}, format="json"
        ).status_code
        == 200
    )
    assert client.post(sources, source_body, format="json").status_code == 201

    assert client.post(action_url(SUBMIT, fiche.slug)).status_code == 200

    assert (
        client.patch(
            detail_url(fiche.slug), {"category": "During"}, format="json"
        ).status_code
        == 403
    )
    assert client.post(sources, source_body, format="json").status_code == 403
    assert client.post(relations, relation_body, format="json").status_code == 403
    assert client.get(detail_url(fiche.slug)).status_code == 200
    assert Entity.objects.get(pk=fiche.pk).category == "Before"

    assert client.post(action_url(WITHDRAW, fiche.slug)).status_code == 200

    assert (
        client.patch(
            detail_url(fiche.slug), {"category": "After"}, format="json"
        ).status_code
        == 200
    )
    assert client.post(relations, relation_body, format="json").status_code == 201


def test_un_relecteur_garde_ses_ecritures_sur_une_fiche_soumise(
    owner: User, reviewer: User
) -> None:
    fiche = record("tr-relecteur", "Tr Relecteur", created_by=owner)

    assert post(owner, SUBMIT, fiche.slug).status_code == 200

    response = api(reviewer).patch(
        detail_url(fiche.slug), {"category": "Reviewed"}, format="json"
    )

    assert response.status_code == 200


# --- Réévaluation sous verrou -------------------------------------------


def mutate_before_locked_read(monkeypatch: pytest.MonkeyPatch, **changes: Any) -> None:
    """Change the record between the private selection and the locked read.

    That gap is exactly the window a concurrent transaction would use, so
    patching the locked fetch is what makes the re-evaluation observable.
    """

    def change_then_lock(queryset: Any, *args: Any, **kwargs: Any) -> Any:
        Entity.objects.filter(pk=kwargs["pk"]).update(**changes)
        return get_object_or_404(queryset, *args, **kwargs)

    monkeypatch.setattr("mythology.views.get_object_or_404", change_then_lock)


def test_le_statut_est_relu_sur_la_ligne_verrouillee(
    owner: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refuse the second of two concurrent submissions."""
    fiche = record("tr-verrou", "Tr Verrou", created_by=owner)
    mutate_before_locked_read(monkeypatch, status=EntityStatus.SUBMITTED)

    response = post(owner, SUBMIT, fiche.slug)

    assert response.status_code == 400
    assert Entity.objects.get(pk=fiche.pk).submitted_at is None


def test_le_droit_de_l_acteur_est_relu_sur_la_ligne_verrouillee(
    owner: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refuse the actor whose record changed hands and got published meanwhile.

    The record stays readable — it is published — so the refusal comes from
    the actor rule re-read on the locked row, not from the private selection.
    """
    fiche = record("tr-droit", "Tr Droit", created_by=owner)
    autre = account("contributeur-d-transitions", groups=(CONTRIBUTOR,))
    mutate_before_locked_read(
        monkeypatch, created_by=autre, status=EntityStatus.PUBLISHED
    )

    response = post(owner, SUBMIT, fiche.slug)

    assert response.status_code == 403
    # La mutation simulée vit dans la transaction de la requête : son annulation
    # fait partie du résultat attendu. Seule l'absence de transition compte.
    apres = Entity.objects.get(pk=fiche.pk)
    assert apres.status != EntityStatus.SUBMITTED
    assert apres.submitted_at is None


# --- Les autres méthodes restent fermées --------------------------------


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("method", ["get", "put", "patch", "delete"])
def test_les_routes_de_transition_n_acceptent_que_post(
    owner: User, action: str, method: str
) -> None:
    fiche = record("tr-methodes", "Tr Methodes", created_by=owner)

    response = getattr(api(owner), method)(action_url(action, fiche.slug))

    assert response.status_code == 405
