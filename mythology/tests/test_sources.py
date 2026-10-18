"""Tests des sources documentaires.

**Toutes les références employées ici sont fictives**, inventées pour la
démonstration. Aucune publication réelle n'est citée, et aucune source n'est
attribuée à une figure du corpus.

Chaque règle est testée à sa portée réelle : la validation Django par
`full_clean()`, la cascade et les champs obligatoires côté base là où ils le
sont effectivement.
"""

import datetime

import pytest
from django.core.exceptions import ValidationError

from mythology.models import Entity, Source, SourceKind
from mythology.tests.factories import create_entity, create_hero, create_source

pytestmark = pytest.mark.django_db


# --- Création et rattachement -------------------------------------------


def test_plusieurs_sources_pour_une_entite() -> None:
    """Une entité porte zéro ou plusieurs sources, ordonnées par référence."""
    entity = create_entity()
    create_source(entity, label="Zeta Fictional Review", kind=SourceKind.ARTICLE)
    create_source(entity, label="Alpha Fictional Encyclopedia")

    labels = [source.label for source in entity.sources.all()]

    assert labels == ["Alpha Fictional Encyclopedia", "Zeta Fictional Review"]


def test_entite_sans_source() -> None:
    """Aucune source n'est requise."""
    entity = create_entity()

    assert entity.sources.count() == 0


def test_meme_reference_sur_deux_entites() -> None:
    """La même référence peut être saisie pour deux fiches.

    Il n'y a ni catalogue partagé ni relation plusieurs-à-plusieurs : chaque
    ligne appartient à une seule entité, et le doublon est légitime.
    """
    premiere = create_entity(name="A", slug="a")
    seconde = create_entity(name="B", slug="b")

    create_source(premiere)
    create_source(seconde)

    assert Source.objects.filter(label="Fictional Handbook of Test Myths").count() == 2
    assert premiere.sources.count() == 1
    assert seconde.sources.count() == 1


def test_doublon_exact_sur_la_meme_entite_est_autorise() -> None:
    """Aucune unicité n'est posée : deux éditions ou usages peuvent coïncider.

    Écarter les doublons relève du contrôle éditorial, pas de la structure de
    la base.
    """
    entity = create_entity()

    create_source(entity, url="https://example.invalid/fictional")
    create_source(entity, url="https://example.invalid/fictional")

    assert entity.sources.count() == 2


def test_representation_lisible() -> None:
    """`__str__` donne la référence, sa nature et l'entité."""
    source = create_source(create_entity(), label="Fictional Museum Catalogue")

    assert str(source) == "Fictional Museum Catalogue (book) — Shango"


# --- Champs facultatifs -------------------------------------------------


def test_source_sans_url_ni_date() -> None:
    """Un ouvrage sans lien reste valide : `url=""` et `accessed_at=None`."""
    source = create_source(create_entity())

    source.full_clean()

    assert source.url == ""
    assert source.accessed_at is None
    assert source.notes == ""


def test_source_orale_sans_url() -> None:
    """Une tradition orale n'a pas d'URL, mais peut avoir une date et des notes."""
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
    """`accessed_at` est une date de consultation, indépendante de l'URL."""
    source = create_source(create_entity(), accessed_at=datetime.date(2026, 1, 2))

    source.full_clean()

    assert source.url == ""
    assert source.accessed_at == datetime.date(2026, 1, 2)


def test_url_et_date_renseignees() -> None:
    """Une référence en ligne porte les deux."""
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
    """Ni date ni référence ne sont déduites à la création."""
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
    """Les six natures prévues passent `full_clean()`."""
    source = create_source(create_entity(), kind=kind)

    source.full_clean()

    assert source.kind == kind


def test_kind_inconnu_refuse_par_full_clean() -> None:
    """Une nature hors liste est rejetée par la validation Django.

    Portée : `full_clean()` seulement. Aucune contrainte PostgreSQL ne porte
    sur `kind`.
    """
    source = Source(entity=create_entity(), label="Fictional Note", kind="podcast")

    with pytest.raises(ValidationError) as excinfo:
        source.full_clean()

    assert "kind" in excinfo.value.message_dict


def test_libelle_obligatoire_refuse_par_full_clean() -> None:
    """Un `label` vide est rejeté par la validation Django."""
    source = Source(entity=create_entity(), label="", kind=SourceKind.BOOK)

    with pytest.raises(ValidationError) as excinfo:
        source.full_clean()

    assert "label" in excinfo.value.message_dict


def test_libelle_blanc_refuse_par_full_clean() -> None:
    """Un `label` composé uniquement d'espaces est rejeté.

    Portée exacte : cette règle n'existe que dans `clean()`. `"   "` n'est pas
    la chaîne vide, donc aucune contrainte de base ne l'intercepte —
    `objects.create(label="   ")` serait accepté.
    """
    source = Source(entity=create_entity(), label="   ", kind=SourceKind.BOOK)

    with pytest.raises(ValidationError) as excinfo:
        source.full_clean()

    assert "label" in excinfo.value.message_dict


def test_libelle_blanc_passe_en_ecriture_directe() -> None:
    """Documente la limite : la base n'arrête pas un libellé blanc.

    Ce test fixe le comportement réel plutôt que de laisser croire à une
    garantie. La normalisation incombera au service d'import.
    """
    source = Source.objects.create(
        entity=create_entity(), label="   ", kind=SourceKind.BOOK
    )

    source.refresh_from_db()

    assert source.label == "   "


def test_libelle_est_normalise_par_clean() -> None:
    """`clean()` retire les espaces de bord d'un libellé valide."""
    source = Source(
        entity=create_entity(),
        label="  Fictional Handbook  ",
        kind=SourceKind.BOOK,
    )

    source.full_clean()

    assert source.label == "Fictional Handbook"


def test_url_invalide_refusee_par_full_clean() -> None:
    """Le format de l'URL est vérifié par `URLField`, via `full_clean()`.

    Aucun accès réseau n'a lieu : la disponibilité du lien n'est pas testée,
    seule sa forme l'est.
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
    """`CASCADE` : la suppression physique d'une fiche retire ses sources."""
    entity = create_entity()
    create_source(entity)
    create_source(entity, label="Second Fictional Reference")

    entity.delete()

    assert Source.objects.count() == 0


def test_suppression_d_une_source_conserve_l_entite() -> None:
    """Supprimer une source ne touche ni la fiche ni ses autres sources."""
    entity = create_entity()
    premiere = create_source(entity)
    create_source(entity, label="Second Fictional Reference")

    premiere.delete()

    assert Entity.objects.filter(pk=entity.pk).exists()
    assert entity.sources.count() == 1


def test_sources_portees_par_un_heros() -> None:
    """Les sources ne sont pas réservées aux divinités."""
    hero = create_hero()

    create_source(hero, label="Fictional Chronicle of Test Heroes")

    assert hero.sources.count() == 1
