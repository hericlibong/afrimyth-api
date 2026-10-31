"""Private editorial read: role, ownership, status and nested references.

What this suite covers, and what it does not. It covers the two private
routes end to end: who is refused and with which code, which records each
role selects, the editorial fields added to the payloads, the nested
references each caller may see, and the fact that no client parameter can
widen that selection.

It does **not** re-prove the guarantees already acquired by the public
suites — pagination arithmetic, filter combination, area hierarchy, public
visibility — which the private routes inherit unchanged. It checks that the
navigation is the same one, not that pagination works.

Accounts, groups and records here are synthetic, created by the tests
themselves. No account or record of the development corpus is involved.
"""

from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager
from typing import Any

import pytest
from django.contrib.auth.models import Group
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from accounts.roles import ADMINISTRATOR, CONTRIBUTOR, REVIEWER
from mythology.models import Entity, EntityStatus, RelationKind
from mythology.selectors import private_entity_detail
from mythology.serializers import (
    PrivateEntityDetailSerializer,
    PrivateEntityListSerializer,
)
from mythology.tests.factories import create_entity, create_relation
from mythology.views import PrivateEntityViewSet

pytestmark = pytest.mark.django_db

PRIVATE_LIST_URL = reverse("managed-entity-list")
PUBLIC_LIST_URL = reverse("entity-list")

PASSWORD = "synthetic-test-passphrase-8402"


def private_detail_url(slug: str) -> str:
    return reverse("managed-entity-detail", kwargs={"slug": slug})


def public_detail_url(slug: str) -> str:
    return reverse("entity-detail", kwargs={"slug": slug})


# --- Comptes et clients -------------------------------------------------


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


# --- Corpus synthétique -------------------------------------------------
#
# Dix fiches couvrant les croisements utiles : les quatre statuts, deux
# propriétaires distincts, un propriétaire nul et la suppression logique.

PUBLISHED_SLUGS = frozenset({"published-owner", "published-other", "orphan-published"})
OWNER_PRIVATE_SLUGS = frozenset({"draft-owner", "submitted-owner", "rejected-owner"})
OTHER_PRIVATE_SLUGS = frozenset({"draft-other"})
ORPHAN_PRIVATE_SLUGS = frozenset({"orphan-draft"})
DELETED_SLUGS = frozenset({"deleted-published", "deleted-draft-owner"})

ACTIVE_SLUGS = (
    PUBLISHED_SLUGS | OWNER_PRIVATE_SLUGS | OTHER_PRIVATE_SLUGS | ORPHAN_PRIVATE_SLUGS
)
ALL_SLUGS = ACTIVE_SLUGS | DELETED_SLUGS


@pytest.fixture
def owner() -> User:
    return account("contributrice-a", groups=(CONTRIBUTOR,))


@pytest.fixture
def other(owner: User) -> User:
    return account("contributeur-b", groups=(CONTRIBUTOR,))


@pytest.fixture
def corpus(owner: User, other: User) -> dict[str, Entity]:
    """Create ten synthetic records named after their coverage cases."""
    deleted_at = timezone.now()
    records = {
        "published-owner": create_entity(
            name="Published Owner",
            slug="published-owner",
            status=EntityStatus.PUBLISHED,
            created_by=owner,
        ),
        "draft-owner": create_entity(
            name="Draft Owner",
            slug="draft-owner",
            status=EntityStatus.DRAFT,
            created_by=owner,
        ),
        "submitted-owner": create_entity(
            name="Submitted Owner",
            slug="submitted-owner",
            status=EntityStatus.SUBMITTED,
            created_by=owner,
            submitted_at=deleted_at,
        ),
        "rejected-owner": create_entity(
            name="Rejected Owner",
            slug="rejected-owner",
            status=EntityStatus.REJECTED,
            created_by=owner,
        ),
        "published-other": create_entity(
            name="Published Other",
            slug="published-other",
            status=EntityStatus.PUBLISHED,
            created_by=other,
        ),
        "draft-other": create_entity(
            name="Draft Other",
            slug="draft-other",
            status=EntityStatus.DRAFT,
            created_by=other,
        ),
        "orphan-published": create_entity(
            name="Orphan Published",
            slug="orphan-published",
            status=EntityStatus.PUBLISHED,
        ),
        "orphan-draft": create_entity(
            name="Orphan Draft",
            slug="orphan-draft",
            status=EntityStatus.DRAFT,
        ),
        "deleted-published": create_entity(
            name="Deleted Published",
            slug="deleted-published",
            status=EntityStatus.PUBLISHED,
            created_by=owner,
            deleted_at=deleted_at,
        ),
        "deleted-draft-owner": create_entity(
            name="Deleted Draft Owner",
            slug="deleted-draft-owner",
            status=EntityStatus.DRAFT,
            created_by=owner,
            deleted_at=deleted_at,
        ),
    }
    assert set(records) == ALL_SLUGS  # garde-fou : les ensembles doivent coller
    return records


#: Rôle de l'appelant → fiches qu'il doit lire sur les routes privées.
#: C'est la traduction directe de la matrice de l'ADR 0002, précisée par
#: l'ADR 0004. Les fiches supprimées n'apparaissent dans aucune ligne.
EXPECTATIONS: dict[str, tuple[Callable[[User, User], User], frozenset[str]]] = {
    "contributeur-proprietaire": (
        lambda owner, other: owner,
        PUBLISHED_SLUGS | OWNER_PRIVATE_SLUGS,
    ),
    "contributeur-autre": (
        lambda owner, other: other,
        PUBLISHED_SLUGS | OTHER_PRIVATE_SLUGS,
    ),
    "relecteur": (
        lambda owner, other: account("relecteur", groups=(REVIEWER,)),
        ACTIVE_SLUGS,
    ),
    "administrateur": (
        lambda owner, other: account("administratrice", groups=(ADMINISTRATOR,)),
        ACTIVE_SLUGS,
    ),
    "superutilisateur-sans-groupe": (
        lambda owner, other: account("secours", is_staff=True, is_superuser=True),
        ACTIVE_SLUGS,
    ),
    "contributeur-et-relecteur": (
        lambda owner, other: account("cumul", groups=(CONTRIBUTOR, REVIEWER)),
        ACTIVE_SLUGS,
    ),
    "contributeur-et-groupe-etranger": (
        lambda owner, other: account(
            "mixte", groups=(CONTRIBUTOR, "newsletter"), is_staff=True
        ),
        PUBLISHED_SLUGS,
    ),
}


@pytest.fixture(params=sorted(EXPECTATIONS))
def caller(
    request: pytest.FixtureRequest, owner: User, other: User
) -> tuple[User, frozenset[str]]:
    """Provide a caller and the expected set of readable records."""
    build, expected = EXPECTATIONS[request.param]
    return build(owner, other), expected


# --- Matrice rôle × propriétaire × statut -------------------------------


def test_la_liste_privee_ne_montre_que_les_fiches_autorisees(
    corpus: dict[str, Entity], caller: tuple[User, frozenset[str]]
) -> None:
    """Match the access matrix in both results and count."""
    user, expected = caller

    response = api(user).get(PRIVATE_LIST_URL)

    assert response.status_code == 200
    payload = response.json()
    assert {item["slug"] for item in payload["results"]} == set(expected)
    assert payload["count"] == len(expected)


def test_le_detail_prive_suit_la_meme_matrice(
    corpus: dict[str, Entity], caller: tuple[User, frozenset[str]]
) -> None:
    """Return 200 for permitted records and 404 for every other record."""
    user, expected = caller
    client = api(user)

    for slug in sorted(ALL_SLUGS):
        response = client.get(private_detail_url(slug))
        attendu = 200 if slug in expected else 404
        assert response.status_code == attendu, slug


def test_une_fiche_interdite_et_un_slug_inconnu_donnent_le_meme_corps(
    corpus: dict[str, Entity], owner: User
) -> None:
    """Do not distinguish forbidden records from unknown records."""
    client = api(owner)

    interdite = client.get(private_detail_url("draft-other"))
    inconnue = client.get(private_detail_url("jamais-vue"))
    supprimee = client.get(private_detail_url("deleted-draft-owner"))

    assert interdite.status_code == inconnue.status_code == supprimee.status_code == 404
    assert interdite.json() == inconnue.json() == supprimee.json()


def test_un_proprietaire_nul_n_appartient_a_aucun_contributeur(
    corpus: dict[str, Entity], owner: User
) -> None:
    """Do not treat ownerless imported records as owned by the contributor."""
    response = api(owner).get(private_detail_url("orphan-draft"))

    assert response.status_code == 404
    assert corpus["orphan-draft"].created_by_id is None


def test_un_relecteur_lit_les_fiches_sans_proprietaire(
    corpus: dict[str, Entity],
) -> None:
    """Allow reviewers to read ownerless records."""
    reviewer = account("relecteur-orphelines", groups=(REVIEWER,))

    response = api(reviewer).get(private_detail_url("orphan-draft"))

    assert response.status_code == 200
    assert response.json()["created_by"] is None


def test_les_suppressions_logiques_sont_exclues_pour_tous(
    corpus: dict[str, Entity],
) -> None:
    """Exclude deleted records even for administrators."""
    admin = account("administrateur-suppressions", groups=(ADMINISTRATOR,))
    client = api(admin)

    liste = client.get(PRIVATE_LIST_URL)

    assert DELETED_SLUGS.isdisjoint({i["slug"] for i in liste.json()["results"]})
    for slug in sorted(DELETED_SLUGS):
        assert client.get(private_detail_url(slug)).status_code == 404, slug
    # Les lignes existent toujours en base : seule la sélection les écarte.
    assert Entity.objects.filter(slug__in=DELETED_SLUGS).count() == 2


# --- Refus : 401 et 403 -------------------------------------------------


@pytest.mark.parametrize("url_builder", ["list", "detail"])
def test_un_appelant_anonyme_est_refuse_en_401(
    corpus: dict[str, Entity], url_builder: str
) -> None:
    url = (
        PRIVATE_LIST_URL
        if url_builder == "list"
        else private_detail_url("published-owner")
    )

    response = api().get(url)

    assert response.status_code == 401


def test_un_jeton_invalide_est_refuse_en_401(corpus: dict[str, Entity]) -> None:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer pas-un-jeton")

    assert client.get(PRIVATE_LIST_URL).status_code == 401


def test_un_jeton_de_renouvellement_est_refuse_en_401(owner: User) -> None:
    """Reject refresh tokens used as access tokens."""
    from rest_framework_simplejwt.tokens import RefreshToken

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(owner)}")

    assert client.get(PRIVATE_LIST_URL).status_code == 401


def test_une_session_seule_ne_suffit_pas(
    corpus: dict[str, Entity], owner: User
) -> None:
    """Require JWT authentication, not an authenticated browser session."""
    client = Client()
    assert client.login(username=owner.username, password=PASSWORD)

    assert client.get(PRIVATE_LIST_URL).status_code == 401


@pytest.mark.parametrize(
    ("nom", "groupes", "flags"),
    [
        ("sans-groupe", (), {}),
        ("staff-seul", (), {"is_staff": True}),
        ("groupe-etranger", ("newsletter",), {}),
        ("staff-et-groupe-etranger", ("newsletter",), {"is_staff": True}),
    ],
)
def test_un_compte_sans_role_metier_est_refuse_en_403(
    corpus: dict[str, Entity],
    nom: str,
    groupes: tuple[str, ...],
    flags: dict[str, Any],
) -> None:
    """Deny route access with 403 even when the requested record is public."""
    client = api(account(nom, groups=groupes, **flags))

    liste = client.get(PRIVATE_LIST_URL)
    publiee = client.get(private_detail_url("published-owner"))

    assert liste.status_code == 403
    assert publiee.status_code == 403


def test_le_403_explique_ce_qui_manque(corpus: dict[str, Entity]) -> None:
    """Name the three business groups without exposing corpus data."""
    response = api(account("sans-role-message")).get(PRIVATE_LIST_URL)

    detail = response.json()["detail"]
    assert "contributor" in detail
    assert "reviewer" in detail
    assert "administrator" in detail


def test_un_changement_de_groupe_agit_avec_le_meme_jeton(
    corpus: dict[str, Entity],
) -> None:
    """Read roles from the database rather than token claims."""
    user = account("promu-en-cours-de-session")
    client = api(user)

    assert client.get(PRIVATE_LIST_URL).status_code == 403

    user.groups.add(Group.objects.get(name=REVIEWER))

    autorise = client.get(PRIVATE_LIST_URL)
    assert autorise.status_code == 200
    assert autorise.json()["count"] == len(ACTIVE_SLUGS)

    user.groups.clear()

    assert client.get(PRIVATE_LIST_URL).status_code == 403


# --- Le contrat public reste strictement public -------------------------


def test_les_routes_publiques_ignorent_le_role_de_l_appelant(
    client: Client, corpus: dict[str, Entity]
) -> None:
    """Keep public reading unchanged with a reviewer's token."""
    reviewer = account("relecteur-public", groups=(REVIEWER,))

    anonyme = client.get(PUBLIC_LIST_URL)
    connecte = api(reviewer).get(PUBLIC_LIST_URL)

    assert anonyme.json() == connecte.json()
    assert anonyme.json()["count"] == len(PUBLISHED_SLUGS)


def test_un_superutilisateur_ne_voit_aucun_brouillon_en_public(
    corpus: dict[str, Entity],
) -> None:
    root = account("super-public", is_staff=True, is_superuser=True)
    client = api(root)

    assert client.get(public_detail_url("draft-owner")).status_code == 404
    assert client.get(public_detail_url("deleted-published")).status_code == 404


@pytest.mark.parametrize("slug", ["published-owner", "orphan-published"])
def test_les_reponses_publiques_n_acquierent_aucun_champ_editorial(
    client: Client, corpus: dict[str, Entity], slug: str
) -> None:
    """Keep editorial fields out of public responses."""
    interdits = {
        "status",
        "created_by",
        "submitted_at",
        "reviewed_at",
        "reviewed_by",
        "review_notes",
        "deleted_at",
        "deleted_by",
    }

    detail = client.get(public_detail_url(slug)).json()
    item = next(
        i for i in client.get(PUBLIC_LIST_URL).json()["results"] if i["slug"] == slug
    )

    assert interdits.isdisjoint(detail)
    assert interdits.isdisjoint(item)


# --- Champs des réponses privées ----------------------------------------


def test_la_liste_privee_ajoute_le_statut_et_le_proprietaire(
    corpus: dict[str, Entity], owner: User
) -> None:
    """Expose the five compact fields plus status and owner."""
    response = api(owner).get(PRIVATE_LIST_URL)

    item = next(i for i in response.json()["results"] if i["slug"] == "submitted-owner")
    assert set(item) == {
        "id",
        "slug",
        "name",
        "entity_type",
        "category",
        "status",
        "created_by",
    }
    assert item["status"] == EntityStatus.SUBMITTED
    assert item["created_by"] == owner.pk


def test_la_liste_privee_rend_un_proprietaire_nul_en_null(
    corpus: dict[str, Entity],
) -> None:
    reviewer = account("relecteur-liste", groups=(REVIEWER,))

    response = api(reviewer).get(PRIVATE_LIST_URL)

    item = next(i for i in response.json()["results"] if i["slug"] == "orphan-draft")
    assert item["created_by"] is None


def test_le_detail_prive_ajoute_les_six_champs_editoriaux(
    corpus: dict[str, Entity], owner: User
) -> None:
    """Add ownership and review fields to the public business fields."""
    reviewer = account("relectrice-detail", groups=(REVIEWER,))
    fiche = corpus["rejected-owner"]
    fiche.submitted_at = timezone.now()
    fiche.reviewed_at = timezone.now()
    fiche.reviewed_by = reviewer
    fiche.review_notes = "Synthetic review note, written by the test."
    fiche.save()

    prive = api(owner).get(private_detail_url("rejected-owner")).json()
    public = Client().get(public_detail_url("published-owner")).json()

    assert set(prive) == set(public) | {
        "status",
        "created_by",
        "submitted_at",
        "reviewed_at",
        "reviewed_by",
        "review_notes",
    }
    assert prive["status"] == EntityStatus.REJECTED
    assert prive["created_by"] == owner.pk
    assert prive["reviewed_by"] == reviewer.pk
    assert prive["review_notes"] == "Synthetic review note, written by the test."
    assert prive["submitted_at"] is not None


def test_le_detail_prive_ne_serialise_aucun_compte(
    corpus: dict[str, Entity], owner: User
) -> None:
    """Represent actors as identifiers, never nested account objects."""
    prive = api(owner).get(private_detail_url("published-owner")).json()

    assert prive["created_by"] == owner.pk
    assert not isinstance(prive["created_by"], dict)
    assert "username" not in str(prive)
    assert "password" not in str(prive)


def test_le_detail_prive_n_expose_pas_les_marques_de_suppression(
    corpus: dict[str, Entity], owner: User
) -> None:
    """Keep deletion marks out of private responses too."""
    prive = api(owner).get(private_detail_url("published-owner")).json()

    assert "deleted_at" not in prive
    assert "deleted_by" not in prive


# --- Références imbriquées ----------------------------------------------


def test_variant_of_est_expose_quand_la_cible_est_lisible(
    corpus: dict[str, Entity], owner: User
) -> None:
    fiche = corpus["draft-owner"]
    fiche.variant_of = corpus["submitted-owner"]
    fiche.save()

    prive = api(owner).get(private_detail_url("draft-owner")).json()

    assert prive["variant_of"]["slug"] == "submitted-owner"
    assert set(prive["variant_of"]) == {"id", "slug", "name", "entity_type"}


def test_variant_of_est_null_quand_la_cible_est_interdite(
    corpus: dict[str, Entity], owner: User
) -> None:
    """Do not leak the identity of a hidden reference."""
    fiche = corpus["draft-owner"]
    fiche.variant_of = corpus["draft-other"]
    fiche.save()

    reponse = api(owner).get(private_detail_url("draft-owner"))

    assert reponse.json()["variant_of"] is None
    assert "Draft Other" not in reponse.content.decode()


def test_variant_of_est_null_quand_la_cible_est_supprimee(
    corpus: dict[str, Entity],
) -> None:
    """Hide deleted targets in nested references too."""
    admin = account("administrateur-references", groups=(ADMINISTRATOR,))
    fiche = corpus["draft-owner"]
    fiche.variant_of = corpus["deleted-published"]
    fiche.save()

    payload = api(admin).get(private_detail_url("draft-owner")).json()

    assert payload["variant_of"] is None


def test_un_relecteur_voit_une_reference_qu_un_contributeur_ne_voit_pas(
    corpus: dict[str, Entity], owner: User
) -> None:
    """Render references according to each caller's access."""
    reviewer = account("relecteur-references", groups=(REVIEWER,))
    fiche = corpus["published-owner"]
    fiche.variant_of = corpus["draft-other"]
    fiche.save()

    vu_par_relecteur = api(reviewer).get(private_detail_url("published-owner")).json()
    vu_par_contributeur = api(owner).get(private_detail_url("published-owner")).json()

    assert vu_par_relecteur["variant_of"]["slug"] == "draft-other"
    assert vu_par_contributeur["variant_of"] is None


def test_une_relation_vers_une_cible_interdite_est_entierement_omise(
    corpus: dict[str, Entity], owner: User
) -> None:
    """Omit forbidden links entirely, without copying the target name."""
    create_relation(
        corpus["draft-owner"],
        RelationKind.CONSORT,
        to_entity=corpus["draft-other"],
        notes="Synthetic note that must not leak.",
    )

    reponse = api(owner).get(private_detail_url("draft-owner"))

    payload = reponse.json()
    assert payload["relations"] == []
    corps = reponse.content.decode()
    assert "Draft Other" not in corps
    assert "must not leak" not in corps


def test_les_relations_autorisees_interdites_et_non_resolues_se_distinguent(
    corpus: dict[str, Entity], owner: User
) -> None:
    """Distinguish permitted, forbidden and unresolved links."""
    source = corpus["draft-owner"]
    create_relation(source, RelationKind.PARENT, to_entity=corpus["submitted-owner"])
    create_relation(source, RelationKind.ENEMY, to_entity=corpus["draft-other"])
    create_relation(source, RelationKind.ALLY, to_name="Figure sans fiche")

    payload = api(owner).get(private_detail_url("draft-owner")).json()

    rendus = {
        (
            relation["kind"],
            relation["to_entity"]["slug"] if relation["to_entity"] else None,
            relation["to_name"],
        )
        for relation in payload["relations"]
    }
    assert rendus == {
        ("parent", "submitted-owner", ""),
        ("ally", None, "Figure sans fiche"),
    }


def test_une_relation_vers_une_cible_supprimee_est_omise(
    corpus: dict[str, Entity],
) -> None:
    admin = account("administrateur-relations", groups=(ADMINISTRATOR,))
    create_relation(
        corpus["draft-owner"],
        RelationKind.PARENT,
        to_entity=corpus["deleted-published"],
    )

    payload = api(admin).get(private_detail_url("draft-owner")).json()

    assert payload["relations"] == []


def test_une_representation_privee_sans_appelant_reste_restrictive(
    corpus: dict[str, Entity],
) -> None:
    """Hide structured references when caller context is missing."""
    fiche = corpus["published-owner"]
    fiche.variant_of = corpus["published-other"]
    fiche.save()
    create_relation(fiche, RelationKind.PARENT, to_entity=corpus["orphan-published"])
    create_relation(fiche, RelationKind.ALLY, to_name="Figure sans fiche")

    payload = PrivateEntityDetailSerializer(Entity.objects.get(pk=fiche.pk)).data

    assert payload["variant_of"] is None
    assert [relation["to_name"] for relation in payload["relations"]] == [
        "Figure sans fiche"
    ]


# --- Les paramètres clients ne changent pas la politique ----------------


@pytest.mark.parametrize(
    "query",
    [
        {"status": "draft"},
        {"created_by": "1"},
        {"deleted_at": ""},
        {"private": "true"},
        {"search": "Draft Other"},
    ],
)
def test_aucun_parametre_client_n_elargit_la_selection(
    corpus: dict[str, Entity], owner: User, query: dict[str, str]
) -> None:
    """Never let a client filter widen access."""
    reponse = api(owner).get(PRIVATE_LIST_URL, query)

    assert reponse.status_code == 200
    slugs = {item["slug"] for item in reponse.json()["results"]}
    assert slugs <= PUBLISHED_SLUGS | OWNER_PRIVATE_SLUGS
    assert "draft-other" not in slugs


def test_un_filtre_restreint_bien_la_selection_privee(
    corpus: dict[str, Entity], owner: User
) -> None:
    """Apply the shared navigation filters to private collections."""
    reponse = api(owner).get(PRIVATE_LIST_URL, {"search": "Submitted"})

    assert {item["slug"] for item in reponse.json()["results"]} == {"submitted-owner"}


def test_les_parametres_de_collection_ne_changent_pas_le_detail_prive(
    corpus: dict[str, Entity], owner: User
) -> None:
    """Do not apply list search parameters to detail requests."""
    reponse = api(owner).get(
        private_detail_url("draft-owner"), {"search": "introuvable"}
    )

    assert reponse.status_code == 200


# --- Navigation réutilisée ----------------------------------------------


def test_la_pagination_privee_garde_vingt_elements_par_page(owner: User) -> None:
    """Use the public collection's page size."""
    for index in range(25):
        create_entity(
            name=f"Owned Draft {index:02d}",
            slug=f"owned-draft-{index:02d}",
            status=EntityStatus.DRAFT,
            created_by=owner,
        )

    premiere = api(owner).get(PRIVATE_LIST_URL).json()
    seconde = api(owner).get(PRIVATE_LIST_URL, {"page": 2}).json()

    assert premiere["count"] == 25
    assert len(premiere["results"]) == 20
    assert len(seconde["results"]) == 5
    assert premiere["next"] is not None


def test_l_ordre_prive_est_stable_et_identique_a_l_ordre_public(
    corpus: dict[str, Entity], owner: User
) -> None:
    """Preserve deterministic name/id ordering."""
    noms = [item["name"] for item in api(owner).get(PRIVATE_LIST_URL).json()["results"]]

    assert noms == sorted(noms)


@pytest.mark.parametrize(
    ("query", "cle"),
    [({"entity_type": "titan"}, "entity_type"), ({"country": "NGA"}, "country")],
)
def test_la_validation_des_parametres_est_la_meme_qu_en_public(
    corpus: dict[str, Entity], owner: User, query: dict[str, str], cle: str
) -> None:
    """Reuse public filter validation errors."""
    prive = api(owner).get(PRIVATE_LIST_URL, query)
    public = Client().get(PUBLIC_LIST_URL, query)

    assert prive.status_code == public.status_code == 400
    assert prive.json() == public.json()
    assert cle in prive.json()


def test_une_page_inexistante_renvoie_404(
    corpus: dict[str, Entity], owner: User
) -> None:
    assert api(owner).get(PRIVATE_LIST_URL, {"page": 99}).status_code == 404


# --- Les autres écritures restent refusées, pour tous les rôles ---------
#
# La création et la modification partielle ont leurs propres suites,
# `test_private_create.py` et `test_private_update.py`. Les refus ci-dessous
# gardent fermé tout le reste.


@pytest.mark.parametrize("method", ["put", "delete"])
def test_le_remplacement_et_la_suppression_sont_refuses_meme_a_un_administrateur(
    corpus: dict[str, Entity], method: str
) -> None:
    """Reject replacement and deletion with 405 even for administrators."""
    client = api(account("administrateur-ecriture", groups=(ADMINISTRATOR,)))

    collection = getattr(client, method)(PRIVATE_LIST_URL)
    fiche = getattr(client, method)(private_detail_url("draft-owner"))

    assert collection.status_code == 405
    assert fiche.status_code == 405


@pytest.mark.parametrize("method", ["post", "put", "delete"])
def test_le_detail_prive_n_accepte_que_la_modification_partielle(
    corpus: dict[str, Entity], method: str
) -> None:
    """Keep every write but `PATCH` closed on the private detail URL."""
    client = api(account("administrateur-detail-ecriture", groups=(ADMINISTRATOR,)))

    assert getattr(client, method)(private_detail_url("draft-owner")).status_code == 405


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_les_ecritures_de_la_collection_sont_refusees_a_un_superutilisateur(
    corpus: dict[str, Entity], method: str
) -> None:
    client = api(account("super-ecriture", is_staff=True, is_superuser=True))

    assert getattr(client, method)(PRIVATE_LIST_URL).status_code == 405


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_l_ecriture_anonyme_est_refusee_avant_la_methode(method: str) -> None:
    """Check authentication before resolving unsupported methods."""
    assert getattr(api(), method)(PRIVATE_LIST_URL).status_code == 401


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_l_ecriture_sans_role_est_refusee_en_403(method: str) -> None:
    client = api(account(f"sans-role-{method}"))

    assert getattr(client, method)(PRIVATE_LIST_URL).status_code == 403


# --- Garde-fous de configuration de la vue ------------------------------


def test_la_vue_privee_n_accepte_que_jwt_et_exige_un_role() -> None:
    """Require explicit JWT authentication and business role permissions."""
    from rest_framework.permissions import IsAuthenticated
    from rest_framework_simplejwt.authentication import JWTAuthentication

    from mythology.permissions import CanEditEntity, HasBusinessRole

    assert PrivateEntityViewSet.authentication_classes == [JWTAuthentication]
    assert PrivateEntityViewSet.permission_classes == [
        IsAuthenticated,
        HasBusinessRole,
        CanEditEntity,
    ]


def test_les_serializers_prives_ne_sont_pas_utilises_en_public() -> None:
    """Never switch public serializers through client parameters."""
    from mythology.views import EntityViewSet

    public = EntityViewSet()
    for action in ("list", "retrieve"):
        public.action = action
        assert public.get_serializer_class() not in {
            PrivateEntityListSerializer,
            PrivateEntityDetailSerializer,
        }


# --- Coût en requêtes ---------------------------------------------------


def test_la_liste_privee_ne_coute_pas_une_requete_par_fiche(owner: User) -> None:
    """Keep list query counts constant across different corpus sizes."""
    client = api(owner)
    for index in range(3):
        create_entity(
            name=f"Few {index}",
            slug=f"few-{index}",
            status=EntityStatus.DRAFT,
            created_by=owner,
        )

    with CaptureQueriesContext(connection) as petit:
        petite = client.get(PRIVATE_LIST_URL)

    for index in range(12):
        create_entity(
            name=f"Many {index:02d}",
            slug=f"many-{index:02d}",
            status=EntityStatus.DRAFT,
            created_by=owner,
        )

    with CaptureQueriesContext(connection) as grand:
        grande = client.get(PRIVATE_LIST_URL)

    assert petite.json()["count"] == 3
    assert grande.json()["count"] == 15
    assert len(grand) == len(petit)


def test_le_detail_prive_ne_coute_pas_une_requete_par_relation(
    owner: User,
) -> None:
    """Keep detail query counts constant as relation targets increase."""
    client = api(owner)
    sobre = create_entity(
        name="Sober", slug="sober", status=EntityStatus.DRAFT, created_by=owner
    )
    create_relation(sobre, RelationKind.ALLY, to_name="Figure sans fiche")

    with CaptureQueriesContext(connection) as petit:
        client.get(private_detail_url("sober"))

    charge = create_entity(
        name="Loaded", slug="loaded", status=EntityStatus.DRAFT, created_by=owner
    )
    charge.variant_of = create_entity(
        name="Reference", slug="reference", status=EntityStatus.PUBLISHED
    )
    charge.save()
    for index, kind in enumerate(
        (RelationKind.PARENT, RelationKind.CHILD, RelationKind.CONSORT)
    ):
        create_relation(
            charge,
            kind,
            to_entity=create_entity(
                name=f"Target {index}",
                slug=f"target-{index}",
                status=EntityStatus.PUBLISHED,
            ),
        )
    create_relation(charge, RelationKind.ENEMY, to_name="Figure sans fiche")

    with CaptureQueriesContext(connection) as grand:
        reponse = client.get(private_detail_url("loaded"))

    assert len(reponse.json()["relations"]) == 4
    assert len(grand) == len(petit)


def test_le_detail_prive_precharge_se_serialise_sans_requete(
    corpus: dict[str, Entity],
    owner: User,
    django_assert_num_queries: Callable[[int], AbstractContextManager[None]],
) -> None:
    """Serialize preloaded private details without further queries."""
    fiche = corpus["draft-owner"]
    fiche.variant_of = corpus["submitted-owner"]
    fiche.save()
    create_relation(fiche, RelationKind.PARENT, to_entity=corpus["published-owner"])
    create_relation(fiche, RelationKind.ENEMY, to_entity=corpus["draft-other"])
    create_relation(fiche, RelationKind.ALLY, to_name="Figure sans fiche")

    roles = frozenset({CONTRIBUTOR})
    loaded = private_entity_detail(roles=roles, caller_id=owner.pk).get(pk=fiche.pk)

    with django_assert_num_queries(0):
        payload = PrivateEntityDetailSerializer(
            loaded, context={"caller_roles": roles, "caller_id": owner.pk}
        ).data

    assert payload["variant_of"]["slug"] == "submitted-owner"
    assert {relation["to_name"] for relation in payload["relations"]} == {
        "",
        "Figure sans fiche",
    }
    assert len(payload["relations"]) == 2
