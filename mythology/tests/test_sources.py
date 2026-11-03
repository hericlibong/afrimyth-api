"""Tests of the documentary sources.

**Every reference used here is fictitious**, invented for demonstration.
No real publication is cited, and no source is attributed to a figure of
the corpus.

Each rule is tested at its real scope: Django validation through
`full_clean()`, the cascade and the mandatory database-side fields where
they actually are.
"""

import datetime

import pytest
from django.core.exceptions import ValidationError

from mythology.models import Entity, Source, SourceKind
from mythology.tests.factories import create_entity, create_hero, create_source

pytestmark = pytest.mark.django_db


# --- Création et rattachement -------------------------------------------


def test_plusieurs_sources_pour_une_entite() -> None:
    """An entity carries zero or several sources, ordered by reference."""
    entity = create_entity()
    create_source(entity, label="Zeta Fictional Review", kind=SourceKind.ARTICLE)
    create_source(entity, label="Alpha Fictional Encyclopedia")

    labels = [source.label for source in entity.sources.all()]

    assert labels == ["Alpha Fictional Encyclopedia", "Zeta Fictional Review"]


def test_entite_sans_source() -> None:
    """No source is required."""
    entity = create_entity()

    assert entity.sources.count() == 0


def test_meme_reference_sur_deux_entites() -> None:
    """The same reference can be entered for two records.

    There is neither a shared catalogue nor a many-to-many relation: each row
    belongs to a single entity, and the duplicate is legitimate.
    """
    premiere = create_entity(name="A", slug="a")
    seconde = create_entity(name="B", slug="b")

    create_source(premiere)
    create_source(seconde)

    assert Source.objects.filter(label="Fictional Handbook of Test Myths").count() == 2
    assert premiere.sources.count() == 1
    assert seconde.sources.count() == 1


def test_doublon_exact_sur_la_meme_entite_est_autorise() -> None:
    """No uniqueness is enforced: two editions or uses may coincide.

    Discarding duplicates is a matter of editorial review, not of the
    database structure.
    """
    entity = create_entity()

    create_source(entity, url="https://example.invalid/fictional")
    create_source(entity, url="https://example.invalid/fictional")

    assert entity.sources.count() == 2


def test_representation_lisible() -> None:
    """`__str__` gives the reference, its nature and the entity."""
    source = create_source(create_entity(), label="Fictional Museum Catalogue")

    assert str(source) == "Fictional Museum Catalogue (book) — Shango"


# --- Champs facultatifs -------------------------------------------------


def test_source_sans_url_ni_date() -> None:
    """A book without a link stays valid: an empty `url` and `accessed_at=None`."""
    source = create_source(create_entity())

    source.full_clean()

    assert source.url == ""
    assert source.accessed_at is None
    assert source.notes == ""


def test_source_orale_sans_url() -> None:
    """An oral tradition has no URL, but may have a date and notes."""
    source = create_source(
        create_entity(),
        label="Fictional oral testimony, village of Testville",
        kind=SourceKind.ORAL,
        accessed_at=datetime.date(2026, 3, 14),
        notes="Fictional interview recorded for demonstration purposes.",
    )

    source.full_clean()

    assert source.kind == SourceKind.ORAL
    assert source.url == ""
    assert source.accessed_at == datetime.date(2026, 3, 14)
    assert source.notes.startswith("Fictional interview")


def test_date_de_consultation_sans_url() -> None:
    """`accessed_at` is a consultation date, independent of the URL."""
    source = create_source(create_entity(), accessed_at=datetime.date(2026, 1, 2))

    source.full_clean()

    assert source.url == ""
    assert source.accessed_at == datetime.date(2026, 1, 2)


def test_url_et_date_renseignees() -> None:
    """An online reference carries both."""
    source = create_source(
        create_entity(),
        label="Fictional Encyclopedia of Imaginary Myths",
        kind=SourceKind.ENCYCLOPEDIA,
        url="https://example.invalid/fictional-entry",
        accessed_at=datetime.date(2026, 5, 20),
    )

    source.full_clean()

    assert source.url == "https://example.invalid/fictional-entry"


def test_aucune_valeur_n_est_remplie_automatiquement() -> None:
    """Neither date nor reference is inferred on creation."""
    source = Source.objects.create(
        entity=create_entity(), label="Fictional Note", kind=SourceKind.OTHER
    )

    source.refresh_from_db()

    assert source.accessed_at is None
    assert source.url == ""
    assert source.notes == ""


# --- Validation ---------------------------------------------------------


@pytest.mark.parametrize("kind", SourceKind.values)
def test_tous_les_kinds_valides_sont_acceptes(kind: str) -> None:
    """The six intended natures pass `full_clean()`."""
    source = create_source(create_entity(), kind=kind)

    source.full_clean()

    assert source.kind == kind


def test_kind_inconnu_refuse_par_full_clean() -> None:
    """A nature outside the list is rejected by Django validation.

    Scope: `full_clean()` only. No PostgreSQL constraint bears on `kind`.
    """
    source = Source(entity=create_entity(), label="Fictional Note", kind="podcast")

    with pytest.raises(ValidationError) as excinfo:
        source.full_clean()

    assert "kind" in excinfo.value.message_dict


def test_libelle_obligatoire_refuse_par_full_clean() -> None:
    """An empty `label` is rejected by Django validation."""
    source = Source(entity=create_entity(), label="", kind=SourceKind.BOOK)

    with pytest.raises(ValidationError) as excinfo:
        source.full_clean()

    assert "label" in excinfo.value.message_dict


def test_libelle_blanc_refuse_par_full_clean() -> None:
    """A `label` made of spaces only is rejected.

    Exact scope: this rule lives in `clean()` only. A blank-filled string is
    not the empty string, so no database constraint intercepts it - a direct
    create with such a label would be accepted.
    """
    source = Source(entity=create_entity(), label="   ", kind=SourceKind.BOOK)

    with pytest.raises(ValidationError) as excinfo:
        source.full_clean()

    assert "label" in excinfo.value.message_dict


def test_libelle_blanc_passe_en_ecriture_directe() -> None:
    """Document the limit: the database does not stop a blank label.

    This test pins the real behaviour down rather than letting a guarantee be
    assumed. Normalisation will fall to the import service.
    """
    source = Source.objects.create(
        entity=create_entity(), label="   ", kind=SourceKind.BOOK
    )

    source.refresh_from_db()

    assert source.label == "   "


def test_libelle_est_normalise_par_clean() -> None:
    """`clean()` strips the edge whitespace of a valid label."""
    source = Source(
        entity=create_entity(),
        label="  Fictional Handbook  ",
        kind=SourceKind.BOOK,
    )

    source.full_clean()

    assert source.label == "Fictional Handbook"


def test_url_invalide_refusee_par_full_clean() -> None:
    """The URL format is checked by `URLField`, through `full_clean()`.

    No network access takes place: the availability of the link is not
    tested, only its shape is.
    """
    source = Source(
        entity=create_entity(),
        label="Fictional Note",
        kind=SourceKind.ARTICLE,
        url="pas-une-url",
    )

    with pytest.raises(ValidationError) as excinfo:
        source.full_clean()

    assert "url" in excinfo.value.message_dict


# --- Suppressions -------------------------------------------------------


def test_suppression_de_l_entite_supprime_ses_sources() -> None:
    """`CASCADE`: the physical deletion of a record removes its sources."""
    entity = create_entity()
    create_source(entity)
    create_source(entity, label="Second Fictional Reference")

    entity.delete()

    assert Source.objects.count() == 0


def test_suppression_d_une_source_conserve_l_entite() -> None:
    """Deleting a source touches neither the record nor its other sources."""
    entity = create_entity()
    premiere = create_source(entity)
    create_source(entity, label="Second Fictional Reference")

    premiere.delete()

    assert Entity.objects.filter(pk=entity.pk).exists()
    assert entity.sources.count() == 1


def test_sources_portees_par_un_heros() -> None:
    """Sources are not reserved for divinities."""
    hero = create_hero()

    create_source(hero, label="Fictional Chronicle of Test Heroes")

    assert hero.sources.count() == 1
