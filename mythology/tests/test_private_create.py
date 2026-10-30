"""Private editorial creation: contract, refusals and atomicity.

What this suite covers: who may create and with which refusal code, the
required fields, the profile matching the type and its default values, the
attachments and their refusals, the server-imposed owner and draft status, the
fields no client may supply, and the fact that a failed creation leaves
nothing behind.

It does **not** re-prove the private read policy, which `test_private_read.py`
already covers end to end. It does check that a new record is immediately
readable by its owner privately and absent from the public API, because that is
part of this increment's contract.

Accounts, records and reference data here are synthetic, created by the tests
themselves. No account or record of the development corpus is involved.
"""

from collections.abc import Iterable
from typing import Any
from uuid import uuid4

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from accounts.roles import ADMINISTRATOR, CONTRIBUTOR, REVIEWER
from mythology.models import (
    Country,
    CreatureProfile,
    DivinityProfile,
    Entity,
    EntityStatus,
    EntityType,
    Gender,
    HeroProfile,
    ThreatLevel,
)
from mythology.tests.factories import (
    create_country,
    create_cultural_area,
    create_domain,
    create_entity,
    create_ethnicity,
)
from mythology.views import EntityViewSet, PrivateEntityViewSet

pytestmark = pytest.mark.django_db

PRIVATE_LIST_URL = reverse("managed-entity-list")
PUBLIC_LIST_URL = reverse("entity-list")

PASSWORD = "synthetic-test-passphrase-9517"


def private_detail_url(slug: str) -> str:
    return reverse("managed-entity-detail", kwargs={"slug": slug})


def public_detail_url(slug: str) -> str:
    return reverse("entity-detail", kwargs={"slug": slug})


# --- Comptes, clients et charges utiles ---------------------------------


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


def payload(entity_type: str = EntityType.HERO, **overrides: Any) -> dict[str, Any]:
    """Build the four required fields, overridable field by field."""
    body: dict[str, Any] = {
        "name": "Synthetic Figure",
        "slug": "synthetic-figure",
        "entity_type": entity_type,
        "gender": Gender.FEMALE,
    }
    body.update(overrides)
    return body


#: Type demandé → clé de profil attendue dans la charge utile.
PROFILE_KEY_BY_TYPE: dict[str, str] = {
    EntityType.DIVINITY: "divinity_profile",
    EntityType.HERO: "hero_profile",
    EntityType.CREATURE: "creature_profile",
}

PROFILE_KEYS = tuple(PROFILE_KEY_BY_TYPE.values())


def profile_counts() -> dict[str, int]:
    """Count the rows of the three profile tables, keyed like the payload."""
    return {
        "divinity_profile": DivinityProfile.objects.count(),
        "hero_profile": HeroProfile.objects.count(),
        "creature_profile": CreatureProfile.objects.count(),
    }


@pytest.fixture
def contributor() -> User:
    return account("contributrice-creation", groups=(CONTRIBUTOR,))


def post(user: User, body: dict[str, Any]) -> Any:
    return api(user).post(PRIVATE_LIST_URL, body, format="json")


# --- Qui peut créer -----------------------------------------------------


def test_un_appelant_anonyme_est_refuse_en_401() -> None:
    response = api().post(PRIVATE_LIST_URL, payload(), format="json")

    assert response.status_code == 401
    assert Entity.objects.count() == 0


def test_une_session_seule_ne_suffit_pas(contributor: User) -> None:
    """Require JWT authentication, not an authenticated browser session."""
    client = Client()
    assert client.login(username=contributor.username, password=PASSWORD)

    response = client.post(PRIVATE_LIST_URL, payload(), content_type="application/json")

    assert response.status_code == 401
    assert Entity.objects.count() == 0


@pytest.mark.parametrize(
    ("nom", "groupes", "flags"),
    [
        ("sans-groupe-creation", (), {}),
        ("staff-seul-creation", (), {"is_staff": True}),
        ("groupe-etranger-creation", ("newsletter",), {}),
    ],
)
def test_un_compte_sans_role_metier_est_refuse_en_403(
    nom: str, groupes: tuple[str, ...], flags: dict[str, Any]
) -> None:
    """Deny creation to an account holding no editorial role."""
    response = post(account(nom, groups=groupes, **flags), payload())

    assert response.status_code == 403
    assert Entity.objects.count() == 0


@pytest.mark.parametrize(
    ("nom", "groupes", "flags"),
    [
        ("contributeur-autorise", (CONTRIBUTOR,), {}),
        ("relecteur-autorise", (REVIEWER,), {}),
        ("administrateur-autorise", (ADMINISTRATOR,), {}),
        ("superutilisateur-autorise", (), {"is_staff": True, "is_superuser": True}),
    ],
)
def test_les_quatre_roles_peuvent_creer(
    nom: str, groupes: tuple[str, ...], flags: dict[str, Any]
) -> None:
    """Allow contributors, reviewers, administrators and superusers to create."""
    user = account(nom, groups=groupes, **flags)

    response = post(user, payload())

    assert response.status_code == 201
    assert Entity.objects.get(slug="synthetic-figure").created_by_id == user.pk


# --- Propriétaire et brouillon imposés ----------------------------------


def test_le_proprietaire_et_le_brouillon_sont_imposes(contributor: User) -> None:
    """Set the owner to the caller and the status to draft, server-side."""
    response = post(contributor, payload())

    assert response.status_code == 201
    assert response.json()["created_by"] == contributor.pk
    assert response.json()["status"] == EntityStatus.DRAFT
    entity = Entity.objects.get(slug="synthetic-figure")
    assert entity.created_by_id == contributor.pk
    assert entity.status == EntityStatus.DRAFT


def test_un_administrateur_cree_pour_lui_meme(contributor: User) -> None:
    """Never let a role choose another account as the owner."""
    admin = account("administratrice-proprietaire", groups=(ADMINISTRATOR,))

    response = post(admin, payload(created_by=contributor.pk))

    assert response.status_code == 400
    assert "created_by" in response.json()
    assert Entity.objects.count() == 0


def test_la_fiche_est_lisible_en_prive_et_absente_du_public(
    client: Client, contributor: User
) -> None:
    """Make the new draft readable by its owner and invisible publicly."""
    cree = post(contributor, payload())

    prive = api(contributor).get(private_detail_url("synthetic-figure"))

    assert cree.status_code == 201
    assert prive.status_code == 200
    assert prive.json() == cree.json()
    assert client.get(public_detail_url("synthetic-figure")).status_code == 404
    assert client.get(PUBLIC_LIST_URL).json()["count"] == 0


# --- Champs obligatoires et slug explicite ------------------------------


@pytest.mark.parametrize("champ", ["name", "slug", "entity_type", "gender"])
def test_les_quatre_champs_requis_sont_exiges(contributor: User, champ: str) -> None:
    """Require the four fields, the slug included: none is derived or defaulted."""
    body = payload()
    del body[champ]

    response = post(contributor, body)

    assert response.status_code == 400
    assert champ in response.json()
    assert Entity.objects.count() == 0


def test_le_slug_fourni_est_conserve_tel_quel(contributor: User) -> None:
    """Store the given slug verbatim, without deriving it from the name."""
    response = post(contributor, payload(name="Synthetic Figure", slug="autre-slug"))

    assert response.status_code == 201
    assert response.json()["slug"] == "autre-slug"
    assert Entity.objects.get(name="Synthetic Figure").slug == "autre-slug"


@pytest.mark.parametrize(
    ("champ", "valeur"),
    [("entity_type", "titan"), ("gender", "inconnu")],
)
def test_une_valeur_hors_choix_est_refusee(
    contributor: User, champ: str, valeur: str
) -> None:
    response = post(contributor, payload(**{champ: valeur}))

    assert response.status_code == 400
    assert champ in response.json()


# --- Les trois types et leur profil exact -------------------------------


@pytest.mark.parametrize("entity_type", sorted(PROFILE_KEY_BY_TYPE))
def test_chaque_type_recoit_exactement_son_profil(
    contributor: User, entity_type: str
) -> None:
    """Create the profile of the requested type, and only that one."""
    expected_key = PROFILE_KEY_BY_TYPE[entity_type]

    response = post(contributor, payload(entity_type))

    assert response.status_code == 201
    body = response.json()
    assert isinstance(body[expected_key], dict)
    for key in PROFILE_KEYS:
        if key != expected_key:
            assert body[key] is None, key
    assert profile_counts() == {key: int(key == expected_key) for key in PROFILE_KEYS}


@pytest.mark.parametrize("profil", [None, {}], ids=["absent", "vide"])
def test_un_profil_absent_ou_vide_prend_ses_valeurs_par_defaut(
    contributor: User, profil: dict[str, Any] | None
) -> None:
    """Create the profile with its defaults instead of leaving none."""
    body = payload(EntityType.HERO)
    if profil is not None:
        body["hero_profile"] = profil

    response = post(contributor, body)

    assert response.status_code == 201
    assert response.json()["hero_profile"] == {
        "titles": [],
        "achievements": [],
        "quests": [],
        "weapons_or_artifacts": [],
        "legacy": "",
        "historical_context": "",
    }
    assert HeroProfile.objects.count() == 1


def test_un_profil_renseigne_est_enregistre(contributor: User) -> None:
    response = post(
        contributor,
        payload(
            EntityType.DIVINITY,
            divinity_profile={
                "cult_offerings": ["Synthetic offering"],
                "cult_places": ["Synthetic place"],
            },
        ),
    )

    assert response.status_code == 201
    profile = DivinityProfile.objects.get()
    assert profile.cult_offerings == ["Synthetic offering"]
    assert profile.cult_places == ["Synthetic place"]
    assert profile.cult_taboos == []


def test_un_niveau_de_menace_vide_est_enregistre_null(contributor: User) -> None:
    """Store a single representation of an unassessed threat level."""
    response = post(
        contributor,
        payload(EntityType.CREATURE, creature_profile={"threat_level": ""}),
    )

    assert response.status_code == 201
    assert response.json()["creature_profile"]["threat_level"] is None
    assert CreatureProfile.objects.get().threat_level is None


def test_un_niveau_de_menace_valide_est_conserve(contributor: User) -> None:
    response = post(
        contributor,
        payload(
            EntityType.CREATURE, creature_profile={"threat_level": ThreatLevel.MYTHIC}
        ),
    )

    assert response.status_code == 201
    assert CreatureProfile.objects.get().threat_level == ThreatLevel.MYTHIC


# --- Profils incohérents ------------------------------------------------


@pytest.mark.parametrize(
    ("entity_type", "cle_fournie"),
    [
        (EntityType.HERO, "divinity_profile"),
        (EntityType.HERO, "creature_profile"),
        (EntityType.DIVINITY, "hero_profile"),
        (EntityType.CREATURE, "divinity_profile"),
    ],
)
def test_une_cle_de_profil_d_un_autre_type_est_refusee(
    contributor: User, entity_type: str, cle_fournie: str
) -> None:
    """Refuse a mismatched profile key instead of ignoring it."""
    response = post(contributor, payload(entity_type, **{cle_fournie: {}}))

    assert response.status_code == 400
    assert cle_fournie in response.json()
    assert Entity.objects.count() == 0


def test_fournir_les_deux_cles_est_refuse(contributor: User) -> None:
    response = post(
        contributor, payload(EntityType.HERO, hero_profile={}, creature_profile={})
    )

    assert response.status_code == 400
    assert "creature_profile" in response.json()
    assert Entity.objects.count() == 0


def test_un_profil_null_est_refuse(contributor: User) -> None:
    """Reject `null` rather than reading it as a request for defaults."""
    response = post(contributor, payload(EntityType.HERO, hero_profile=None))

    assert response.status_code == 400
    assert "hero_profile" in response.json()
    assert Entity.objects.count() == 0


@pytest.mark.parametrize("cle", ["entity", "entity_id", "id", "pk"])
def test_un_profil_ne_nomme_ni_son_entite_ni_son_identifiant(
    contributor: User, cle: str
) -> None:
    """Keep the profile attachment and identifier out of the client's reach."""
    response = post(contributor, payload(EntityType.HERO, hero_profile={cle: 1}))

    assert response.status_code == 400
    assert cle in response.json()["hero_profile"]
    assert Entity.objects.count() == 0


def test_un_champ_de_profil_inconnu_est_refuse(contributor: User) -> None:
    """Report a misspelt profile field instead of dropping it silently."""
    response = post(
        contributor, payload(EntityType.HERO, hero_profile={"titels": ["Typo"]})
    )

    assert response.status_code == 400
    assert "titels" in response.json()["hero_profile"]


def test_un_champ_de_profil_d_un_autre_profil_est_refuse(contributor: User) -> None:
    response = post(
        contributor, payload(EntityType.HERO, hero_profile={"habitat": ["Elsewhere"]})
    )

    assert response.status_code == 400
    assert "habitat" in response.json()["hero_profile"]


# --- Champs imposés par le serveur --------------------------------------


@pytest.mark.parametrize(
    ("champ", "valeur"),
    [
        ("id", "3fa85f64-5717-4562-b3fc-2c963f66afa6"),
        ("pk", "3fa85f64-5717-4562-b3fc-2c963f66afa6"),
        ("status", EntityStatus.PUBLISHED),
        ("created_by", 1),
        ("created_by_id", 1),
        ("submitted_at", "2026-10-27T09:00:00Z"),
        ("reviewed_at", "2026-10-27T09:00:00Z"),
        ("reviewed_by", 1),
        ("review_notes", "Injected note."),
        ("deleted_at", "2026-10-27T09:00:00Z"),
        ("deleted_by", 1),
        ("created_at", "2026-10-27T09:00:00Z"),
        ("updated_at", "2026-10-27T09:00:00Z"),
    ],
)
def test_un_champ_serveur_injecte_est_refuse(
    contributor: User, champ: str, valeur: Any
) -> None:
    """Name the refused server-controlled field, and create nothing."""
    response = post(contributor, payload(**{champ: valeur}))

    assert response.status_code == 400
    assert champ in response.json()
    assert Entity.objects.count() == 0


def test_un_administrateur_ne_peut_pas_davantage_imposer_le_statut() -> None:
    """Refuse the editorial status for every role, administrators included."""
    admin = account("administratrice-statut", groups=(ADMINISTRATOR,))

    response = post(admin, payload(status=EntityStatus.PUBLISHED))

    assert response.status_code == 400
    assert "status" in response.json()


@pytest.mark.parametrize("champ", ["sources", "relations", "relations_from"])
def test_la_creation_imbriquee_est_differee_et_refusee(
    contributor: User, champ: str
) -> None:
    """Refuse deferred nested collections rather than dropping them."""
    body = payload()
    body[champ] = []

    response = post(contributor, body)

    assert response.status_code == 400
    assert champ in response.json()
    assert Entity.objects.count() == 0


def test_un_champ_inconnu_est_refuse(contributor: User) -> None:
    """Report an unrecognised key so a typo cannot pass unnoticed."""
    response = post(contributor, payload(entity_typ="hero", prompt="Forbidden"))

    assert response.status_code == 400
    assert {"entity_typ", "prompt"} <= set(response.json())


# --- Champs métier simples et listes de chaînes -------------------------


def test_les_champs_metier_simples_sont_enregistres(contributor: User) -> None:
    response = post(
        contributor,
        payload(
            category="Synthetic subtitle",
            cultural_role="Synthetic role",
            alignment="Lawful Neutral",
            story_description="Synthetic narrative.",
            manifestations="Synthetic manifestation.",
            characteristics=["Synthetic trait"],
            symbols=["Synthetic symbol"],
        ),
    )

    assert response.status_code == 201
    entity = Entity.objects.get(slug="synthetic-figure")
    assert entity.category == "Synthetic subtitle"
    assert entity.characteristics == ["Synthetic trait"]
    assert entity.symbols == ["Synthetic symbol"]
    assert entity.power_objects == []


@pytest.mark.parametrize(
    "valeur",
    ["Synthetic trait", {"first": "Synthetic trait"}, [["Synthetic trait"]], 7, [7]],
    ids=["chaine", "objet", "liste-imbriquee", "nombre", "element-numerique"],
)
def test_un_tableau_invalide_n_est_pas_converti(contributor: User, valeur: Any) -> None:
    """Refuse a wrong type instead of coercing it into an acceptable value."""
    response = post(contributor, payload(characteristics=valeur))

    assert response.status_code == 400
    assert "characteristics" in response.json()
    assert Entity.objects.count() == 0


def test_un_element_trop_long_est_refuse(contributor: User) -> None:
    """Apply the column's own length validation to each item."""
    response = post(contributor, payload(symbols=["x" * 101]))

    assert response.status_code == 400
    assert "symbols" in response.json()


@pytest.mark.parametrize(
    ("entity_type", "profile_key", "field"),
    [
        (EntityType.DIVINITY, "divinity_profile", "cult_offerings"),
        (EntityType.HERO, "hero_profile", "titles"),
        (EntityType.CREATURE, "creature_profile", "powers"),
    ],
)
def test_profile_string_lists_reject_numeric_items(
    contributor: User, entity_type: str, profile_key: str, field: str
) -> None:
    """Do not silently turn numeric profile items into strings."""
    response = post(contributor, payload(entity_type, **{profile_key: {field: [7]}}))

    assert response.status_code == 400
    assert field in response.json()[profile_key]
    assert Entity.objects.count() == 0
    assert all(count == 0 for count in profile_counts().values())


# --- Rattachements aux référentiels -------------------------------------


def test_les_rattachements_sont_enregistres(contributor: User) -> None:
    """Attach foreign keys and collections by reference identifier."""
    country = create_country()
    other_country = create_country(name="Benin", slug="benin", iso_code="BJ")
    ethnicity = create_ethnicity()
    area = create_cultural_area()
    other_area = create_cultural_area(name="Congo Basin", slug="congo-basin")
    domain = create_domain()

    response = post(
        contributor,
        payload(
            primary_country=country.pk,
            secondary_countries=[other_country.pk],
            primary_ethnicity=ethnicity.pk,
            secondary_ethnicities=[],
            primary_cultural_area=area.pk,
            secondary_cultural_areas=[other_area.pk],
            domains=[domain.pk],
        ),
    )

    assert response.status_code == 201
    entity = Entity.objects.get(slug="synthetic-figure")
    assert entity.primary_country_id == country.pk
    assert entity.primary_ethnicity_id == ethnicity.pk
    assert entity.primary_cultural_area_id == area.pk
    assert list(entity.secondary_countries.values_list("pk", flat=True)) == [
        other_country.pk
    ]
    assert list(entity.domains.values_list("pk", flat=True)) == [domain.pk]
    assert list(entity.secondary_cultural_areas.values_list("pk", flat=True)) == [
        other_area.pk
    ]
    assert list(entity.secondary_ethnicities.all()) == []


def test_les_rattachements_sont_facultatifs(contributor: User) -> None:
    response = post(contributor, payload(primary_country=None))

    assert response.status_code == 201
    entity = Entity.objects.get(slug="synthetic-figure")
    assert entity.primary_country_id is None
    assert list(entity.domains.all()) == []


@pytest.mark.parametrize(
    ("champ", "valeur"),
    [
        ("primary_country", 9999),
        ("primary_ethnicity", 9999),
        ("primary_cultural_area", 9999),
        ("secondary_countries", [9999]),
        ("domains", [9999]),
    ],
)
def test_un_rattachement_inexistant_est_refuse(
    contributor: User, champ: str, valeur: Any
) -> None:
    """Refuse an unknown reference instead of creating it."""
    response = post(contributor, payload(**{champ: valeur}))

    assert response.status_code == 400
    assert champ in response.json()
    assert Entity.objects.count() == 0


@pytest.mark.parametrize(
    ("primaire", "secondaire", "fabrique"),
    [
        ("primary_country", "secondary_countries", create_country),
        ("primary_ethnicity", "secondary_ethnicities", create_ethnicity),
        ("primary_cultural_area", "secondary_cultural_areas", create_cultural_area),
    ],
)
def test_une_valeur_a_la_fois_principale_et_secondaire_est_refusee(
    contributor: User, primaire: str, secondaire: str, fabrique: Any
) -> None:
    """Keep a primary anchor distinct from the secondary attachments."""
    reference = fabrique()

    response = post(
        contributor, payload(**{primaire: reference.pk, secondaire: [reference.pk]})
    )

    assert response.status_code == 400
    assert secondaire in response.json()
    assert Entity.objects.count() == 0


def test_aucun_referentiel_n_est_cree_au_passage(contributor: User) -> None:
    """Never create reference data from an entity creation request."""
    response = post(contributor, payload(primary_country={"name": "Nowhere"}))

    assert response.status_code == 400
    assert "primary_country" in response.json()
    assert Country.objects.count() == 0


# --- `variant_of` suit la politique privée ------------------------------


def test_une_variante_lisible_est_acceptee(contributor: User) -> None:
    reference = create_entity(
        name="Synthetic Reference",
        slug="synthetic-reference",
        status=EntityStatus.PUBLISHED,
    )

    response = post(contributor, payload(variant_of=str(reference.pk)))

    assert response.status_code == 201
    assert response.json()["variant_of"]["slug"] == "synthetic-reference"
    assert Entity.objects.get(slug="synthetic-figure").variant_of_id == reference.pk


def test_une_variante_absente_ou_nulle_est_acceptee(contributor: User) -> None:
    response = post(contributor, payload(variant_of=None))

    assert response.status_code == 201
    assert response.json()["variant_of"] is None


def test_les_cibles_interdites_supprimees_et_inexistantes_sont_indistinctes(
    contributor: User,
) -> None:
    """Refuse an unreadable, a deleted and an unknown target identically."""
    autre = account("contributeur-b-creation", groups=(CONTRIBUTOR,))
    interdite = create_entity(
        name="Synthetic Other Draft",
        slug="synthetic-other-draft",
        status=EntityStatus.DRAFT,
        created_by=autre,
    )
    supprimee = create_entity(
        name="Synthetic Deleted",
        slug="synthetic-deleted",
        status=EntityStatus.PUBLISHED,
        deleted_at=timezone.now(),
    )

    refus = [
        post(contributor, payload(variant_of=str(cible)))
        for cible in (interdite.pk, supprimee.pk, uuid4())
    ]

    assert [reponse.status_code for reponse in refus] == [400, 400, 400]
    corps = [reponse.json() for reponse in refus]
    assert corps[0] == corps[1] == corps[2]
    assert "Synthetic Other Draft" not in str(corps[0])
    assert Entity.objects.filter(slug="synthetic-figure").count() == 0


def test_un_relecteur_peut_viser_une_cible_qu_un_contributeur_ne_voit_pas(
    contributor: User,
) -> None:
    """Follow the caller's own read policy when selecting the reference."""
    interdite = create_entity(
        name="Synthetic Orphan Draft",
        slug="synthetic-orphan-draft",
        status=EntityStatus.DRAFT,
    )
    reviewer = account("relectrice-variante", groups=(REVIEWER,))

    refus = post(contributor, payload(variant_of=str(interdite.pk)))
    accepte = post(
        reviewer,
        payload(
            name="Synthetic Variant",
            slug="synthetic-variant",
            variant_of=str(interdite.pk),
        ),
    )

    assert refus.status_code == 400
    assert accepte.status_code == 201


def test_un_identifiant_mal_forme_est_refuse(contributor: User) -> None:
    response = post(contributor, payload(variant_of="pas-un-uuid"))

    assert response.status_code == 400
    assert "variant_of" in response.json()


# --- Doublons -----------------------------------------------------------


def test_un_slug_deja_pris_est_refuse(contributor: User) -> None:
    create_entity(name="Synthetic Existing", slug="synthetic-figure")

    response = post(contributor, payload())

    assert response.status_code == 400
    assert "slug" in response.json()
    assert Entity.objects.count() == 1


def test_un_meme_nom_pour_un_meme_type_est_refuse(contributor: User) -> None:
    """Keep the name/type uniqueness, whatever the slug."""
    create_entity(
        name="Synthetic Figure", slug="synthetic-already", entity_type=EntityType.HERO
    )

    response = post(contributor, payload(EntityType.HERO, slug="synthetic-other-slug"))

    assert response.status_code == 400
    assert Entity.objects.count() == 1


def test_un_meme_nom_pour_un_autre_type_est_accepte(contributor: User) -> None:
    create_entity(
        name="Synthetic Figure", slug="synthetic-already", entity_type=EntityType.HERO
    )

    response = post(
        contributor, payload(EntityType.CREATURE, slug="synthetic-creature")
    )

    assert response.status_code == 201


# --- Atomicité ----------------------------------------------------------


def raise_validation_error(*args: Any, **kwargs: Any) -> None:
    """Simulate a business validation failure, wherever it is installed."""
    raise DjangoValidationError({"__all__": "Synthetic failure, raised by the test."})


def test_un_echec_du_profil_annule_l_entite_deja_enregistree(
    contributor: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Leave no entity behind when the profile fails after the entity is saved."""
    monkeypatch.setattr(HeroProfile, "full_clean", raise_validation_error)

    response = post(contributor, payload(EntityType.HERO))

    assert response.status_code == 400
    assert Entity.objects.count() == 0
    assert HeroProfile.objects.count() == 0


def test_un_echec_de_rattachement_annule_le_couple_entite_profil(
    contributor: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Leave no pair behind when attaching the collections fails."""
    domain = create_domain()
    monkeypatch.setattr(
        "mythology.serializers.attach_collections", raise_validation_error
    )

    response = post(contributor, payload(domains=[domain.pk]))

    assert response.status_code == 400
    assert Entity.objects.count() == 0
    assert HeroProfile.objects.count() == 0


def test_une_erreur_inattendue_n_est_pas_transformee_en_400(
    contributor: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Never hide a bug behind a 400, and still leave nothing behind."""

    def boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("Synthetic bug, raised by the test.")

    monkeypatch.setattr("mythology.serializers.attach_collections", boom)
    domain = create_domain()

    with pytest.raises(RuntimeError):
        post(contributor, payload(domains=[domain.pk]))

    assert Entity.objects.count() == 0
    assert HeroProfile.objects.count() == 0


# --- Garde-fous de configuration des vues -------------------------------


def test_la_vue_privee_n_ouvre_que_la_creation() -> None:
    """Add creation only, without routing update or destroy.

    A full `ModelViewSet` would have opened the three other writes at once;
    this guard is what keeps them closed until their own increments.
    """
    assert hasattr(PrivateEntityViewSet, "create")
    for action in ("update", "partial_update", "destroy"):
        assert not hasattr(PrivateEntityViewSet, action), action


def test_la_vue_publique_n_acquiert_aucune_ecriture() -> None:
    for action in ("create", "update", "partial_update", "destroy"):
        assert not hasattr(EntityViewSet, action), action


def test_la_vue_privee_choisit_le_serializer_de_creation() -> None:
    """Never serve the create serializer on a read action."""
    from mythology.serializers import PrivateEntityCreateSerializer

    view = PrivateEntityViewSet()
    view.action = "create"
    assert view.get_serializer_class() is PrivateEntityCreateSerializer
    for action in ("list", "retrieve"):
        view.action = action
        assert view.get_serializer_class() is not PrivateEntityCreateSerializer
