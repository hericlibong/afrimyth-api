"""Private editorial update: rights, partial contract, refusals and atomicity.

Covers `PATCH /api/manage/entities/{slug}/`: the role × ownership × status
matrix, the partial semantics, the profile tied to the stored type, the fields
no client may supply, the attachments checked on the final state, and the fact
that a refused request changes nothing.

The private read policy and the creation contract are not re-proved here; they
have their own suites. Accounts, records and reference data are synthetic.
"""

from collections.abc import Callable, Iterable
from typing import Any
from uuid import uuid4

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError as DjangoValidationError
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from accounts.roles import ADMINISTRATOR, CONTRIBUTOR, REVIEWER
from mythology.models import (
    CreatureProfile,
    DivinityProfile,
    Entity,
    EntityStatus,
    EntityType,
    HeroProfile,
    ThreatLevel,
)
from mythology.tests.factories import (
    create_country,
    create_creature_profile,
    create_cultural_area,
    create_divinity_profile,
    create_domain,
    create_entity,
    create_ethnicity,
    create_hero_profile,
)

pytestmark = pytest.mark.django_db

PASSWORD = "synthetic-test-passphrase-3064"


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


PROFILE_FACTORIES: dict[str, Callable[[Entity], Any]] = {
    EntityType.DIVINITY: create_divinity_profile,
    EntityType.HERO: create_hero_profile,
    EntityType.CREATURE: create_creature_profile,
}


def record(
    slug: str, name: str, entity_type: str = EntityType.DIVINITY, **extra: Any
) -> Entity:
    """Create a consistent record: an entity and the profile of its type."""
    entity = create_entity(name=name, slug=slug, entity_type=entity_type, **extra)
    PROFILE_FACTORIES[entity_type](entity)
    return entity


def patch(user: User, slug: str, body: dict[str, Any]) -> Any:
    return api(user).patch(detail_url(slug), body, format="json")


@pytest.fixture
def owner() -> User:
    return account("contributrice-a-maj", groups=(CONTRIBUTOR,))


@pytest.fixture
def fiche(owner: User) -> Entity:
    """One owned draft hero, the record most tests patch."""
    return record("maj-brouillon", "Maj Brouillon", EntityType.HERO, created_by=owner)


# --- Matrice rôle × propriétaire × statut -------------------------------

#: Fiche → code attendu pour chaque appelant. 404 : non lisible ou supprimée.
#: 403 : lisible mais non modifiable. 200 : modifiable.
MATRIX: dict[str, dict[str, int]] = {
    "draft-owner": {"owner": 200, "other": 404, "reviewer": 200, "admin": 200},
    "rejected-owner": {"owner": 200, "other": 404, "reviewer": 200, "admin": 200},
    "submitted-owner": {"owner": 403, "other": 404, "reviewer": 200, "admin": 200},
    "published-owner": {"owner": 403, "other": 403, "reviewer": 403, "admin": 200},
    "draft-other": {"owner": 404, "other": 200, "reviewer": 200, "admin": 200},
    "orphan-draft": {"owner": 404, "other": 404, "reviewer": 200, "admin": 200},
    "deleted-draft": {"owner": 404, "other": 404, "reviewer": 404, "admin": 404},
}


@pytest.fixture
def corpus(owner: User) -> dict[str, User]:
    """Create the matrix records and return the four callers by key."""
    other = account("contributeur-b-maj", groups=(CONTRIBUTOR,))
    record("draft-owner", "Draft Owner", created_by=owner)
    record(
        "rejected-owner",
        "Rejected Owner",
        created_by=owner,
        status=EntityStatus.REJECTED,
    )
    record(
        "submitted-owner",
        "Submitted Owner",
        created_by=owner,
        status=EntityStatus.SUBMITTED,
    )
    record(
        "published-owner",
        "Published Owner",
        created_by=owner,
        status=EntityStatus.PUBLISHED,
    )
    record("draft-other", "Draft Other", created_by=other)
    record("orphan-draft", "Orphan Draft")
    record(
        "deleted-draft",
        "Deleted Draft",
        created_by=owner,
        deleted_at=timezone.now(),
    )
    return {
        "owner": owner,
        "other": other,
        "reviewer": account("relectrice-maj", groups=(REVIEWER,)),
        "admin": account("administratrice-maj", groups=(ADMINISTRATOR,)),
    }


@pytest.mark.parametrize("slug", sorted(MATRIX))
def test_la_matrice_role_proprietaire_statut_est_respectee(
    corpus: dict[str, User], slug: str
) -> None:
    """Apply the update rights to the record itself, not only to the route."""
    for role, expected in MATRIX[slug].items():
        response = patch(corpus[role], slug, {"category": "Revised"})
        assert response.status_code == expected, f"{slug} / {role}"


def test_un_refus_de_modification_ne_change_rien(corpus: dict[str, User]) -> None:
    """Leave a readable but unmodifiable record untouched."""
    response = patch(corpus["owner"], "published-owner", {"category": "Revised"})

    assert response.status_code == 403
    assert Entity.objects.get(slug="published-owner").category == ""


def test_une_fiche_interdite_et_un_slug_inconnu_donnent_le_meme_404(
    corpus: dict[str, User],
) -> None:
    """Never let a refusal confirm that a record exists."""
    interdite = patch(corpus["owner"], "draft-other", {"category": "Revised"})
    supprimee = patch(corpus["owner"], "deleted-draft", {"category": "Revised"})
    inconnue = patch(corpus["owner"], "jamais-vue", {"category": "Revised"})

    assert interdite.status_code == supprimee.status_code == inconnue.status_code == 404
    assert interdite.json() == supprimee.json() == inconnue.json()


def test_un_appelant_anonyme_est_refuse_en_401(fiche: Entity) -> None:
    response = api().patch(detail_url(fiche.slug), {"category": "x"}, format="json")

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("nom", "groupes", "flags"),
    [
        ("sans-groupe-maj", (), {}),
        ("staff-seul-maj", (), {"is_staff": True}),
        ("groupe-etranger-maj", ("newsletter",), {}),
    ],
)
def test_un_compte_sans_role_metier_est_refuse_en_403(
    fiche: Entity, nom: str, groupes: tuple[str, ...], flags: dict[str, Any]
) -> None:
    """Refuse the route itself to an account holding no editorial role."""
    response = patch(
        account(nom, groups=groupes, **flags), fiche.slug, {"category": "x"}
    )

    assert response.status_code == 403


def test_un_superutilisateur_sans_groupe_modifie_comme_un_administrateur(
    owner: User,
) -> None:
    root = account("secours-maj", is_staff=True, is_superuser=True)
    record(
        "maj-publiee", "Maj Publiee", created_by=owner, status=EntityStatus.PUBLISHED
    )

    response = patch(root, "maj-publiee", {"category": "Revised"})

    assert response.status_code == 200


def test_un_changement_de_groupe_agit_avec_le_meme_jeton(fiche: Entity) -> None:
    """Read the update rights from the database, not from the token."""
    user = account("promu-maj")
    client = api(user)

    refuse = client.patch(detail_url(fiche.slug), {"category": "x"}, format="json")
    assert refuse.status_code == 403

    user.groups.add(Group.objects.get(name=REVIEWER))

    autorise = client.patch(detail_url(fiche.slug), {"category": "y"}, format="json")
    assert autorise.status_code == 200


# --- Sémantique partielle -----------------------------------------------


def test_un_champ_absent_conserve_sa_valeur(owner: User) -> None:
    """Change only the supplied keys."""
    fiche = record(
        "maj-partielle",
        "Maj Partielle",
        EntityType.HERO,
        created_by=owner,
        category="Kept subtitle",
        characteristics=["Kept trait"],
        story_description="Kept narrative.",
    )

    response = patch(owner, fiche.slug, {"story_description": "Revised narrative."})

    assert response.status_code == 200
    fiche.refresh_from_db()
    assert fiche.story_description == "Revised narrative."
    assert fiche.category == "Kept subtitle"
    assert fiche.characteristics == ["Kept trait"]


def test_une_liste_fournie_remplace_la_seule_liste_visee(owner: User) -> None:
    fiche = record(
        "maj-listes",
        "Maj Listes",
        EntityType.HERO,
        created_by=owner,
        characteristics=["Old trait"],
        symbols=["Kept symbol"],
    )

    response = patch(owner, fiche.slug, {"characteristics": ["New trait"]})

    assert response.status_code == 200
    fiche.refresh_from_db()
    assert fiche.characteristics == ["New trait"]
    assert fiche.symbols == ["Kept symbol"]


def test_une_liste_vide_vide_la_liste(owner: User) -> None:
    fiche = record(
        "maj-vide",
        "Maj Vide",
        EntityType.HERO,
        created_by=owner,
        characteristics=["Old trait"],
    )

    assert patch(owner, fiche.slug, {"characteristics": []}).status_code == 200
    fiche.refresh_from_db()
    assert fiche.characteristics == []


def test_un_corps_vide_est_accepte_et_ne_change_rien(
    fiche: Entity, owner: User
) -> None:
    response = patch(owner, fiche.slug, {})

    assert response.status_code == 200
    assert response.json()["slug"] == fiche.slug


def test_la_reponse_200_est_la_representation_du_detail_prive(
    fiche: Entity, owner: User
) -> None:
    modifiee = patch(owner, fiche.slug, {"category": "Revised"})
    relue = api(owner).get(detail_url(fiche.slug))

    assert modifiee.status_code == 200
    assert modifiee.json() == relue.json()
    assert modifiee.json()["category"] == "Revised"


def test_le_slug_est_modifiable(fiche: Entity, owner: User) -> None:
    response = patch(owner, fiche.slug, {"slug": "maj-nouveau-slug"})

    assert response.status_code == 200
    assert response.json()["slug"] == "maj-nouveau-slug"
    assert Entity.objects.get(pk=fiche.pk).slug == "maj-nouveau-slug"


def test_l_identifiant_ne_change_pas(fiche: Entity, owner: User) -> None:
    response = patch(owner, fiche.slug, {"name": "Maj Renommee"})

    assert response.status_code == 200
    assert response.json()["id"] == str(fiche.pk)


@pytest.mark.parametrize(
    ("champ", "fabrique"),
    [
        ("primary_country", create_country),
        ("primary_ethnicity", create_ethnicity),
        ("primary_cultural_area", create_cultural_area),
    ],
)
def test_un_ancrage_principal_peut_etre_remis_a_null(
    owner: User, champ: str, fabrique: Any
) -> None:
    """Accept `null` on the fields that are actually nullable."""
    fiche = record(
        "maj-ancrage",
        "Maj Ancrage",
        EntityType.HERO,
        created_by=owner,
        **{champ: fabrique()},
    )

    assert patch(owner, fiche.slug, {champ: None}).status_code == 200
    fiche.refresh_from_db()
    assert getattr(fiche, f"{champ}_id") is None


@pytest.mark.parametrize("champ", ["name", "slug", "category"])
def test_un_champ_textuel_requis_refuse_null(
    fiche: Entity, owner: User, champ: str
) -> None:
    """Refuse `null` on a field that is not nullable."""
    response = patch(owner, fiche.slug, {champ: None})

    assert response.status_code == 400
    assert champ in response.json()


# --- Profil et type -----------------------------------------------------


def test_le_type_ne_peut_pas_changer(fiche: Entity, owner: User) -> None:
    """Refuse `entity_type` explicitly, per ADR 0005."""
    response = patch(owner, fiche.slug, {"entity_type": EntityType.DIVINITY})

    assert response.status_code == 400
    assert "entity_type" in response.json()
    assert Entity.objects.get(pk=fiche.pk).entity_type == EntityType.HERO


def test_le_profil_est_modifie_partiellement(owner: User) -> None:
    fiche = record("maj-profil", "Maj Profil", EntityType.HERO, created_by=owner)
    profile = HeroProfile.objects.get(entity=fiche)
    profile.titles = ["Kept title"]
    profile.legacy = "Kept legacy."
    profile.save()

    response = patch(owner, fiche.slug, {"hero_profile": {"quests": ["New quest"]}})

    assert response.status_code == 200
    profile.refresh_from_db()
    assert profile.quests == ["New quest"]
    assert profile.titles == ["Kept title"]
    assert profile.legacy == "Kept legacy."
    assert HeroProfile.objects.count() == 1


@pytest.mark.parametrize("profil", [None, {}], ids=["absent", "vide"])
def test_un_profil_absent_ou_vide_n_efface_rien(
    owner: User, profil: dict[str, Any] | None
) -> None:
    fiche = record("maj-intact", "Maj Intact", EntityType.HERO, created_by=owner)
    profile = HeroProfile.objects.get(entity=fiche)
    profile.titles = ["Kept title"]
    profile.save()

    body: dict[str, Any] = {"category": "Revised"}
    if profil is not None:
        body["hero_profile"] = profil

    assert patch(owner, fiche.slug, body).status_code == 200
    profile.refresh_from_db()
    assert profile.titles == ["Kept title"]


def test_un_profil_null_est_refuse(fiche: Entity, owner: User) -> None:
    response = patch(owner, fiche.slug, {"hero_profile": None})

    assert response.status_code == 400
    assert "hero_profile" in response.json()


def test_une_cle_de_profil_d_un_autre_type_est_refusee(
    fiche: Entity, owner: User
) -> None:
    response = patch(owner, fiche.slug, {"divinity_profile": {"cult_taboos": ["x"]}})

    assert response.status_code == 400
    assert "divinity_profile" in response.json()
    assert DivinityProfile.objects.count() == 0


@pytest.mark.parametrize("cle", ["entity", "entity_id", "id", "pk"])
def test_un_profil_ne_nomme_ni_son_entite_ni_son_identifiant(
    fiche: Entity, owner: User, cle: str
) -> None:
    response = patch(owner, fiche.slug, {"hero_profile": {cle: 1}})

    assert response.status_code == 400
    assert cle in response.json()["hero_profile"]


def test_un_champ_de_profil_inconnu_est_refuse(fiche: Entity, owner: User) -> None:
    response = patch(owner, fiche.slug, {"hero_profile": {"titels": ["Typo"]}})

    assert response.status_code == 400
    assert "titels" in response.json()["hero_profile"]


def test_une_fiche_sans_profil_est_refusee_sans_mutation(owner: User) -> None:
    """Never repair a legacy inconsistency as a side effect of an update."""
    fiche = create_entity(
        name="Maj Sans Profil",
        slug="maj-sans-profil",
        entity_type=EntityType.HERO,
        created_by=owner,
    )

    response = patch(owner, fiche.slug, {"category": "Revised"})

    assert response.status_code == 400
    assert "exactly the profile of its type" in str(response.json())
    fiche.refresh_from_db()
    assert fiche.category == ""
    assert HeroProfile.objects.count() == 0


def test_une_fiche_portant_un_profil_etranger_est_refusee(owner: User) -> None:
    """Refuse a record carrying a profile of another type than its own."""
    fiche = create_entity(
        name="Maj Profil Etranger",
        slug="maj-profil-etranger",
        entity_type=EntityType.HERO,
        created_by=owner,
    )
    create_hero_profile(fiche)
    DivinityProfile.objects.create(entity=fiche)

    response = patch(owner, fiche.slug, {"category": "Revised"})

    assert response.status_code == 400
    assert Entity.objects.get(pk=fiche.pk).category == ""


def test_un_niveau_de_menace_vide_est_normalise_en_null(owner: User) -> None:
    fiche = record(
        "maj-creature", "Maj Creature", EntityType.CREATURE, created_by=owner
    )
    CreatureProfile.objects.filter(entity=fiche).update(threat_level=ThreatLevel.MYTHIC)

    response = patch(owner, fiche.slug, {"creature_profile": {"threat_level": ""}})

    assert response.status_code == 200
    assert response.json()["creature_profile"]["threat_level"] is None
    assert CreatureProfile.objects.get(entity=fiche).threat_level is None


# --- Champs imposés par le serveur --------------------------------------


@pytest.mark.parametrize(
    ("champ", "valeur"),
    [
        ("id", "3fa85f64-5717-4562-b3fc-2c963f66afa6"),
        ("pk", "3fa85f64-5717-4562-b3fc-2c963f66afa6"),
        ("status", EntityStatus.PUBLISHED),
        ("created_by", 1),
        ("created_by_id", 1),
        ("submitted_at", "2026-10-30T09:00:00Z"),
        ("reviewed_at", "2026-10-30T09:00:00Z"),
        ("reviewed_by", 1),
        ("review_notes", "Injected note."),
        ("deleted_at", "2026-10-30T09:00:00Z"),
        ("deleted_by", 1),
        ("created_at", "2026-10-30T09:00:00Z"),
        ("updated_at", "2026-10-30T09:00:00Z"),
        ("sources", []),
        ("relations", []),
        ("relations_from", []),
    ],
)
def test_un_champ_serveur_injecte_est_refuse(
    fiche: Entity, owner: User, champ: str, valeur: Any
) -> None:
    """Name every refused server-controlled or deferred key, and change nothing."""
    response = patch(owner, fiche.slug, {champ: valeur, "category": "Revised"})

    assert response.status_code == 400
    assert champ in response.json()
    assert Entity.objects.get(pk=fiche.pk).category == ""


def test_un_administrateur_ne_transfere_pas_la_propriete(
    fiche: Entity, owner: User
) -> None:
    admin = account("administratrice-transfert", groups=(ADMINISTRATOR,))

    response = patch(admin, fiche.slug, {"created_by": admin.pk})

    assert response.status_code == 400
    assert Entity.objects.get(pk=fiche.pk).created_by_id == owner.pk


def test_un_administrateur_ne_publie_pas_par_patch(fiche: Entity, owner: User) -> None:
    admin = account("administratrice-statut-maj", groups=(ADMINISTRATOR,))

    response = patch(admin, fiche.slug, {"status": EntityStatus.PUBLISHED})

    assert response.status_code == 400
    assert Entity.objects.get(pk=fiche.pk).status == EntityStatus.DRAFT


def test_un_champ_inconnu_est_refuse(fiche: Entity, owner: User) -> None:
    response = patch(owner, fiche.slug, {"categorie": "Typo", "prompt": "Forbidden"})

    assert response.status_code == 400
    assert {"categorie", "prompt"} <= set(response.json())


# --- Tableaux et longueurs ----------------------------------------------


@pytest.mark.parametrize(
    "valeur",
    ["Synthetic trait", {"first": "Synthetic trait"}, [["nested"]], [7]],
    ids=["chaine", "objet", "liste-imbriquee", "nombre"],
)
def test_un_tableau_invalide_n_est_pas_converti(
    fiche: Entity, owner: User, valeur: Any
) -> None:
    """Refuse a wrong type instead of coercing it into an acceptable value."""
    response = patch(owner, fiche.slug, {"characteristics": valeur})

    assert response.status_code == 400
    assert "characteristics" in response.json()
    assert Entity.objects.get(pk=fiche.pk).characteristics == []


def test_un_element_trop_long_est_refuse(fiche: Entity, owner: User) -> None:
    response = patch(owner, fiche.slug, {"symbols": ["x" * 101]})

    assert response.status_code == 400
    assert "symbols" in response.json()


def test_une_valeur_hors_choix_est_refusee(fiche: Entity, owner: User) -> None:
    response = patch(owner, fiche.slug, {"gender": "inconnu"})

    assert response.status_code == 400
    assert "gender" in response.json()


# --- Doublons -----------------------------------------------------------


def test_un_slug_deja_pris_est_refuse(fiche: Entity, owner: User) -> None:
    record("maj-deja-pris", "Maj Deja Pris", EntityType.HERO, created_by=owner)

    response = patch(owner, fiche.slug, {"slug": "maj-deja-pris"})

    assert response.status_code == 400
    assert "slug" in response.json()
    assert Entity.objects.get(pk=fiche.pk).slug == "maj-brouillon"


def test_un_nom_deja_pris_pour_le_meme_type_est_refuse(
    fiche: Entity, owner: User
) -> None:
    record("maj-homonyme", "Maj Homonyme", EntityType.HERO, created_by=owner)

    response = patch(owner, fiche.slug, {"name": "Maj Homonyme"})

    assert response.status_code == 400
    assert Entity.objects.get(pk=fiche.pk).name == "Maj Brouillon"


def test_renvoyer_ses_propres_valeurs_n_est_pas_un_doublon(
    fiche: Entity, owner: User
) -> None:
    """Never let a record conflict with itself."""
    response = patch(owner, fiche.slug, {"slug": fiche.slug, "name": fiche.name})

    assert response.status_code == 200


def test_un_nom_deja_pris_pour_un_autre_type_est_accepte(
    fiche: Entity, owner: User
) -> None:
    record("maj-divinite", "Maj Divinite", created_by=owner)

    response = patch(owner, fiche.slug, {"name": "Maj Divinite"})

    assert response.status_code == 200


# --- Rattachements et état final ----------------------------------------


def test_les_rattachements_sont_remplaces_ou_laisses_intacts(owner: User) -> None:
    kept = create_domain(name="Kept Domain", slug="kept-domain")
    added = create_country()
    fiche = record("maj-liens", "Maj Liens", EntityType.HERO, created_by=owner)
    fiche.domains.set([kept])

    response = patch(owner, fiche.slug, {"secondary_countries": [added.pk]})

    assert response.status_code == 200
    assert list(fiche.secondary_countries.values_list("pk", flat=True)) == [added.pk]
    assert list(fiche.domains.values_list("pk", flat=True)) == [kept.pk]


def test_une_collection_peut_etre_videe(owner: User) -> None:
    domain = create_domain()
    fiche = record("maj-domaines", "Maj Domaines", EntityType.HERO, created_by=owner)
    fiche.domains.set([domain])

    assert patch(owner, fiche.slug, {"domains": []}).status_code == 200
    assert list(fiche.domains.all()) == []


@pytest.mark.parametrize(
    ("champ", "valeur"),
    [
        ("primary_country", 9999),
        ("secondary_ethnicities", [9999]),
        ("domains", [9999]),
    ],
)
def test_un_rattachement_inexistant_est_refuse(
    fiche: Entity, owner: User, champ: str, valeur: Any
) -> None:
    response = patch(owner, fiche.slug, {champ: valeur})

    assert response.status_code == 400
    assert champ in response.json()


def test_le_recouvrement_est_juge_sur_l_etat_final_stocke(owner: User) -> None:
    """Combine the stored primary anchor with the patched secondary list."""
    country = create_country()
    fiche = record(
        "maj-recouvrement",
        "Maj Recouvrement",
        EntityType.HERO,
        created_by=owner,
        primary_country=country,
    )

    response = patch(owner, fiche.slug, {"secondary_countries": [country.pk]})

    assert response.status_code == 400
    assert "secondary_countries" in response.json()
    assert list(fiche.secondary_countries.all()) == []


def test_le_recouvrement_est_juge_sur_l_ancrage_patche(owner: User) -> None:
    """Combine the patched primary anchor with the stored secondary list."""
    area = create_cultural_area()
    fiche = record("maj-aire", "Maj Aire", EntityType.HERO, created_by=owner)
    fiche.secondary_cultural_areas.set([area])

    response = patch(owner, fiche.slug, {"primary_cultural_area": area.pk})

    assert response.status_code == 400
    assert "secondary_cultural_areas" in response.json()
    assert Entity.objects.get(pk=fiche.pk).primary_cultural_area_id is None


def test_deplacer_un_ancrage_vers_le_secondaire_en_une_requete_est_accepte(
    owner: User,
) -> None:
    """Accept a swap whose final state is consistent."""
    country = create_country()
    other = create_country(name="Benin", slug="benin", iso_code="BJ")
    fiche = record(
        "maj-echange",
        "Maj Echange",
        EntityType.HERO,
        created_by=owner,
        primary_country=country,
    )

    response = patch(
        owner,
        fiche.slug,
        {"primary_country": other.pk, "secondary_countries": [country.pk]},
    )

    assert response.status_code == 200
    fiche.refresh_from_db()
    assert fiche.primary_country_id == other.pk
    assert list(fiche.secondary_countries.values_list("pk", flat=True)) == [country.pk]


# --- `variant_of` -------------------------------------------------------


def test_une_variante_lisible_est_acceptee(fiche: Entity, owner: User) -> None:
    reference = record(
        "maj-reference",
        "Maj Reference",
        created_by=owner,
        status=EntityStatus.PUBLISHED,
    )

    response = patch(owner, fiche.slug, {"variant_of": str(reference.pk)})

    assert response.status_code == 200
    assert response.json()["variant_of"]["slug"] == "maj-reference"


def test_une_variante_peut_etre_retiree(owner: User) -> None:
    reference = record("maj-cible", "Maj Cible", created_by=owner)
    fiche = record(
        "maj-variante",
        "Maj Variante",
        EntityType.HERO,
        created_by=owner,
        variant_of=reference,
    )

    assert patch(owner, fiche.slug, {"variant_of": None}).status_code == 200
    assert Entity.objects.get(pk=fiche.pk).variant_of_id is None


def test_les_cibles_interdites_supprimees_et_inexistantes_sont_indistinctes(
    fiche: Entity, owner: User
) -> None:
    other = account("contributeur-cible", groups=(CONTRIBUTOR,))
    interdite = record("maj-interdite", "Maj Interdite", created_by=other)
    supprimee = record(
        "maj-supprimee",
        "Maj Supprimee",
        created_by=owner,
        status=EntityStatus.PUBLISHED,
        deleted_at=timezone.now(),
    )

    refus = [
        patch(owner, fiche.slug, {"variant_of": str(cible)})
        for cible in (interdite.pk, supprimee.pk, uuid4())
    ]

    assert [r.status_code for r in refus] == [400, 400, 400]
    assert refus[0].json() == refus[1].json() == refus[2].json()
    assert "Maj Interdite" not in str(refus[0].json())


def test_l_auto_lien_est_refuse(fiche: Entity, owner: User) -> None:
    response = patch(owner, fiche.slug, {"variant_of": str(fiche.pk)})

    assert response.status_code == 400
    assert "variant_of" in response.json()
    assert Entity.objects.get(pk=fiche.pk).variant_of_id is None


# --- Atomicité ----------------------------------------------------------


def raise_validation_error(*args: Any, **kwargs: Any) -> None:
    """Simulate a business validation failure, wherever it is installed."""
    raise DjangoValidationError({"__all__": "Synthetic failure, raised by the test."})


def test_un_echec_du_profil_annule_la_mutation_de_l_entite(
    fiche: Entity, owner: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Revert the entity when the profile fails after it was saved."""
    monkeypatch.setattr(HeroProfile, "full_clean", raise_validation_error)

    response = patch(
        owner,
        fiche.slug,
        {"category": "Revised", "hero_profile": {"titles": ["Revised"]}},
    )

    assert response.status_code == 400
    assert Entity.objects.get(pk=fiche.pk).category == ""
    assert HeroProfile.objects.get(entity=fiche).titles == []


def test_un_echec_de_rattachement_annule_entite_et_profil(
    fiche: Entity, owner: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Revert both the entity and the profile when attaching fails."""
    domain = create_domain()
    monkeypatch.setattr(
        "mythology.serializers.attach_collections", raise_validation_error
    )

    response = patch(
        owner,
        fiche.slug,
        {
            "category": "Revised",
            "hero_profile": {"titles": ["Revised"]},
            "domains": [domain.pk],
        },
    )

    assert response.status_code == 400
    assert Entity.objects.get(pk=fiche.pk).category == ""
    assert HeroProfile.objects.get(entity=fiche).titles == []


def test_une_erreur_inattendue_n_est_pas_transformee_en_400(
    fiche: Entity, owner: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Never hide a bug behind a 400, and still revert everything."""

    def boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("Synthetic bug, raised by the test.")

    monkeypatch.setattr("mythology.serializers.attach_collections", boom)
    domain = create_domain()

    with pytest.raises(RuntimeError):
        patch(owner, fiche.slug, {"category": "Revised", "domains": [domain.pk]})

    assert Entity.objects.get(pk=fiche.pk).category == ""


def test_le_droit_est_reevalue_sur_la_ligne_verrouillee(
    fiche: Entity, owner: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refuse the write when the status changed after the permission check.

    The simulated concurrent transition happens between the object permission
    and the locked read, which is exactly the window the re-check closes.
    """
    original = Entity.objects.select_for_update

    def submit_then_lock(*args: Any, **kwargs: Any) -> Any:
        Entity.objects.filter(pk=fiche.pk).update(status=EntityStatus.SUBMITTED)
        return original(*args, **kwargs)

    monkeypatch.setattr(Entity.objects, "select_for_update", submit_then_lock)

    response = patch(owner, fiche.slug, {"category": "Revised"})

    assert response.status_code == 403
    assert Entity.objects.get(pk=fiche.pk).category == ""


@pytest.mark.parametrize("changed_side", ["primary", "secondary"])
def test_attachment_validation_uses_the_locked_state(
    fiche: Entity, owner: User, monkeypatch: pytest.MonkeyPatch, changed_side: str
) -> None:
    """Reject overlaps introduced between initial validation and the locked read."""
    country = create_country()
    original = Entity.objects.select_for_update

    def change_attachment_then_lock(*args: Any, **kwargs: Any) -> Any:
        if changed_side == "primary":
            Entity.objects.filter(pk=fiche.pk).update(primary_country=country)
        else:
            fiche.secondary_countries.add(country)
        return original(*args, **kwargs)

    monkeypatch.setattr(
        Entity.objects, "select_for_update", change_attachment_then_lock
    )
    body: dict[str, Any] = (
        {"secondary_countries": [country.pk]}
        if changed_side == "primary"
        else {"primary_country": country.pk}
    )

    response = patch(owner, fiche.slug, body)

    assert response.status_code == 400
    assert "secondary_countries" in response.json()
    fiche.refresh_from_db()
    assert fiche.primary_country_id is None
    assert not fiche.secondary_countries.exists()


# --- Les autres écritures restent fermées -------------------------------


@pytest.mark.parametrize("method", ["put", "delete"])
def test_le_remplacement_et_la_suppression_restent_refuses(
    fiche: Entity, method: str
) -> None:
    client = api(account("administratrice-fermee", groups=(ADMINISTRATOR,)))

    assert getattr(client, method)(detail_url(fiche.slug)).status_code == 405


def test_le_patch_public_reste_refuse(fiche: Entity, owner: User) -> None:
    """Keep the public routes free of any write operation."""
    url = reverse("entity-detail", kwargs={"slug": fiche.slug})

    assert api(owner).patch(url, {"category": "x"}, format="json").status_code == 405


def test_le_patch_de_la_collection_privee_reste_refuse(owner: User) -> None:
    url = reverse("managed-entity-list")

    assert api(owner).patch(url, {"category": "x"}, format="json").status_code == 405
