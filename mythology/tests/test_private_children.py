"""Private editorial writes on a record's documentary sources and relations.

Covers the six nested routes under `/api/manage/entities/{slug}/`: the
POST/PATCH/DELETE journey of both children, the input contracts, the target
rules of a relation, the lookup inside the parent, and the fact that the
parent record itself is never touched.

The role × ownership × status matrix is proved once in `test_private_update.py`
and only sampled here, since the same `is_privately_editable` decides both.
Accounts and records are synthetic.
"""

from collections.abc import Iterable
from datetime import date
from typing import Any
from uuid import uuid4

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from accounts.roles import ADMINISTRATOR, CONTRIBUTOR, REVIEWER
from mythology.models import (
    Entity,
    EntityRelation,
    EntityStatus,
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

PASSWORD = "synthetic-test-passphrase-5128"


def sources_url(slug: str) -> str:
    return reverse("managed-entity-sources", kwargs={"slug": slug})


def source_url(slug: str, source_id: int) -> str:
    return reverse(
        "managed-entity-source-detail",
        kwargs={"slug": slug, "source_id": source_id},
    )


def relations_url(slug: str) -> str:
    return reverse("managed-entity-relations", kwargs={"slug": slug})


def relation_url(slug: str, relation_id: int) -> str:
    return reverse(
        "managed-entity-relation-detail",
        kwargs={"slug": slug, "relation_id": relation_id},
    )


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
    return account("contributrice-enfants", groups=(CONTRIBUTOR,))


@pytest.fixture
def fiche(owner: User) -> Entity:
    """The owned draft every happy path writes on."""
    return record("enf-brouillon", "Enf Brouillon", created_by=owner)


@pytest.fixture
def cible(owner: User) -> Entity:
    """A published figure every caller may read, usable as a relation target."""
    return record("enf-cible", "Enf Cible", status=EntityStatus.PUBLISHED)


SOURCE_BODY = {"label": "Synthetic Reference Work", "kind": SourceKind.BOOK}


# --- Parcours des sources -----------------------------------------------


def test_le_parcours_complet_d_une_source(owner: User, fiche: Entity) -> None:
    """Create, read back, update and delete one documentary source."""
    client = api(owner)

    cree = client.post(sources_url(fiche.slug), SOURCE_BODY, format="json")

    assert cree.status_code == 201
    assert set(cree.json()) == {"id", "label", "kind", "url", "accessed_at", "notes"}
    identifiant = cree.json()["id"]

    detail = client.get(reverse("managed-entity-detail", kwargs={"slug": fiche.slug}))
    assert [source["id"] for source in detail.json()["sources"]] == [identifiant]

    modifiee = client.patch(
        source_url(fiche.slug, identifiant),
        {"notes": "Revised note.", "accessed_at": "2026-10-30"},
        format="json",
    )

    assert modifiee.status_code == 200
    source = Source.objects.get(pk=identifiant)
    assert source.notes == "Revised note."
    assert source.accessed_at == date(2026, 10, 30)
    assert source.label == "Synthetic Reference Work"

    supprimee = client.delete(source_url(fiche.slug, identifiant))

    assert supprimee.status_code == 204
    assert supprimee.content == b""
    assert Source.objects.count() == 0
    assert Entity.objects.filter(pk=fiche.pk).exists()


@pytest.mark.parametrize("champ", ["label", "kind"])
def test_la_creation_d_une_source_exige_label_et_kind(
    owner: User, fiche: Entity, champ: str
) -> None:
    body = dict(SOURCE_BODY)
    del body[champ]

    response = api(owner).post(sources_url(fiche.slug), body, format="json")

    assert response.status_code == 400
    assert champ in response.json()
    assert Source.objects.count() == 0


@pytest.mark.parametrize(
    ("champ", "valeur"),
    [
        ("label", "   "),
        ("kind", "pamphlet"),
        ("url", "pas-une-url"),
        ("accessed_at", "30/10/2026"),
        ("label", ""),
    ],
)
def test_les_validations_du_modele_source_sont_appliquees(
    owner: User, fiche: Entity, champ: str, valeur: Any
) -> None:
    """Reuse the model and field validation rather than restating it."""
    body = {**SOURCE_BODY, champ: valeur}

    response = api(owner).post(sources_url(fiche.slug), body, format="json")

    assert response.status_code == 400
    assert champ in response.json()
    assert Source.objects.count() == 0


def test_une_source_accepte_les_valeurs_vides_que_le_modele_permet(
    owner: User, fiche: Entity
) -> None:
    response = api(owner).post(
        sources_url(fiche.slug),
        {**SOURCE_BODY, "url": "", "notes": "", "accessed_at": None},
        format="json",
    )

    assert response.status_code == 201
    source = Source.objects.get()
    assert source.url == ""
    assert source.accessed_at is None


def test_un_patch_de_source_conserve_les_champs_omis(
    owner: User, fiche: Entity
) -> None:
    source = create_source(fiche, label="Kept Label", notes="Kept note.")

    response = api(owner).patch(
        source_url(fiche.slug, source.pk),
        {"url": "https://example.test/"},
        format="json",
    )

    assert response.status_code == 200
    source.refresh_from_db()
    assert source.url == "https://example.test/"
    assert source.label == "Kept Label"
    assert source.notes == "Kept note."


def test_un_patch_de_source_refuse_un_label_vide(owner: User, fiche: Entity) -> None:
    source = create_source(fiche, label="Kept Label")

    response = api(owner).patch(
        source_url(fiche.slug, source.pk), {"label": ""}, format="json"
    )

    assert response.status_code == 400
    assert "label" in response.json()
    assert Source.objects.get(pk=source.pk).label == "Kept Label"


def test_les_sources_en_double_sont_permises(owner: User, fiche: Entity) -> None:
    """Keep the existing decision: a reference may be recorded twice."""
    client = api(owner)

    premiere = client.post(sources_url(fiche.slug), SOURCE_BODY, format="json")
    seconde = client.post(sources_url(fiche.slug), SOURCE_BODY, format="json")

    assert premiere.status_code == seconde.status_code == 201
    assert Source.objects.filter(entity=fiche).count() == 2


# --- Parcours des relations ---------------------------------------------


def test_le_parcours_complet_d_une_relation(
    owner: User, fiche: Entity, cible: Entity
) -> None:
    """Create, read back, update and delete one outgoing relation."""
    client = api(owner)

    cree = client.post(
        relations_url(fiche.slug),
        {"kind": RelationKind.PARENT, "to_entity": str(cible.pk)},
        format="json",
    )

    assert cree.status_code == 201
    assert set(cree.json()) == {"id", "kind", "to_entity", "to_name", "notes"}
    assert cree.json()["to_entity"]["slug"] == cible.slug
    identifiant = cree.json()["id"]

    detail = client.get(reverse("managed-entity-detail", kwargs={"slug": fiche.slug}))
    assert [link["id"] for link in detail.json()["relations"]] == [identifiant]

    modifiee = client.patch(
        relation_url(fiche.slug, identifiant),
        {"notes": "Revised note."},
        format="json",
    )

    assert modifiee.status_code == 200
    assert EntityRelation.objects.get(pk=identifiant).notes == "Revised note."

    supprimee = client.delete(relation_url(fiche.slug, identifiant))

    assert supprimee.status_code == 204
    assert EntityRelation.objects.count() == 0
    assert Entity.objects.filter(pk=cible.pk).exists()
    assert Entity.objects.filter(pk=fiche.pk).exists()


def test_une_relation_peut_citer_un_nom_sans_fiche(owner: User, fiche: Entity) -> None:
    response = api(owner).post(
        relations_url(fiche.slug),
        {"kind": RelationKind.ALLY, "to_name": "Figure Without A Record"},
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["to_entity"] is None
    relation = EntityRelation.objects.get()
    assert relation.to_name == "Figure Without A Record"
    assert relation.from_entity_id == fiche.pk


@pytest.mark.parametrize(
    "body",
    [
        {"kind": RelationKind.PARENT},
        {"kind": RelationKind.PARENT, "to_name": "   "},
        {"kind": RelationKind.PARENT, "to_name": "", "to_entity": None},
    ],
    ids=["aucune-cible", "nom-blanc", "deux-formes-vides"],
)
def test_une_relation_sans_cible_est_refusee(
    owner: User, fiche: Entity, body: dict[str, Any]
) -> None:
    response = api(owner).post(relations_url(fiche.slug), body, format="json")

    assert response.status_code == 400
    assert EntityRelation.objects.count() == 0


def test_une_relation_avec_deux_cibles_est_refusee(
    owner: User, fiche: Entity, cible: Entity
) -> None:
    response = api(owner).post(
        relations_url(fiche.slug),
        {
            "kind": RelationKind.PARENT,
            "to_entity": str(cible.pk),
            "to_name": "Figure Without A Record",
        },
        format="json",
    )

    assert response.status_code == 400
    assert EntityRelation.objects.count() == 0


def test_le_kind_est_exige_et_valide(owner: User, fiche: Entity) -> None:
    client = api(owner)

    absent = client.post(relations_url(fiche.slug), {"to_name": "Cited"}, format="json")
    inconnu = client.post(
        relations_url(fiche.slug),
        {"kind": "nemesis", "to_name": "Cited"},
        format="json",
    )

    assert absent.status_code == inconnu.status_code == 400
    assert "kind" in absent.json()
    assert "kind" in inconnu.json()


def test_une_auto_relation_est_refusee(owner: User, fiche: Entity) -> None:
    response = api(owner).post(
        relations_url(fiche.slug),
        {"kind": RelationKind.CONSORT, "to_entity": str(fiche.pk)},
        format="json",
    )

    assert response.status_code == 400
    assert EntityRelation.objects.count() == 0


def test_les_cibles_interdites_supprimees_et_inexistantes_sont_indistinctes(
    owner: User, fiche: Entity
) -> None:
    """Refuse an unreadable, a deleted and an unknown target identically."""
    autre = account("contributeur-b-enfants", groups=(CONTRIBUTOR,))
    interdite = record("enf-interdite", "Enf Interdite", created_by=autre)
    supprimee = record(
        "enf-supprimee",
        "Enf Supprimee",
        status=EntityStatus.PUBLISHED,
        deleted_at=timezone.now(),
    )
    client = api(owner)

    refus = [
        client.post(
            relations_url(fiche.slug),
            {"kind": RelationKind.PARENT, "to_entity": str(pk)},
            format="json",
        )
        for pk in (interdite.pk, supprimee.pk, uuid4())
    ]

    assert [reponse.status_code for reponse in refus] == [400, 400, 400]
    corps = [reponse.json() for reponse in refus]
    assert corps[0] == corps[1] == corps[2]
    assert "Enf Interdite" not in str(corps[0])
    assert str(interdite.pk) not in str(corps[0])
    assert EntityRelation.objects.count() == 0


def test_une_cible_lisible_mais_non_modifiable_est_acceptee(
    owner: User, fiche: Entity, cible: Entity
) -> None:
    """Reading the target is enough; modifying it is not required."""
    response = api(owner).post(
        relations_url(fiche.slug),
        {"kind": RelationKind.ENEMY, "to_entity": str(cible.pk)},
        format="json",
    )

    assert response.status_code == 201
    assert cible.status == EntityStatus.PUBLISHED


def test_un_nom_cite_est_resolu_explicitement(
    owner: User, fiche: Entity, cible: Entity
) -> None:
    """Switching target forms takes both keys in one request."""
    relation = create_relation(fiche, RelationKind.PARENT, to_name="Cited Figure")
    client = api(owner)

    sans_vider = client.patch(
        relation_url(fiche.slug, relation.pk),
        {"to_entity": str(cible.pk)},
        format="json",
    )

    assert sans_vider.status_code == 400
    assert EntityRelation.objects.get(pk=relation.pk).to_entity_id is None

    resolue = client.patch(
        relation_url(fiche.slug, relation.pk),
        {"to_entity": str(cible.pk), "to_name": ""},
        format="json",
    )

    assert resolue.status_code == 200
    relation.refresh_from_db()
    assert relation.to_entity_id == cible.pk
    assert relation.to_name == ""


def test_une_cible_resolue_peut_redevenir_un_nom(
    owner: User, fiche: Entity, cible: Entity
) -> None:
    relation = create_relation(fiche, RelationKind.CHILD, to_entity=cible)

    response = api(owner).patch(
        relation_url(fiche.slug, relation.pk),
        {"to_entity": None, "to_name": "Cited Instead"},
        format="json",
    )

    assert response.status_code == 200
    relation.refresh_from_db()
    assert relation.to_entity_id is None
    assert relation.to_name == "Cited Instead"


def test_un_patch_de_relation_conserve_le_champ_omis(
    owner: User, fiche: Entity, cible: Entity
) -> None:
    relation = create_relation(fiche, RelationKind.ALLY, to_entity=cible)

    response = api(owner).patch(
        relation_url(fiche.slug, relation.pk),
        {"kind": RelationKind.ENEMY},
        format="json",
    )

    assert response.status_code == 200
    relation.refresh_from_db()
    assert relation.kind == RelationKind.ENEMY
    assert relation.to_entity_id == cible.pk


def test_un_triplet_en_double_est_refuse(
    owner: User, fiche: Entity, cible: Entity
) -> None:
    """Keep the existing uniqueness of a relation triple."""
    create_relation(fiche, RelationKind.PARENT, to_entity=cible)

    response = api(owner).post(
        relations_url(fiche.slug),
        {"kind": RelationKind.PARENT, "to_entity": str(cible.pk)},
        format="json",
    )

    assert response.status_code == 400
    assert EntityRelation.objects.count() == 1


def test_un_autre_kind_vers_la_meme_cible_est_accepte(
    owner: User, fiche: Entity, cible: Entity
) -> None:
    create_relation(fiche, RelationKind.PARENT, to_entity=cible)

    response = api(owner).post(
        relations_url(fiche.slug),
        {"kind": RelationKind.ALLY, "to_entity": str(cible.pk)},
        format="json",
    )

    assert response.status_code == 201


def test_un_patch_ne_conflit_pas_avec_la_relation_elle_meme(
    owner: User, fiche: Entity, cible: Entity
) -> None:
    """Never let a relation collide with itself when it is updated."""
    relation = create_relation(fiche, RelationKind.PARENT, to_entity=cible)

    response = api(owner).patch(
        relation_url(fiche.slug, relation.pk),
        {"kind": RelationKind.PARENT, "notes": "Revised note."},
        format="json",
    )

    assert response.status_code == 200


def test_un_patch_vers_un_triplet_existant_est_refuse(
    owner: User, fiche: Entity, cible: Entity
) -> None:
    create_relation(fiche, RelationKind.PARENT, to_entity=cible)
    relation = create_relation(fiche, RelationKind.ALLY, to_entity=cible)

    response = api(owner).patch(
        relation_url(fiche.slug, relation.pk),
        {"kind": RelationKind.PARENT},
        format="json",
    )

    assert response.status_code == 400
    assert EntityRelation.objects.get(pk=relation.pk).kind == RelationKind.ALLY


def test_le_sens_oriente_du_lien_est_conserve(
    owner: User, fiche: Entity, cible: Entity
) -> None:
    """Write exactly one row, in the direction given, with no reciprocal."""
    response = api(owner).post(
        relations_url(fiche.slug),
        {"kind": RelationKind.PARENT, "to_entity": str(cible.pk)},
        format="json",
    )

    assert response.status_code == 201
    assert EntityRelation.objects.count() == 1
    relation = EntityRelation.objects.get()
    assert relation.from_entity_id == fiche.pk
    assert relation.to_entity_id == cible.pk
    assert not EntityRelation.objects.filter(from_entity=cible).exists()


# --- Le parent vient de l'URL -------------------------------------------


@pytest.mark.parametrize("champ", ["id", "entity", "entity_id", "label_typo"])
def test_une_cle_imposee_ou_inconnue_est_refusee_sur_une_source(
    owner: User, fiche: Entity, champ: str
) -> None:
    response = api(owner).post(
        sources_url(fiche.slug), {**SOURCE_BODY, champ: 1}, format="json"
    )

    assert response.status_code == 400
    assert champ in response.json()
    assert Source.objects.count() == 0


@pytest.mark.parametrize(
    "champ", ["id", "entity", "from_entity", "from_entity_id", "to_entity_id", "kynd"]
)
def test_une_cle_imposee_ou_inconnue_est_refusee_sur_une_relation(
    owner: User, fiche: Entity, champ: str
) -> None:
    response = api(owner).post(
        relations_url(fiche.slug),
        {"kind": RelationKind.PARENT, "to_name": "Cited", champ: 1},
        format="json",
    )

    assert response.status_code == 400
    assert champ in response.json()
    assert EntityRelation.objects.count() == 0


def test_un_enfant_est_rattache_a_la_fiche_de_l_url(owner: User, fiche: Entity) -> None:
    autre = record("enf-autre", "Enf Autre", created_by=owner)

    response = api(owner).post(sources_url(autre.slug), SOURCE_BODY, format="json")

    assert response.status_code == 201
    assert Source.objects.get().entity_id == autre.pk
    assert not Source.objects.filter(entity=fiche).exists()


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_un_enfant_d_une_autre_fiche_donne_404(
    owner: User, fiche: Entity, method: str
) -> None:
    """Look the child up inside the parent, never by its identifier alone."""
    autre = record("enf-voisine", "Enf Voisine", created_by=owner)
    source = create_source(autre, label="Belongs Elsewhere")
    client = api(owner)

    etrangere = getattr(client, method)(
        source_url(fiche.slug, source.pk), {"notes": "x"}, format="json"
    )
    inexistante = getattr(client, method)(
        source_url(fiche.slug, 999999), {"notes": "x"}, format="json"
    )

    assert etrangere.status_code == inexistante.status_code == 404
    assert etrangere.json() == inexistante.json()
    assert Source.objects.filter(pk=source.pk).exists()


def test_une_relation_vers_une_cible_masquee_reste_inaccessible(
    owner: User, fiche: Entity
) -> None:
    """Keep the read filter on relations: a hidden target hides its link."""
    autre = account("contributeur-c-enfants", groups=(CONTRIBUTOR,))
    masquee = record("enf-masquee", "Enf Masquee", created_by=autre)
    relation = create_relation(fiche, RelationKind.PARENT, to_entity=masquee)
    client = api(owner)

    modifiee = client.patch(
        relation_url(fiche.slug, relation.pk), {"notes": "x"}, format="json"
    )
    supprimee = client.delete(relation_url(fiche.slug, relation.pk))

    assert modifiee.status_code == supprimee.status_code == 404
    assert "Enf Masquee" not in modifiee.content.decode()
    assert EntityRelation.objects.filter(pk=relation.pk).exists()


# --- Droits de la fiche porteuse ----------------------------------------


@pytest.mark.parametrize(
    ("role", "statut", "attendu"),
    [
        ("owner", EntityStatus.DRAFT, 201),
        ("owner", EntityStatus.REJECTED, 201),
        ("owner", EntityStatus.SUBMITTED, 403),
        ("owner", EntityStatus.PUBLISHED, 403),
        ("reviewer", EntityStatus.SUBMITTED, 201),
        ("reviewer", EntityStatus.PUBLISHED, 403),
        ("admin", EntityStatus.PUBLISHED, 201),
    ],
)
def test_les_ecritures_d_enfants_suivent_le_droit_de_modifier_le_parent(
    owner: User, role: str, statut: str, attendu: int
) -> None:
    """Reuse the parent's update right rather than defining a second matrix."""
    fiche = record("enf-droits", "Enf Droits", created_by=owner, status=statut)
    caller = owner
    if role == "reviewer":
        caller = account(f"relectrice-{statut}", groups=(REVIEWER,))
    elif role == "admin":
        caller = account(f"administratrice-{statut}", groups=(ADMINISTRATOR,))

    response = api(caller).post(sources_url(fiche.slug), SOURCE_BODY, format="json")

    assert response.status_code == attendu
    assert Source.objects.count() == (1 if attendu == 201 else 0)


def test_un_parent_non_lisible_supprime_ou_inconnu_donne_le_meme_404(
    owner: User,
) -> None:
    autre = account("contributeur-d-enfants", groups=(CONTRIBUTOR,))
    interdite = record("enf-interdite-parent", "Enf Interdite Parent", created_by=autre)
    supprimee = record(
        "enf-supprimee-parent",
        "Enf Supprimee Parent",
        created_by=owner,
        deleted_at=timezone.now(),
    )
    client = api(owner)

    refus = [
        client.post(sources_url(slug), SOURCE_BODY, format="json")
        for slug in (interdite.slug, supprimee.slug, "jamais-vue")
    ]

    assert [reponse.status_code for reponse in refus] == [404, 404, 404]
    assert refus[0].json() == refus[1].json() == refus[2].json()
    assert Source.objects.count() == 0


def test_un_appelant_anonyme_est_refuse_en_401(fiche: Entity) -> None:
    assert api().post(sources_url(fiche.slug), SOURCE_BODY).status_code == 401
    assert api().delete(relations_url(fiche.slug)).status_code == 401


def test_un_compte_sans_role_metier_est_refuse_en_403(fiche: Entity) -> None:
    client = api(account("sans-role-enfants", is_staff=True))

    assert client.post(sources_url(fiche.slug), SOURCE_BODY).status_code == 403


# --- Le parent reste intact ---------------------------------------------


def test_une_ecriture_d_enfant_ne_touche_pas_la_fiche(
    owner: User, fiche: Entity, cible: Entity
) -> None:
    """Leave the record's own columns, `updated_at` included, as they were."""
    avant = Entity.objects.get(pk=fiche.pk)
    client = api(owner)

    client.post(sources_url(fiche.slug), SOURCE_BODY, format="json")
    client.post(
        relations_url(fiche.slug),
        {"kind": RelationKind.PARENT, "to_entity": str(cible.pk)},
        format="json",
    )

    apres = Entity.objects.get(pk=fiche.pk)
    assert apres.updated_at == avant.updated_at
    assert apres.status == avant.status
    assert apres.created_by_id == avant.created_by_id
    assert apres.entity_type == avant.entity_type


def test_la_suppression_d_un_enfant_ne_supprime_rien_d_autre(
    owner: User, fiche: Entity, cible: Entity
) -> None:
    source = create_source(fiche, label="Removed Reference")
    gardee = create_source(fiche, label="Kept Reference")
    relation = create_relation(fiche, RelationKind.PARENT, to_entity=cible)
    client = api(owner)

    assert client.delete(source_url(fiche.slug, source.pk)).status_code == 204
    assert client.delete(relation_url(fiche.slug, relation.pk)).status_code == 204

    assert list(Source.objects.values_list("pk", flat=True)) == [gardee.pk]
    assert EntityRelation.objects.count() == 0
    assert Entity.objects.filter(pk__in=[fiche.pk, cible.pk]).count() == 2
    assert fiche.divinity_profile is not None


def test_le_droit_est_reevalue_sur_la_fiche_verrouillee(
    owner: User, fiche: Entity, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refuse the child write when the parent's status changed meanwhile.

    The simulated transition lands between the object permission and the
    locked read, which is the window the re-check closes.
    """
    original = Entity.objects.select_for_update

    def submit_then_lock(*args: Any, **kwargs: Any) -> Any:
        Entity.objects.filter(pk=fiche.pk).update(status=EntityStatus.SUBMITTED)
        return original(*args, **kwargs)

    monkeypatch.setattr(Entity.objects, "select_for_update", submit_then_lock)

    response = api(owner).post(sources_url(fiche.slug), SOURCE_BODY, format="json")

    assert response.status_code == 403
    assert Source.objects.count() == 0


# --- Les autres écritures restent fermées -------------------------------


@pytest.mark.parametrize("method", ["put", "delete", "get"])
def test_les_collections_d_enfants_n_acceptent_que_post(
    owner: User, fiche: Entity, method: str
) -> None:
    """Add no list route and no replacement on the child collections."""
    client = api(owner)

    assert getattr(client, method)(sources_url(fiche.slug)).status_code == 405
    assert getattr(client, method)(relations_url(fiche.slug)).status_code == 405


@pytest.mark.parametrize("method", ["put", "post", "get"])
def test_un_enfant_n_accepte_que_patch_et_delete(
    owner: User, fiche: Entity, method: str
) -> None:
    source = create_source(fiche, label="Immutable Reference")

    response = getattr(api(owner), method)(source_url(fiche.slug, source.pk))

    assert response.status_code == 405


def test_les_routes_publiques_n_ont_pas_de_routes_d_enfants(
    owner: User, fiche: Entity
) -> None:
    """Keep the public contract free of any child route."""
    response = api(owner).post(
        f"/api/entities/{fiche.slug}/sources/", SOURCE_BODY, format="json"
    )

    assert response.status_code == 404


@pytest.mark.parametrize("champ", ["sources", "relations"])
def test_les_enfants_restent_refuses_dans_le_corps_d_une_entite(
    owner: User, fiche: Entity, champ: str
) -> None:
    """Point at the dedicated routes instead of announcing an unavailable write."""
    url = reverse("managed-entity-detail", kwargs={"slug": fiche.slug})

    response = api(owner).patch(url, {champ: []}, format="json")

    assert response.status_code == 400
    assert f"/{champ}/" in str(response.json()[champ])
