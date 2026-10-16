"""Tests des quatre référentiels et de leurs relations avec `Entity`."""

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
    """Les quatre référentiels se créent et s'affichent par leur nom."""
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
    """Une aire peut avoir un parent, accessible par `children`."""
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
    """Le nom et le slug d'un pays sont uniques indépendamment."""
    create_country()

    with pytest.raises(IntegrityError), transaction.atomic():
        create_country(iso_code="", **doublon)


def test_unicite_des_noms_des_quatre_referentiels() -> None:
    """Chacun des quatre modèles refuse un nom déjà pris."""
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
    """Les trois valeurs techniques de `kind` passent `full_clean()`."""
    for index, kind in enumerate(CulturalAreaKind.values):
        CulturalArea(name=f"Area {index}", slug=f"area-{index}", kind=kind).full_clean()


def test_kind_inconnu_est_refuse() -> None:
    """Une valeur hors `CulturalAreaKind` est rejetée par `full_clean()`."""
    area = CulturalArea(name="Area", slug="area", kind="galactic")

    with pytest.raises(ValidationError) as excinfo:
        area.full_clean()

    assert "kind" in excinfo.value.message_dict


def test_aire_ne_peut_etre_son_propre_parent_validation() -> None:
    """`full_clean()` refuse une aire qui se désigne elle-même comme parent."""
    area = create_cultural_area()
    area.parent = area

    with pytest.raises(ValidationError) as excinfo:
        area.full_clean()

    assert "parent" in excinfo.value.message_dict


def test_aire_ne_peut_etre_son_propre_parent_en_base() -> None:
    """La contrainte de base rejette aussi un `save()` direct.

    C'est ici la seule garantie réelle : contrairement au `clean()`, elle
    s'applique même sans passer par un formulaire.
    """
    area = create_cultural_area()
    area.parent = area

    with pytest.raises(IntegrityError), transaction.atomic():
        area.save()


def test_iso_code_est_normalise_en_majuscules() -> None:
    """Un code saisi en minuscules est enregistré en majuscules.

    La normalisation a lieu dans `save()`, donc elle s'applique aussi à un
    appel ORM direct, et pas seulement aux formulaires.
    """
    country = create_country(iso_code=" ng ")

    country.refresh_from_db()

    assert country.iso_code == "NG"


@pytest.mark.parametrize("code", ["N1", "ÉÀ", "N", "NGA"])
def test_iso_code_invalide_est_refuse_par_full_clean(code: str) -> None:
    """Un code non alphabétique est rejeté par `full_clean()`.

    Portée exacte : ce contrôle de format n'existe que dans `clean()`. Un
    `objects.create(iso_code="N1")` ne serait arrêté par aucune contrainte de
    base, la seule règle en base étant la longueur maximale de deux
    caractères.
    """
    country = Country(name="Testland", slug="testland", iso_code=code)

    with pytest.raises(ValidationError) as excinfo:
        country.full_clean()

    assert "iso_code" in excinfo.value.message_dict


def test_full_clean_normalise_avant_de_controler_la_longueur() -> None:
    """Les espaces sont retirés avant la validation de longueur du champ."""
    country = Country(name="Testland", slug="testland", iso_code=" ng ")

    country.full_clean()

    assert country.iso_code == "NG"


def test_plusieurs_pays_sans_code_iso() -> None:
    """L'unicité conditionnelle autorise plusieurs pays sans code ISO."""
    create_country(name="Sans code A", slug="sans-code-a", iso_code="")
    create_country(name="Sans code B", slug="sans-code-b", iso_code="")

    assert Country.objects.filter(iso_code="").count() == 2


def test_code_iso_renseigne_reste_unique() -> None:
    """Deux pays ne peuvent pas partager le même code ISO renseigné."""
    create_country()

    with pytest.raises(IntegrityError), transaction.atomic():
        create_country(name="Niger", slug="niger", iso_code="NG")


# --- Protection à la suppression ---------------------------------------


def test_suppression_protegee_du_pays_principal() -> None:
    """Un pays utilisé comme ancrage principal ne peut pas être supprimé."""
    country = create_country()
    create_entity(primary_country=country)

    with pytest.raises(ProtectedError):
        country.delete()

    assert Country.objects.filter(pk=country.pk).exists()


def test_suppression_protegee_de_l_ethnie_principale() -> None:
    """Une ethnie utilisée comme ancrage principal est protégée."""
    ethnicity = create_ethnicity()
    create_entity(primary_ethnicity=ethnicity)

    with pytest.raises(ProtectedError):
        ethnicity.delete()


def test_suppression_protegee_de_l_aire_principale() -> None:
    """Une aire utilisée comme ancrage principal est protégée."""
    area = create_cultural_area()
    create_entity(primary_cultural_area=area)

    with pytest.raises(ProtectedError):
        area.delete()


def test_suppression_protegee_de_l_aire_parente() -> None:
    """Une aire parente d'une autre aire est protégée."""
    parent = create_cultural_area()
    create_cultural_area(name="Yorubaland", slug="yorubaland", parent=parent)

    with pytest.raises(ProtectedError):
        parent.delete()


def test_suppression_protegee_de_l_aire_d_une_ethnie() -> None:
    """L'aire principale d'une ethnie est protégée."""
    area = create_cultural_area()
    create_ethnicity(primary_cultural_area=area)

    with pytest.raises(ProtectedError):
        area.delete()


def test_domaine_secondaire_reste_supprimable() -> None:
    """Un rattachement multiple n'empêche pas la suppression.

    `ManyToManyField` n'accepte pas `on_delete` : seules les trois clés
    principales sont protégées. La suppression retire simplement le lien.
    """
    domain = create_domain()
    entity = create_entity()
    entity.domains.add(domain)

    domain.delete()

    assert Domain.objects.count() == 0
    assert entity.domains.count() == 0


# --- Relations sur `Entity` --------------------------------------------


def test_coexistence_des_rattachements_principaux_et_secondaires() -> None:
    """Les trois ancrages et les quatre collections cohabitent."""
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
    """Une entité accepte plusieurs pays, ethnies, aires et domaines."""
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
    """Les accès inverses ne mélangent pas ancrage et rattachement.

    Un même pays peut être l'ancrage d'une entité et un rattachement
    secondaire d'une autre : les deux relations restent lisibles séparément.
    """
    country = create_country()
    principale = create_entity(primary_country=country)
    secondaire = create_entity(name="Oya", slug="oya")
    secondaire.secondary_countries.add(country)

    assert list(country.entities_as_primary_country.all()) == [principale]
    assert list(country.entities_as_secondary_country.all()) == [secondaire]


def test_entite_sans_rattachement() -> None:
    """Les nouveaux champs sont facultatifs : rien n'est requis."""
    entity = create_entity()

    assert entity.primary_country is None
    assert entity.primary_ethnicity is None
    assert entity.primary_cultural_area is None
    assert entity.secondary_countries.count() == 0
    assert entity.secondary_ethnicities.count() == 0
    assert entity.secondary_cultural_areas.count() == 0
    assert entity.domains.count() == 0


def test_meme_valeur_principale_et_secondaire_n_est_pas_bloquee() -> None:
    """Documente que la règle « principal ≠ secondaire » n'est pas imposée.

    L'ADR 0002 la prévoit, mais aucune barrière ne l'applique dans cet
    incrément : ce test fixe le comportement réel pour que la situation soit
    constatée, et non découverte plus tard. Son application appartiendra aux
    services d'import et d'écriture, avant l'ouverture du CRUD.
    """
    country = create_country()
    entity = create_entity(primary_country=country)

    entity.secondary_countries.add(country)

    assert entity.primary_country == country
    assert list(entity.secondary_countries.all()) == [country]
