"""Tests of the four reference models and of their relations with `Entity`."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from mythology.models import Country, CulturalArea, CulturalAreaKind, Domain
from mythology.tests.factories import (
    create_country,
    create_cultural_area,
    create_domain,
    create_entity,
    create_ethnicity,
)

pytestmark = pytest.mark.django_db


# --- Création et représentation ----------------------------------------


def test_creation_et_representation_des_referentiels() -> None:
    """The four reference models are created and displayed by their name."""
    area = create_cultural_area()
    country = create_country()
    ethnicity = create_ethnicity(primary_cultural_area=area)
    domain = create_domain()

    assert str(area) == "West Africa"
    assert str(country) == "Nigeria"
    assert str(ethnicity) == "Yoruba"
    assert str(domain) == "Thunder"
    assert area.kind == CulturalAreaKind.AFRICAN_REGION
    assert country.iso_code == "NG"
    assert ethnicity.primary_cultural_area == area
    assert area.ethnicities.get() == ethnicity


def test_aire_culturelle_hierarchique() -> None:
    """An area may have a parent, reachable through `children`."""
    parent = create_cultural_area()
    child = create_cultural_area(name="Yorubaland", slug="yorubaland", parent=parent)

    assert child.parent == parent
    assert parent.children.get() == child


# --- Unicité ------------------------------------------------------------


@pytest.mark.parametrize(
    "doublon",
    [
        pytest.param({"slug": "autre"}, id="meme-nom"),
        pytest.param({"name": "Autre"}, id="meme-slug"),
    ],
)
def test_unicite_du_nom_et_du_slug_des_pays(doublon: dict[str, str]) -> None:
    """The name and the slug of a country are unique independently."""
    create_country()

    with pytest.raises(IntegrityError), transaction.atomic():
        create_country(iso_code="", **doublon)


def test_unicite_des_noms_des_quatre_referentiels() -> None:
    """Each of the four models refuses a name that is already taken."""
    create_cultural_area()
    create_ethnicity()
    create_domain()

    for creer, kwargs in (
        (create_cultural_area, {"slug": "autre-aire"}),
        (create_ethnicity, {"slug": "autre-ethnie"}),
        (create_domain, {"slug": "autre-domaine"}),
    ):
        with pytest.raises(IntegrityError), transaction.atomic():
            creer(**kwargs)


# --- Validation ---------------------------------------------------------


def test_kind_valide_est_accepte() -> None:
    """The three technical values of `kind` pass `full_clean()`."""
    for index, kind in enumerate(CulturalAreaKind.values):
        CulturalArea(name=f"Area {index}", slug=f"area-{index}", kind=kind).full_clean()


def test_kind_inconnu_est_refuse() -> None:
    """A value outside `CulturalAreaKind` is rejected by `full_clean()`."""
    area = CulturalArea(name="Area", slug="area", kind="galactic")

    with pytest.raises(ValidationError) as excinfo:
        area.full_clean()

    assert "kind" in excinfo.value.message_dict


def test_aire_ne_peut_etre_son_propre_parent_validation() -> None:
    """`full_clean()` refuses an area that names itself as its parent."""
    area = create_cultural_area()
    area.parent = area

    with pytest.raises(ValidationError) as excinfo:
        area.full_clean()

    assert "parent" in excinfo.value.message_dict


def test_aire_ne_peut_etre_son_propre_parent_en_base() -> None:
    """The database constraint also rejects a direct `save()`.

    This is the only real guarantee here: unlike `clean()`, it applies even
    without going through a form.
    """
    area = create_cultural_area()
    area.parent = area

    with pytest.raises(IntegrityError), transaction.atomic():
        area.save()


def test_iso_code_est_normalise_en_majuscules() -> None:
    """A code typed in lower case is stored in upper case.

    The normalisation happens in `save()`, so it also applies to a direct ORM
    call, and not only to forms.
    """
    country = create_country(iso_code=" ng ")

    country.refresh_from_db()

    assert country.iso_code == "NG"


@pytest.mark.parametrize("code", ["N1", "ÉÀ", "N", "NGA"])
def test_iso_code_invalide_est_refuse_par_full_clean(code: str) -> None:
    """A non-alphabetic code is rejected by `full_clean()`.

    Exact scope: this format check lives in `clean()` only. A direct create
    with a malformed code would be stopped by no database constraint, the
    only database rule being the maximum length of two characters.
    """
    country = Country(name="Testland", slug="testland", iso_code=code)

    with pytest.raises(ValidationError) as excinfo:
        country.full_clean()

    assert "iso_code" in excinfo.value.message_dict


def test_full_clean_normalise_avant_de_controler_la_longueur() -> None:
    """Whitespace is stripped before the field length validation."""
    country = Country(name="Testland", slug="testland", iso_code=" ng ")

    country.full_clean()

    assert country.iso_code == "NG"


def test_plusieurs_pays_sans_code_iso() -> None:
    """Conditional uniqueness allows several countries without an ISO code."""
    create_country(name="Sans code A", slug="sans-code-a", iso_code="")
    create_country(name="Sans code B", slug="sans-code-b", iso_code="")

    assert Country.objects.filter(iso_code="").count() == 2


def test_code_iso_renseigne_reste_unique() -> None:
    """Two countries cannot share the same filled-in ISO code."""
    create_country()

    with pytest.raises(IntegrityError), transaction.atomic():
        create_country(name="Niger", slug="niger", iso_code="NG")


# --- Protection à la suppression ---------------------------------------


def test_suppression_protegee_du_pays_principal() -> None:
    """A country used as a primary anchor cannot be deleted."""
    country = create_country()
    create_entity(primary_country=country)

    with pytest.raises(ProtectedError):
        country.delete()

    assert Country.objects.filter(pk=country.pk).exists()


def test_suppression_protegee_de_l_ethnie_principale() -> None:
    """An ethnicity used as a primary anchor is protected."""
    ethnicity = create_ethnicity()
    create_entity(primary_ethnicity=ethnicity)

    with pytest.raises(ProtectedError):
        ethnicity.delete()


def test_suppression_protegee_de_l_aire_principale() -> None:
    """An area used as a primary anchor is protected."""
    area = create_cultural_area()
    create_entity(primary_cultural_area=area)

    with pytest.raises(ProtectedError):
        area.delete()


def test_suppression_protegee_de_l_aire_parente() -> None:
    """An area that is the parent of another area is protected."""
    parent = create_cultural_area()
    create_cultural_area(name="Yorubaland", slug="yorubaland", parent=parent)

    with pytest.raises(ProtectedError):
        parent.delete()


def test_suppression_protegee_de_l_aire_d_une_ethnie() -> None:
    """The primary area of an ethnicity is protected."""
    area = create_cultural_area()
    create_ethnicity(primary_cultural_area=area)

    with pytest.raises(ProtectedError):
        area.delete()


def test_domaine_secondaire_reste_supprimable() -> None:
    """A many-to-many attachment does not prevent deletion.

    `ManyToManyField` accepts no `on_delete`: only the three primary keys are
    protected. Deletion simply removes the link.
    """
    domain = create_domain()
    entity = create_entity()
    entity.domains.add(domain)

    domain.delete()

    assert Domain.objects.count() == 0
    assert entity.domains.count() == 0


# --- Relations sur `Entity` --------------------------------------------


def test_coexistence_des_rattachements_principaux_et_secondaires() -> None:
    """The three anchors and the four collections coexist."""
    area = create_cultural_area()
    diaspora = create_cultural_area(
        name="Caribbean diaspora",
        slug="caribbean-diaspora",
        kind=CulturalAreaKind.DIASPORIC,
    )
    nigeria = create_country()
    benin = create_country(name="Benin", slug="benin", iso_code="BJ")
    yoruba = create_ethnicity()
    fon = create_ethnicity(name="Fon", slug="fon")
    thunder = create_domain()
    justice = create_domain(name="Justice", slug="justice")

    entity = create_entity(
        primary_country=nigeria,
        primary_ethnicity=yoruba,
        primary_cultural_area=area,
    )
    entity.secondary_countries.add(benin)
    entity.secondary_ethnicities.add(fon)
    entity.secondary_cultural_areas.add(diaspora)
    entity.domains.add(thunder, justice)

    entity.refresh_from_db()

    assert entity.primary_country == nigeria
    assert entity.primary_ethnicity == yoruba
    assert entity.primary_cultural_area == area
    assert list(entity.secondary_countries.all()) == [benin]
    assert list(entity.secondary_ethnicities.all()) == [fon]
    assert list(entity.secondary_cultural_areas.all()) == [diaspora]
    assert list(entity.domains.all()) == [justice, thunder]  # ordonnés par nom


def test_plusieurs_valeurs_par_collection() -> None:
    """An entity accepts several countries, ethnicities, areas and domains."""
    entity = create_entity()
    entity.secondary_countries.add(
        create_country(name="Benin", slug="benin", iso_code="BJ"),
        create_country(name="Togo", slug="togo", iso_code="TG"),
    )
    entity.secondary_ethnicities.add(
        create_ethnicity(name="Fon", slug="fon"),
        create_ethnicity(name="Ewe", slug="ewe"),
    )
    entity.secondary_cultural_areas.add(
        create_cultural_area(),
        create_cultural_area(
            name="Pan-African",
            slug="pan-african",
            kind=CulturalAreaKind.TRANSREGIONAL,
        ),
    )
    entity.domains.add(
        create_domain(),
        create_domain(name="Justice", slug="justice"),
    )

    assert entity.secondary_countries.count() == 2
    assert entity.secondary_ethnicities.count() == 2
    assert entity.secondary_cultural_areas.count() == 2
    assert entity.domains.count() == 2


def test_related_names_distinguent_principal_et_secondaire() -> None:
    """The reverse accessors do not mix anchor and attachment.

    One country can be the anchor of an entity and a secondary attachment of
    another: both relations stay readable separately.
    """
    country = create_country()
    principale = create_entity(primary_country=country)
    secondaire = create_entity(name="Oya", slug="oya")
    secondaire.secondary_countries.add(country)

    assert list(country.entities_as_primary_country.all()) == [principale]
    assert list(country.entities_as_secondary_country.all()) == [secondaire]


def test_entite_sans_rattachement() -> None:
    """The new fields are optional: nothing is required."""
    entity = create_entity()

    assert entity.primary_country is None
    assert entity.primary_ethnicity is None
    assert entity.primary_cultural_area is None
    assert entity.secondary_countries.count() == 0
    assert entity.secondary_ethnicities.count() == 0
    assert entity.secondary_cultural_areas.count() == 0
    assert entity.domains.count() == 0


def test_meme_valeur_principale_et_secondaire_n_est_pas_bloquee() -> None:
    """Document that the primary is not secondary rule is not enforced.

    ADR 0002 provides for it, but no barrier applies it in this increment:
    this test pins the real behaviour down so that the situation is observed,
    and not discovered later. Enforcing it will belong to the import and
    write services, before CRUD is opened.
    """
    country = create_country()
    entity = create_entity(primary_country=country)

    entity.secondary_countries.add(country)

    assert entity.primary_country == country
    assert list(entity.secondary_countries.all()) == [country]
