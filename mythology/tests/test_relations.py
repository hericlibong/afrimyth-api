"""Tests of the cultural variants and of the relations between figures.

Each rule is tested at the scope where it really applies: the database
constraints through a direct `save()` expecting an `IntegrityError`, the
form validations through `full_clean()` expecting a `ValidationError`.
The two do not protect the same write paths.
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from mythology.models import Entity, EntityRelation, EntityType, RelationKind
from mythology.tests.factories import (
    create_creature,
    create_entity,
    create_hero,
    create_relation,
)

pytestmark = pytest.mark.django_db


# --- Variantes culturelles ----------------------------------------------


def test_variante_est_une_entite_autonome() -> None:
    """The variant inherits nothing from its reference: no text, no attachment."""
    reference = create_entity(name="Mami Wata", slug="mami-wata")
    variante = create_entity(
        name="Mami Wata (Caribbean)",
        slug="mami-wata-caribbean",
        story_description="Récit propre à la variante.",
        variant_of=reference,
    )

    reference.refresh_from_db()

    assert variante.variant_of == reference
    assert list(reference.variants.all()) == [variante]
    assert reference.story_description == ""
    assert reference.variant_of is None


def test_variante_peut_avoir_un_autre_type() -> None:
    """No constraint of type equality is enforced.

    A regional form may be a divinity where the reference figure is a
    creature, as stated by decision 3 of ADR 0002.
    """
    creature = create_creature(name="Mami Wata", slug="mami-wata")
    divinite = create_entity(
        name="Mami Wata (Vodun)",
        slug="mami-wata-vodun",
        variant_of=creature,
    )

    divinite.full_clean()

    assert divinite.entity_type == EntityType.DIVINITY
    assert divinite.variant_of is not None
    assert divinite.variant_of.entity_type == EntityType.CREATURE


def test_variant_of_est_facultatif() -> None:
    """An entity without a reference stays valid."""
    entity = create_entity()

    entity.full_clean()

    assert entity.variant_of is None
    assert list(entity.variants.all()) == []


def test_auto_reference_refusee_par_full_clean() -> None:
    """`full_clean()` gives a readable message rather than a database error."""
    entity = create_entity()
    entity.variant_of = entity

    with pytest.raises(ValidationError) as excinfo:
        entity.full_clean()

    assert "variant_of" in excinfo.value.message_dict


def test_auto_reference_refusee_en_base() -> None:
    """The `CheckConstraint` also stops a direct `save()`.

    This is the only real guarantee: it applies without going through a form.
    """
    entity = create_entity()
    entity.variant_of = entity

    with pytest.raises(IntegrityError), transaction.atomic():
        entity.save()


def test_suppression_d_une_reference_est_protegee() -> None:
    """`PROTECT` prevents the physical deletion of a cited figure."""
    reference = create_entity(name="Mami Wata", slug="mami-wata")
    create_entity(
        name="Mami Wata (Caribbean)",
        slug="mami-wata-caribbean",
        variant_of=reference,
    )

    with pytest.raises(ProtectedError):
        reference.delete()

    assert Entity.objects.filter(pk=reference.pk).exists()


def test_cycle_indirect_de_variantes_n_est_pas_detecte() -> None:
    """Document an accepted limit: A to B to A is not refused.

    Only the direct self-reference is forbidden. Detecting indirect cycles
    would require a recursive traversal, out of scope. This test pins the real
    behaviour down so that it is observed, not discovered later.
    """
    a = create_entity(name="A", slug="a")
    b = create_entity(name="B", slug="b", variant_of=a)
    a.variant_of = b
    a.save()

    a.refresh_from_db()

    assert a.variant_of == b
    assert b.variant_of == a


# --- Relations : sens de lecture ----------------------------------------


def test_sens_de_lecture_de_la_relation() -> None:
    """`A - parent -> B` means that B is a parent of A.

    This test is the safeguard against a reversal at import time: if it
    fails, the direction has been flipped somewhere.
    """
    enfant = create_entity(name="Shango", slug="shango")
    pere = create_entity(name="Oranyan", slug="oranyan")

    lien = create_relation(enfant, RelationKind.PARENT, to_entity=pere)

    assert lien.from_entity == enfant
    assert lien.to_entity == pere
    assert str(lien) == "Shango — parent → Oranyan"
    # Le parent n'a reçu aucune ligne : le lien est unidirectionnel.
    assert list(pere.relations_from.all()) == []
    assert list(pere.relations_to.all()) == [lien]


def test_aucune_relation_inverse_n_est_creee() -> None:
    """A `parent` generates no `child`, and an ally no counterpart."""
    a = create_entity(name="A", slug="a")
    b = create_entity(name="B", slug="b")

    create_relation(a, RelationKind.PARENT, to_entity=b)
    create_relation(a, RelationKind.ALLY, to_entity=b)

    assert EntityRelation.objects.count() == 2
    assert EntityRelation.objects.filter(from_entity=b).count() == 0


# --- Relations : cibles résolues et citées ------------------------------


def test_relation_vers_une_fiche_existante() -> None:
    """A resolved target leaves `to_name` empty."""
    source = create_entity(name="A", slug="a")
    cible = create_entity(name="B", slug="b")

    lien = create_relation(source, RelationKind.CONSORT, to_entity=cible)

    assert lien.to_entity == cible
    assert lien.to_name == ""


def test_relation_vers_une_figure_sans_fiche() -> None:
    """A cited target keeps its raw name, without a record.

    This is the majority case of the V2 corpus: the names cited often
    designate absent figures.
    """
    source = create_entity()

    lien = create_relation(source, RelationKind.PARENT, to_name="Yemoja")

    assert lien.to_entity is None
    assert lien.to_name == "Yemoja"
    assert str(lien) == "Shango — parent → Yemoja"


def test_aucun_rapprochement_automatique_par_nom() -> None:
    """Creating the homonymous record does not resolve the existing link.

    No resolution by name is attempted: names are ambiguous, and an automatic
    merge would be a loss of data.
    """
    source = create_entity(name="A", slug="a")
    lien = create_relation(source, RelationKind.PARENT, to_name="Yemoja")

    create_entity(name="Yemoja", slug="yemoja")
    lien.refresh_from_db()

    assert lien.to_entity is None
    assert lien.to_name == "Yemoja"


# --- Relations : exclusivité de la cible --------------------------------


def test_deux_cibles_refusees_en_base() -> None:
    """The constraint forbids a record *and* a name."""
    source = create_entity(name="A", slug="a")
    cible = create_entity(name="B", slug="b")

    with pytest.raises(IntegrityError), transaction.atomic():
        create_relation(source, RelationKind.PARENT, to_entity=cible, to_name="Yemoja")


def test_aucune_cible_refusee_en_base() -> None:
    """The constraint forbids the absence of both."""
    source = create_entity()

    with pytest.raises(IntegrityError), transaction.atomic():
        create_relation(source, RelationKind.PARENT)


def test_deux_cibles_refusees_par_full_clean() -> None:
    """`full_clean()` reports the same case with a form message."""
    source = create_entity(name="A", slug="a")
    cible = create_entity(name="B", slug="b")
    lien = EntityRelation(
        from_entity=source,
        kind=RelationKind.PARENT,
        to_entity=cible,
        to_name="Yemoja",
    )

    with pytest.raises(ValidationError) as excinfo:
        lien.full_clean()

    assert "to_name" in excinfo.value.message_dict


def test_aucune_cible_refusee_par_full_clean() -> None:
    """Same for a relation with no target at all."""
    lien = EntityRelation(from_entity=create_entity(), kind=RelationKind.PARENT)

    with pytest.raises(ValidationError) as excinfo:
        lien.full_clean()

    assert "to_name" in excinfo.value.message_dict


def test_nom_compose_d_espaces_refuse_par_full_clean() -> None:
    """A blank name is treated as a missing target.

    This rule lives in `clean()` only: a blank-filled string is not the empty
    string, so the database constraint would let it through.
    """
    lien = EntityRelation(
        from_entity=create_entity(),
        kind=RelationKind.PARENT,
        to_name="   ",
    )

    with pytest.raises(ValidationError) as excinfo:
        lien.full_clean()

    assert "to_name" in excinfo.value.message_dict


def test_nom_cible_est_normalise_par_clean() -> None:
    """`clean()` strips the edge whitespace of a valid name."""
    lien = EntityRelation(
        from_entity=create_entity(),
        kind=RelationKind.PARENT,
        to_name="  Yemoja  ",
    )

    lien.full_clean()

    assert lien.to_name == "Yemoja"


# --- Relations : auto-lien et doublons ----------------------------------


def test_auto_lien_resolu_refuse_en_base() -> None:
    """An entity cannot be linked to itself through a resolved target."""
    entity = create_entity()

    with pytest.raises(IntegrityError), transaction.atomic():
        create_relation(entity, RelationKind.ALLY, to_entity=entity)


def test_auto_lien_resolu_refuse_par_full_clean() -> None:
    """`full_clean()` gives the matching message."""
    entity = create_entity()
    lien = EntityRelation(from_entity=entity, kind=RelationKind.ALLY, to_entity=entity)

    with pytest.raises(ValidationError) as excinfo:
        lien.full_clean()

    assert "to_entity" in excinfo.value.message_dict


def test_doublon_de_lien_resolu_refuse() -> None:
    """`(from_entity, to_entity, kind)` is unique for resolved links."""
    source = create_entity(name="A", slug="a")
    cible = create_entity(name="B", slug="b")
    create_relation(source, RelationKind.PARENT, to_entity=cible)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_relation(source, RelationKind.PARENT, to_entity=cible)


def test_doublon_de_lien_non_resolu_refuse() -> None:
    """`(from_entity, to_name, kind)` is unique for cited links."""
    source = create_entity()
    create_relation(source, RelationKind.PARENT, to_name="Yemoja")

    with pytest.raises(IntegrityError), transaction.atomic():
        create_relation(source, RelationKind.PARENT, to_name="Yemoja")


def test_plusieurs_types_pour_une_meme_paire() -> None:
    """Only the triple is unique: a pair may carry several kinds."""
    source = create_entity(name="A", slug="a")
    cible = create_entity(name="B", slug="b")

    create_relation(source, RelationKind.PARENT, to_entity=cible)
    create_relation(source, RelationKind.ALLY, to_entity=cible)
    create_relation(source, RelationKind.ENEMY, to_entity=cible)

    assert source.relations_from.count() == 3


def test_meme_nom_cite_sous_deux_types() -> None:
    """The same uniqueness applies to cited links, per kind."""
    source = create_entity()

    create_relation(source, RelationKind.PARENT, to_name="Yemoja")
    create_relation(source, RelationKind.ENEMY, to_name="Yemoja")

    assert source.relations_from.count() == 2


def test_deux_sources_peuvent_citer_le_meme_nom() -> None:
    """Uniqueness is carried by the source, not by the name alone."""
    a = create_entity(name="A", slug="a")
    b = create_entity(name="B", slug="b")

    create_relation(a, RelationKind.PARENT, to_name="Yemoja")
    create_relation(b, RelationKind.PARENT, to_name="Yemoja")

    assert EntityRelation.objects.filter(to_name="Yemoja").count() == 2


# --- Suppression --------------------------------------------------------


def test_suppression_de_la_source_supprime_ses_liens() -> None:
    """`CASCADE` on `from_entity`: the outgoing links disappear."""
    source = create_entity(name="A", slug="a")
    cible = create_entity(name="B", slug="b")
    create_relation(source, RelationKind.PARENT, to_entity=cible)

    source.delete()

    assert EntityRelation.objects.count() == 0
    assert Entity.objects.filter(pk=cible.pk).exists()


def test_suppression_de_la_cible_supprime_le_lien() -> None:
    """`CASCADE` on `to_entity`: the link disappears with the target.

    A scope worth knowing: a **physical** deletion of a target erases the
    links that cited it, without degrading them into `to_name`. The V1 API
    will use logical deletion, not implemented in this increment.
    """
    source = create_entity(name="A", slug="a")
    cible = create_entity(name="B", slug="b")
    create_relation(source, RelationKind.PARENT, to_entity=cible)

    cible.delete()

    assert EntityRelation.objects.count() == 0
    assert Entity.objects.filter(pk=source.pk).exists()


def test_types_de_relation_disponibles() -> None:
    """The five intended kinds are declared, with English labels."""
    assert RelationKind.values == ["parent", "child", "consort", "ally", "enemy"]
    assert RelationKind.PARENT.label == "Parent"
    assert RelationKind.CONSORT.label == "Consort"


def test_type_inconnu_refuse_par_full_clean() -> None:
    """A `kind` outside the list is rejected by `full_clean()`."""
    lien = EntityRelation(from_entity=create_entity(), kind="rival", to_name="Yemoja")

    with pytest.raises(ValidationError) as excinfo:
        lien.full_clean()

    assert "kind" in excinfo.value.message_dict


def test_ordre_deterministe_des_relations() -> None:
    """`Meta.ordering` gives a stable order: `kind`, then `to_name`, then `id`."""
    source = create_entity(name="A", slug="a")
    cible = create_entity(name="B", slug="b")
    create_relation(source, RelationKind.PARENT, to_name="Zulu figure")
    create_relation(source, RelationKind.ALLY, to_entity=cible)
    create_relation(source, RelationKind.PARENT, to_name="Aba figure")

    ordre = [(lien.kind, lien.to_name) for lien in source.relations_from.all()]

    assert ordre == [
        ("ally", ""),
        ("parent", "Aba figure"),
        ("parent", "Zulu figure"),
    ]


def test_hero_peut_porter_des_relations() -> None:
    """Relations are not reserved for divinities."""
    hero = create_hero()
    ennemi = create_creature()

    create_relation(hero, RelationKind.ENEMY, to_entity=ennemi)

    assert hero.relations_from.count() == 1
