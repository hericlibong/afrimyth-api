"""Tests des variantes culturelles et des relations entre figures.

Chaque règle est testée à la portée où elle s'applique réellement : les
contraintes de base par un `save()` direct attendant une `IntegrityError`, les
validations de formulaire par `full_clean()` attendant une `ValidationError`.
Les deux ne protègent pas les mêmes chemins d'écriture.
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
    """La variante ne reçoit rien de sa référence : ni textes, ni rattachements."""
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
    """Aucune contrainte d'égalité des types n'est posée.

    Une forme régionale peut être une divinité là où la figure de référence
    est une créature, conformément à la décision 3 de l'ADR 0002.
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
    """Une entité sans référence reste valide."""
    entity = create_entity()

    entity.full_clean()

    assert entity.variant_of is None
    assert list(entity.variants.all()) == []


def test_auto_reference_refusee_par_full_clean() -> None:
    """`full_clean()` donne un message lisible plutôt qu'une erreur de base."""
    entity = create_entity()
    entity.variant_of = entity

    with pytest.raises(ValidationError) as excinfo:
        entity.full_clean()

    assert "variant_of" in excinfo.value.message_dict


def test_auto_reference_refusee_en_base() -> None:
    """La `CheckConstraint` arrête aussi un `save()` direct.

    C'est la seule garantie réelle : elle s'applique sans passer par un
    formulaire.
    """
    entity = create_entity()
    entity.variant_of = entity

    with pytest.raises(IntegrityError), transaction.atomic():
        entity.save()


def test_suppression_d_une_reference_est_protegee() -> None:
    """`PROTECT` empêche la suppression physique d'une figure citée."""
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
    """Documente une limite assumée : A → B → A n'est pas refusé.

    Seule l'auto-référence directe est interdite. Détecter les cycles
    indirects demanderait un parcours récursif, hors périmètre. Ce test fixe
    le comportement réel pour qu'il soit constaté, non découvert plus tard.
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
    """`A — parent → B` signifie « B est un parent de A ».

    Ce test est le garde-fou contre une inversion à l'import : s'il échoue,
    c'est que le sens a été retourné quelque part.
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
    """Un `parent` ne génère pas de `child`, ni un allié sa réciproque."""
    a = create_entity(name="A", slug="a")
    b = create_entity(name="B", slug="b")

    create_relation(a, RelationKind.PARENT, to_entity=b)
    create_relation(a, RelationKind.ALLY, to_entity=b)

    assert EntityRelation.objects.count() == 2
    assert EntityRelation.objects.filter(from_entity=b).count() == 0


# --- Relations : cibles résolues et citées ------------------------------


def test_relation_vers_une_fiche_existante() -> None:
    """Une cible résolue laisse `to_name` vide."""
    source = create_entity(name="A", slug="a")
    cible = create_entity(name="B", slug="b")

    lien = create_relation(source, RelationKind.CONSORT, to_entity=cible)

    assert lien.to_entity == cible
    assert lien.to_name == ""


def test_relation_vers_une_figure_sans_fiche() -> None:
    """Une cible citée conserve son nom brut, sans fiche.

    C'est le cas majoritaire du corpus V2 : les noms cités désignent souvent
    des figures absentes.
    """
    source = create_entity()

    lien = create_relation(source, RelationKind.PARENT, to_name="Yemoja")

    assert lien.to_entity is None
    assert lien.to_name == "Yemoja"
    assert str(lien) == "Shango — parent → Yemoja"


def test_aucun_rapprochement_automatique_par_nom() -> None:
    """Créer la fiche homonyme ne résout pas le lien existant.

    Aucune résolution par nom n'est tentée : les noms sont ambigus, et une
    fusion automatique serait une perte de donnée.
    """
    source = create_entity(name="A", slug="a")
    lien = create_relation(source, RelationKind.PARENT, to_name="Yemoja")

    create_entity(name="Yemoja", slug="yemoja")
    lien.refresh_from_db()

    assert lien.to_entity is None
    assert lien.to_name == "Yemoja"


# --- Relations : exclusivité de la cible --------------------------------


def test_deux_cibles_refusees_en_base() -> None:
    """La contrainte interdit une fiche *et* un nom."""
    source = create_entity(name="A", slug="a")
    cible = create_entity(name="B", slug="b")

    with pytest.raises(IntegrityError), transaction.atomic():
        create_relation(source, RelationKind.PARENT, to_entity=cible, to_name="Yemoja")


def test_aucune_cible_refusee_en_base() -> None:
    """La contrainte interdit l'absence des deux."""
    source = create_entity()

    with pytest.raises(IntegrityError), transaction.atomic():
        create_relation(source, RelationKind.PARENT)


def test_deux_cibles_refusees_par_full_clean() -> None:
    """`full_clean()` signale le même cas avec un message de formulaire."""
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
    """Même chose pour une relation sans cible du tout."""
    lien = EntityRelation(from_entity=create_entity(), kind=RelationKind.PARENT)

    with pytest.raises(ValidationError) as excinfo:
        lien.full_clean()

    assert "to_name" in excinfo.value.message_dict


def test_nom_compose_d_espaces_refuse_par_full_clean() -> None:
    """Un nom blanc est traité comme une absence de cible.

    Cette règle n'existe que dans `clean()` : `"   "` n'est pas la chaîne
    vide, donc la contrainte de base le laisserait passer.
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
    """`clean()` retire les espaces de bord d'un nom valide."""
    lien = EntityRelation(
        from_entity=create_entity(),
        kind=RelationKind.PARENT,
        to_name="  Yemoja  ",
    )

    lien.full_clean()

    assert lien.to_name == "Yemoja"


# --- Relations : auto-lien et doublons ----------------------------------


def test_auto_lien_resolu_refuse_en_base() -> None:
    """Une entité ne peut pas être liée à elle-même par une cible résolue."""
    entity = create_entity()

    with pytest.raises(IntegrityError), transaction.atomic():
        create_relation(entity, RelationKind.ALLY, to_entity=entity)


def test_auto_lien_resolu_refuse_par_full_clean() -> None:
    """`full_clean()` donne le message correspondant."""
    entity = create_entity()
    lien = EntityRelation(from_entity=entity, kind=RelationKind.ALLY, to_entity=entity)

    with pytest.raises(ValidationError) as excinfo:
        lien.full_clean()

    assert "to_entity" in excinfo.value.message_dict


def test_doublon_de_lien_resolu_refuse() -> None:
    """`(from_entity, to_entity, kind)` est unique pour les liens résolus."""
    source = create_entity(name="A", slug="a")
    cible = create_entity(name="B", slug="b")
    create_relation(source, RelationKind.PARENT, to_entity=cible)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_relation(source, RelationKind.PARENT, to_entity=cible)


def test_doublon_de_lien_non_resolu_refuse() -> None:
    """`(from_entity, to_name, kind)` est unique pour les liens cités."""
    source = create_entity()
    create_relation(source, RelationKind.PARENT, to_name="Yemoja")

    with pytest.raises(IntegrityError), transaction.atomic():
        create_relation(source, RelationKind.PARENT, to_name="Yemoja")


def test_plusieurs_types_pour_une_meme_paire() -> None:
    """Seul le triplet est unique : une paire peut porter plusieurs types."""
    source = create_entity(name="A", slug="a")
    cible = create_entity(name="B", slug="b")

    create_relation(source, RelationKind.PARENT, to_entity=cible)
    create_relation(source, RelationKind.ALLY, to_entity=cible)
    create_relation(source, RelationKind.ENEMY, to_entity=cible)

    assert source.relations_from.count() == 3


def test_meme_nom_cite_sous_deux_types() -> None:
    """La même unicité s'applique aux liens cités, par type."""
    source = create_entity()

    create_relation(source, RelationKind.PARENT, to_name="Yemoja")
    create_relation(source, RelationKind.ENEMY, to_name="Yemoja")

    assert source.relations_from.count() == 2


def test_deux_sources_peuvent_citer_le_meme_nom() -> None:
    """L'unicité est portée par la source, pas par le nom seul."""
    a = create_entity(name="A", slug="a")
    b = create_entity(name="B", slug="b")

    create_relation(a, RelationKind.PARENT, to_name="Yemoja")
    create_relation(b, RelationKind.PARENT, to_name="Yemoja")

    assert EntityRelation.objects.filter(to_name="Yemoja").count() == 2


# --- Suppression --------------------------------------------------------


def test_suppression_de_la_source_supprime_ses_liens() -> None:
    """`CASCADE` sur `from_entity` : les liens sortants disparaissent."""
    source = create_entity(name="A", slug="a")
    cible = create_entity(name="B", slug="b")
    create_relation(source, RelationKind.PARENT, to_entity=cible)

    source.delete()

    assert EntityRelation.objects.count() == 0
    assert Entity.objects.filter(pk=cible.pk).exists()


def test_suppression_de_la_cible_supprime_le_lien() -> None:
    """`CASCADE` sur `to_entity` : le lien disparaît avec la cible.

    Portée à connaître : une suppression **physique** d'une cible efface les
    liens qui la citaient, sans les dégrader en `to_name`. L'API V1 utilisera
    la suppression logique, non implémentée dans cet incrément.
    """
    source = create_entity(name="A", slug="a")
    cible = create_entity(name="B", slug="b")
    create_relation(source, RelationKind.PARENT, to_entity=cible)

    cible.delete()

    assert EntityRelation.objects.count() == 0
    assert Entity.objects.filter(pk=source.pk).exists()


def test_types_de_relation_disponibles() -> None:
    """Les cinq types prévus sont déclarés, avec des libellés anglais."""
    assert RelationKind.values == ["parent", "child", "consort", "ally", "enemy"]
    assert RelationKind.PARENT.label == "Parent"
    assert RelationKind.CONSORT.label == "Consort"


def test_type_inconnu_refuse_par_full_clean() -> None:
    """Un `kind` hors liste est rejeté par `full_clean()`."""
    lien = EntityRelation(from_entity=create_entity(), kind="rival", to_name="Yemoja")

    with pytest.raises(ValidationError) as excinfo:
        lien.full_clean()

    assert "kind" in excinfo.value.message_dict


def test_ordre_deterministe_des_relations() -> None:
    """`Meta.ordering` donne un ordre stable : `kind`, puis `to_name`, puis `id`."""
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
    """Les relations ne sont pas réservées aux divinités."""
    hero = create_hero()
    ennemi = create_creature()

    create_relation(hero, RelationKind.ENEMY, to_entity=ennemi)

    assert hero.relations_from.count() == 1
