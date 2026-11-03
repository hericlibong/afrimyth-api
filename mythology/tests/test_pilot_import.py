"""Tests of the `import_mythology_pilot` command.

**Self-contained**: no test reads the real corpus. Each case writes its
own synthetic JSON into a temporary directory, shaped like the V2 corpus
but with invented content. The tests therefore stay runnable without the
`_audit` directory.

The three names of the selection - `Oya`, `Anansi`, `Mokele-mbembe` - are
on the other hand kept as they are, since that is precisely the selection
the command applies.
"""

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from mythology.management.commands.import_mythology_pilot import (
    clean_list,
    clean_text,
    reconcile_domains,
)
from mythology.models import (
    Country,
    CreatureProfile,
    CulturalArea,
    CulturalAreaKind,
    DivinityProfile,
    Domain,
    Entity,
    EntityRelation,
    EntityStatus,
    EntityType,
    Ethnicity,
    HeroProfile,
    RelationKind,
)
from mythology.serializers import EntityDetailSerializer
from mythology.tests.factories import create_entity, publish
from mythology.views import EntityViewSet

pytestmark = pytest.mark.django_db


# --- Jeux synthétiques --------------------------------------------------


def synthetic_divinity(**overrides: Any) -> dict[str, Any]:
    """A synthetic divinity, shaped exactly like the V2 corpus."""
    data: dict[str, Any] = {
        "entity_type": "Divinity",
        "name": "Oya",
        "category": "Synthetic subtitle",
        "origin": {
            "country": "Nigeria",
            "ethnicity": "Yoruba",
            "pantheon": "Synthetic pantheon",
            "cultural_region": "West Africa",
        },
        "identity": {
            "gender": "Female",
            "cultural_role": "Synthetic role",
            "alignment": "Lawful Neutral",
        },
        "attributes": {
            "domains": ["Wind", "Cemeteries"],
            "symbols": ["Synthetic symbol"],
            "power_objects": ["Synthetic object"],
            "symbolic_animals": ["Synthetic animal"],
        },
        "appearance": {
            "physical_signs": ["Synthetic sign"],
            "manifestations": "Synthetic manifestation.",
            "image_generation_prompt": "Synthetic prompt, must be ignored.",
            "imageUrl": "/synthetic/ignored.png",
        },
        "story": {
            "description": "Synthetic narrative.",
            "characteristics": ["Synthetic trait"],
        },
        "relations": {"parents": [], "conjoint": [], "descendants": []},
        "type_specific": {
            "divinity": {
                "cult": {"offerings": ["Synthetic offering"], "taboos": []},
                "domains": ["Wind", "Ceteris"],
            }
        },
        "rendering": {"prompt_canon": "Synthetic canon, must be ignored."},
    }
    data.update(overrides)
    return data


def synthetic_hero(**overrides: Any) -> dict[str, Any]:
    """A synthetic hero."""
    data: dict[str, Any] = {
        "entity_type": "Hero",
        "name": "Anansi",
        "category": "Synthetic subtitle",
        "origin": {
            "country": "Ghana",
            "ethnicity": "Akan",
            "pantheon": "Synthetic pantheon",
            "cultural_region": "West Africa",
        },
        "identity": {
            "gender": "Male",
            "cultural_role": "Synthetic role",
            "alignment": "Chaotic Neutral",
        },
        "attributes": {
            "domains": ["Stories"],
            "symbols": [],
            "power_objects": [],
            "symbolic_animals": [],
        },
        "appearance": {"physical_signs": [], "manifestations": ""},
        "story": {"description": "Synthetic narrative.", "characteristics": []},
        "relations": {"parents": [], "conjoint": [], "descendants": []},
        "type_specific": {
            "hero": {
                "titles": ["Synthetic title"],
                "achievements": ["Synthetic achievement"],
                "weapons_or_artifacts": ["Synthetic artifact"],
                "legacy": "Synthetic legacy.",
            }
        },
    }
    data.update(overrides)
    return data


def synthetic_creature(**overrides: Any) -> dict[str, Any]:
    """A synthetic creature, whose origin is an area and not a country."""
    data: dict[str, Any] = {
        "entity_type": "Creature",
        "name": "Mokele-mbembe",
        "category": "Synthetic subtitle",
        "origin": {
            "country": "Congo Basin",
            "ethnicity": "Bakwele",
            "pantheon": "Synthetic pantheon",
            "cultural_region": "Central Africa",
        },
        "identity": {
            "gender": "Neutral",
            "cultural_role": "Synthetic role",
            "alignment": "True Neutral",
        },
        "attributes": {
            "domains": ["Water"],
            "symbols": [],
            # Marqueur d'absence, tel qu'il figure dans le corpus réel.
            "power_objects": ["None"],
            "symbolic_animals": [],
        },
        "appearance": {"physical_signs": [], "manifestations": ""},
        "story": {"description": "Synthetic narrative.", "characteristics": []},
        "relations": {"parents": [], "conjoint": [], "descendants": []},
        "type_specific": {
            "creature": {
                "habitat": ["Synthetic habitat"],
                "powers": [],
                "strengths": [],
                "weaknesses": [],
                "diet": "Synthetic diet",
                "size": "Synthetic size",
            }
        },
    }
    data.update(overrides)
    return data


def write_corpus(tmp_path: Path, entries: list[dict[str, Any]]) -> str:
    """Write a synthetic corpus and return its path."""
    path = tmp_path / "synthetic_corpus.json"
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return str(path)


def full_corpus(tmp_path: Path, **kwargs: Any) -> str:
    """A complete synthetic corpus: the three records of the selection."""
    return write_corpus(
        tmp_path,
        [synthetic_divinity(**kwargs), synthetic_hero(), synthetic_creature()],
    )


# --- Fonctions de transformation ---------------------------------------


def test_clean_list_ecarte_les_marqueurs_d_absence() -> None:
    """A placeholder list is an absence, not a power object."""
    notes: list[str] = []

    assert clean_list(["None", "Real"], label="x", notes=notes) == ["Real"]
    assert any("placeholder" in note for note in notes)


def test_clean_list_deduplique_en_conservant_l_ordre() -> None:
    notes: list[str] = []

    assert clean_list(["B", "A", "B"], label="x", notes=notes) == ["B", "A"]
    assert any("duplicate" in note for note in notes)


def test_clean_list_signale_une_valeur_nulle() -> None:
    notes: list[str] = []

    assert clean_list(None, label="x", notes=notes) == []
    assert any("null value" in note for note in notes)


def test_clean_list_signale_une_forme_inattendue() -> None:
    """A string instead of a list is reported, not guessed."""
    notes: list[str] = []

    assert clean_list("Wind", label="x", notes=notes) == []
    assert any("unexpected shape" in note for note in notes)


def test_clean_list_conserve_l_unicode() -> None:
    """Non-ASCII characters go through the import unaltered."""
    notes: list[str] = []

    assert clean_list(["Ṣàngó", "Mmuo"], label="x", notes=notes) == ["Ṣàngó", "Mmuo"]


def test_clean_text_signale_une_valeur_nulle() -> None:
    notes: list[str] = []

    assert clean_text(None, label="x", notes=notes) == ""
    assert any("null value" in note for note in notes)


def test_domaines_reconcilies_avec_correction() -> None:
    """Deduplicated union, `Ceteris` corrected, synonyms kept."""
    notes: list[str] = []
    item = {
        "attributes": {"domains": ["Wind", "Cemeteries", "Transformation"]},
        "type_specific": {"divinity": {"domains": ["Wind", "Ceteris", "Change"]}},
    }

    domains = reconcile_domains(item, name="Synthetic", notes=notes)

    assert domains == ["Wind", "Cemeteries", "Transformation", "Change"]
    assert any("corrected to 'Cemeteries'" in note for note in notes)
    # `Change` et `Transformation` coexistent : aucune fusion automatique.
    assert "Change" in domains and "Transformation" in domains


def test_domaines_sans_bloc_divinite() -> None:
    """A missing `divinity` block is not reported as an anomaly."""
    notes: list[str] = []
    item = {"attributes": {"domains": ["Stories"]}, "type_specific": {"hero": {}}}

    assert reconcile_domains(item, name="Synthetic", notes=notes) == ["Stories"]
    assert not any("divinity.domains" in note for note in notes)


# --- Import des trois types --------------------------------------------


def test_import_des_trois_types(tmp_path: Path) -> None:
    """The three records are created, each with its single profile."""
    call_command("import_mythology_pilot", input=full_corpus(tmp_path))

    oya = Entity.objects.get(slug="oya")
    anansi = Entity.objects.get(slug="anansi")
    mokele = Entity.objects.get(slug="mokele-mbembe")

    assert oya.entity_type == EntityType.DIVINITY
    assert anansi.entity_type == EntityType.HERO
    assert mokele.entity_type == EntityType.CREATURE
    assert DivinityProfile.objects.count() == 1
    assert HeroProfile.objects.count() == 1
    assert CreatureProfile.objects.count() == 1
    assert not hasattr(oya, "hero_profile")
    assert not hasattr(anansi, "divinity_profile")


def test_les_champs_du_tronc_commun_sont_conserves(tmp_path: Path) -> None:
    """Texts and lists of the common trunk reach the database intact."""
    call_command("import_mythology_pilot", input=full_corpus(tmp_path))

    oya = Entity.objects.get(slug="oya")

    assert oya.category == "Synthetic subtitle"
    assert oya.cultural_role == "Synthetic role"
    assert oya.alignment == "Lawful Neutral"
    assert oya.story_description == "Synthetic narrative."
    assert oya.characteristics == ["Synthetic trait"]
    assert oya.physical_signs == ["Synthetic sign"]
    assert oya.symbols == ["Synthetic symbol"]
    assert oya.power_objects == ["Synthetic object"]
    assert oya.symbolic_animals == ["Synthetic animal"]
    assert oya.manifestations == "Synthetic manifestation."


def test_les_profils_recoivent_leurs_champs(tmp_path: Path) -> None:
    """Each profile receives the fields of its `type_specific` block."""
    call_command("import_mythology_pilot", input=full_corpus(tmp_path))

    oya = Entity.objects.get(slug="oya")
    anansi = Entity.objects.get(slug="anansi")
    mokele = Entity.objects.get(slug="mokele-mbembe")

    assert oya.divinity_profile.cult_offerings == ["Synthetic offering"]
    # Clé absente du corpus : la valeur par défaut du modèle s'applique.
    assert oya.divinity_profile.cult_rituals == []
    assert anansi.hero_profile.titles == ["Synthetic title"]
    assert anansi.hero_profile.legacy == "Synthetic legacy."
    assert anansi.hero_profile.quests == []
    assert mokele.creature_profile.habitat == ["Synthetic habitat"]
    assert mokele.creature_profile.diet == "Synthetic diet"
    assert mokele.creature_profile.threat_level is None


def test_les_fiches_importees_sont_en_draft(tmp_path: Path) -> None:
    """No public status, no owner, no review mark."""
    call_command("import_mythology_pilot", input=full_corpus(tmp_path))

    for entity in Entity.objects.all():
        assert entity.status == EntityStatus.DRAFT
        assert entity.created_by is None
        assert entity.reviewed_by is None
        assert entity.reviewed_at is None
        assert entity.deleted_at is None
        assert entity.sources.count() == 0


def test_les_donnees_de_rendu_ne_sont_pas_importees(tmp_path: Path) -> None:
    """`rendering`, the image prompt and `imageUrl` stay out of the model."""
    call_command("import_mythology_pilot", input=full_corpus(tmp_path))

    oya = Entity.objects.get(slug="oya")
    stored = " ".join(
        [oya.story_description, oya.manifestations, oya.category, *oya.symbols]
    )

    assert "prompt" not in stored.lower()
    assert "ignored" not in stored.lower()


# --- Référentiels -------------------------------------------------------


def test_les_aires_de_reference_sont_preparees(tmp_path: Path) -> None:
    """The four regions, the diaspora and the sub-region are created."""
    call_command("import_mythology_pilot", input=full_corpus(tmp_path))

    noms = set(CulturalArea.objects.values_list("name", flat=True))

    assert {
        "West Africa",
        "Central Africa",
        "East Africa",
        "Southern Africa",
        "Diaspora",
        "Congo Basin",
    } <= noms
    assert CulturalArea.objects.get(name="Diaspora").kind == CulturalAreaKind.DIASPORIC
    assert CulturalArea.objects.get(name="West Africa").parent is None


def test_la_sous_region_est_rattachee_a_sa_region(tmp_path: Path) -> None:
    """`Congo Basin` is an African region whose parent is Central Africa."""
    call_command("import_mythology_pilot", input=full_corpus(tmp_path))

    congo = CulturalArea.objects.get(name="Congo Basin")

    assert congo.kind == CulturalAreaKind.AFRICAN_REGION
    assert congo.parent is not None
    assert congo.parent.name == "Central Africa"


def test_une_aire_geographique_ne_devient_pas_un_pays(tmp_path: Path) -> None:
    """`Congo Basin` does not enter `Country` and leaves the country null.

    This is decision 2 of ADR 0002: only genuine countries are recorded as
    such.
    """
    call_command("import_mythology_pilot", input=full_corpus(tmp_path))

    mokele = Entity.objects.get(slug="mokele-mbembe")

    assert mokele.primary_country is None
    assert not Country.objects.filter(name="Congo Basin").exists()
    assert mokele.primary_cultural_area is not None
    assert mokele.primary_cultural_area.name == "Congo Basin"
    # La région parente reste accessible, sans duplication artificielle.
    assert mokele.secondary_cultural_areas.count() == 0


def test_les_pays_et_ethnies_sont_crees(tmp_path: Path) -> None:
    """Countries carry the ISO code of the explicit table.

    Ethnicities get no inferred area.
    """
    call_command("import_mythology_pilot", input=full_corpus(tmp_path))

    nigeria = Country.objects.get(name="Nigeria")
    yoruba = Ethnicity.objects.get(name="Yoruba")

    assert nigeria.iso_code == "NG"
    assert Country.objects.get(name="Ghana").iso_code == "GH"
    # Le corpus donne la région de la figure, pas celle de l'ethnie :
    # l'inférer serait inventer.
    assert yoruba.primary_cultural_area is None


def test_origine_composite_scinde_principal_et_secondaires(tmp_path: Path) -> None:
    """The first real country is primary, the following ones secondary."""
    corpus = write_corpus(
        tmp_path,
        [
            synthetic_divinity(
                origin={
                    "country": "Nigeria / Ghana",
                    "ethnicity": "Yoruba",
                    "cultural_region": "West Africa",
                }
            ),
            synthetic_hero(),
            synthetic_creature(),
        ],
    )

    call_command("import_mythology_pilot", input=corpus)
    oya = Entity.objects.get(slug="oya")

    assert oya.primary_country is not None
    assert oya.primary_country.name == "Nigeria"
    assert [c.name for c in oya.secondary_countries.all()] == ["Ghana"]


def test_aucun_doublon_entre_principal_et_secondaire(tmp_path: Path) -> None:
    """A repeated country does not end up both primary and secondary."""
    corpus = write_corpus(
        tmp_path,
        [
            synthetic_divinity(
                origin={
                    "country": "Nigeria / Nigeria",
                    "ethnicity": "Yoruba",
                    "cultural_region": "West Africa",
                }
            ),
            synthetic_hero(),
            synthetic_creature(),
        ],
    )

    call_command("import_mythology_pilot", input=corpus)
    oya = Entity.objects.get(slug="oya")

    assert oya.primary_country is not None
    assert oya.primary_country.name == "Nigeria"
    assert oya.secondary_countries.count() == 0


def test_ethnie_vague_est_signalee_et_non_creee(tmp_path: Path) -> None:
    """`Multi-ethnic` is reported, not recorded as a real ethnicity."""
    corpus = write_corpus(
        tmp_path,
        [
            synthetic_divinity(
                origin={
                    "country": "Nigeria",
                    "ethnicity": "Multi-ethnic",
                    "cultural_region": "West Africa",
                }
            ),
            synthetic_hero(),
            synthetic_creature(),
        ],
    )

    call_command("import_mythology_pilot", input=corpus)
    oya = Entity.objects.get(slug="oya")

    assert oya.primary_ethnicity is None
    assert not Ethnicity.objects.filter(name="Multi-ethnic").exists()


def test_les_domaines_sont_dedupliques_et_corriges(tmp_path: Path) -> None:
    """The union of domains is applied to the imported record."""
    call_command("import_mythology_pilot", input=full_corpus(tmp_path))

    oya = Entity.objects.get(slug="oya")
    noms = sorted(oya.domains.values_list("name", flat=True))

    assert noms == ["Cemeteries", "Wind"]
    assert not Domain.objects.filter(name="Ceteris").exists()


def test_referentiel_existant_divergent_n_est_pas_reecrit(tmp_path: Path) -> None:
    """A country already present with another ISO code is kept as it is."""
    Country.objects.create(name="Nigeria", slug="nigeria", iso_code="XX")

    call_command("import_mythology_pilot", input=full_corpus(tmp_path))

    assert Country.objects.get(slug="nigeria").iso_code == "XX"
    assert Country.objects.filter(slug="nigeria").count() == 1


# --- Relations en deux passes ------------------------------------------


def test_cible_absente_reste_dans_to_name(tmp_path: Path) -> None:
    """A name cited outside the pilot is kept, unresolved."""
    corpus = write_corpus(
        tmp_path,
        [
            synthetic_divinity(
                relations={
                    "parents": ["Yemaya"],
                    "conjoint": ["Ogun"],
                    "descendants": [],
                }
            ),
            synthetic_hero(),
            synthetic_creature(),
        ],
    )

    call_command("import_mythology_pilot", input=corpus)
    oya = Entity.objects.get(slug="oya")
    liens = {(r.kind, r.to_name, r.to_entity) for r in oya.relations_from.all()}

    assert liens == {
        (RelationKind.PARENT, "Yemaya", None),
        (RelationKind.CONSORT, "Ogun", None),
    }


def test_resolution_en_deux_passes(tmp_path: Path) -> None:
    """A reference towards another pilot record is resolved.

    This demonstrates the second pass: `Anansi` is created after `Oya`, and
    the link from Oya towards it is resolved nonetheless.
    """
    corpus = write_corpus(
        tmp_path,
        [
            synthetic_divinity(
                relations={
                    "parents": ["Anansi"],
                    "conjoint": [],
                    "descendants": [],
                }
            ),
            synthetic_hero(),
            synthetic_creature(),
        ],
    )

    call_command("import_mythology_pilot", input=corpus)
    lien = Entity.objects.get(slug="oya").relations_from.get()

    assert lien.kind == RelationKind.PARENT
    assert lien.to_entity is not None
    assert lien.to_entity.slug == "anansi"
    # Une cible résolue laisse `to_name` vide.
    assert lien.to_name == ""


def test_cible_du_pilote_deja_presente_est_resolue_sans_modification(
    tmp_path: Path,
) -> None:
    """Recreating a source may target an already imported pilot record."""
    corpus = write_corpus(
        tmp_path,
        [
            synthetic_divinity(
                relations={"parents": ["Anansi"], "conjoint": [], "descendants": []}
            ),
            synthetic_hero(),
            synthetic_creature(),
        ],
    )
    call_command("import_mythology_pilot", input=corpus)
    anansi = Entity.objects.get(slug="anansi")
    original_updated_at = anansi.updated_at
    Entity.objects.get(slug="oya").delete()

    call_command("import_mythology_pilot", input=corpus)

    relation = Entity.objects.get(slug="oya").relations_from.get()
    assert relation.to_entity_id == anansi.pk
    assert relation.to_name == ""
    anansi.refresh_from_db()
    assert anansi.updated_at == original_updated_at
    assert anansi.relations_from.count() == 0
    assert Entity.objects.count() == 3


def test_parent_inattendu_d_une_region_racine_est_signale(tmp_path: Path) -> None:
    """An existing parent is preserved but reported when a root is expected."""
    parent = CulturalArea.objects.create(
        name="Synthetic Parent", slug="synthetic-parent", kind="african_region"
    )
    area = CulturalArea.objects.create(
        name="West Africa", slug="west-africa", kind="african_region", parent=parent
    )
    output = StringIO()

    call_command("import_mythology_pilot", input=full_corpus(tmp_path), stdout=output)

    area.refresh_from_db()
    assert area.parent_id == parent.pk
    assert "parent_id=" in output.getvalue()
    assert "differs from corpus value None" in output.getvalue()


def test_aucun_rapprochement_avec_une_fiche_preexistante(tmp_path: Path) -> None:
    """A homonymous record already in the database does not resolve the target.

    `Shango` exists historically; the link from Oya towards that name stays
    unresolved nonetheless, and the historical record is left untouched.
    """
    shango = create_entity(name="Shango", slug="shango")
    corpus = write_corpus(
        tmp_path,
        [
            synthetic_divinity(
                relations={
                    "parents": [],
                    "conjoint": ["Shango"],
                    "descendants": [],
                }
            ),
            synthetic_hero(),
            synthetic_creature(),
        ],
    )

    call_command("import_mythology_pilot", input=corpus)
    lien = Entity.objects.get(slug="oya").relations_from.get()

    assert lien.to_entity is None
    assert lien.to_name == "Shango"
    assert shango.relations_to.count() == 0


def test_descendants_ne_sont_pas_convertis(tmp_path: Path) -> None:
    """`descendants` is not turned into a `child` link."""
    corpus = write_corpus(
        tmp_path,
        [
            synthetic_divinity(
                relations={
                    "parents": [],
                    "conjoint": [],
                    "descendants": ["Some Descendant"],
                }
            ),
            synthetic_hero(),
            synthetic_creature(),
        ],
    )

    call_command("import_mythology_pilot", input=corpus)

    assert EntityRelation.objects.filter(kind=RelationKind.CHILD).count() == 0
    assert Entity.objects.get(slug="oya").relations_from.count() == 0


def test_aucun_lien_inverse_n_est_cree(tmp_path: Path) -> None:
    """Resolving a target does not create a reciprocal relation."""
    corpus = write_corpus(
        tmp_path,
        [
            synthetic_divinity(
                relations={"parents": ["Anansi"], "conjoint": [], "descendants": []}
            ),
            synthetic_hero(),
            synthetic_creature(),
        ],
    )

    call_command("import_mythology_pilot", input=corpus)

    assert EntityRelation.objects.count() == 1
    assert Entity.objects.get(slug="anansi").relations_from.count() == 0


def test_doublon_exact_de_relation_est_dedoublonne(tmp_path: Path) -> None:
    """A name cited twice produces a single link."""
    corpus = write_corpus(
        tmp_path,
        [
            synthetic_divinity(
                relations={
                    "parents": ["Yemaya", "Yemaya"],
                    "conjoint": [],
                    "descendants": [],
                }
            ),
            synthetic_hero(),
            synthetic_creature(),
        ],
    )

    call_command("import_mythology_pilot", input=corpus)

    assert Entity.objects.get(slug="oya").relations_from.count() == 1


# --- Erreurs et entrées invalides --------------------------------------


def test_fichier_absent_donne_une_erreur_lisible(tmp_path: Path) -> None:
    with pytest.raises(CommandError, match="not found"):
        call_command("import_mythology_pilot", input=str(tmp_path / "absent.json"))


def test_json_invalide_donne_une_erreur_lisible(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{ ceci n'est pas du JSON", encoding="utf-8")

    with pytest.raises(CommandError, match="Invalid JSON"):
        call_command("import_mythology_pilot", input=str(path))


def test_racine_non_liste_donne_une_erreur_lisible(tmp_path: Path) -> None:
    path = tmp_path / "object.json"
    path.write_text('{"name": "Oya"}', encoding="utf-8")

    with pytest.raises(CommandError, match="expected a JSON list"):
        call_command("import_mythology_pilot", input=str(path))


def test_selection_incomplete_donne_une_erreur(tmp_path: Path) -> None:
    """Mokele-mbembe is missing: the command refuses to import halfway."""
    corpus = write_corpus(tmp_path, [synthetic_divinity(), synthetic_hero()])

    with pytest.raises(CommandError, match="selection incomplete"):
        call_command("import_mythology_pilot", input=corpus)

    assert Entity.objects.count() == 0


def test_nom_duplique_dans_le_corpus_donne_une_erreur(tmp_path: Path) -> None:
    corpus = write_corpus(
        tmp_path,
        [
            synthetic_divinity(),
            synthetic_divinity(),
            synthetic_hero(),
            synthetic_creature(),
        ],
    )

    with pytest.raises(CommandError, match="ambiguous"):
        call_command("import_mythology_pilot", input=corpus)


def test_type_inattendu_donne_une_erreur(tmp_path: Path) -> None:
    """Oya declared as a `Creature`: the command refuses rather than comply."""
    corpus = write_corpus(
        tmp_path,
        [
            synthetic_divinity(entity_type="Creature"),
            synthetic_hero(),
            synthetic_creature(),
        ],
    )

    with pytest.raises(CommandError, match="expected type"):
        call_command("import_mythology_pilot", input=corpus)


def test_genre_inconnu_donne_une_erreur(tmp_path: Path) -> None:
    """A gender outside the table is not guessed."""
    corpus = write_corpus(
        tmp_path,
        [
            synthetic_divinity(
                identity={
                    "gender": "Plasma",
                    "cultural_role": "Synthetic role",
                    "alignment": "Lawful Neutral",
                }
            ),
            synthetic_hero(),
            synthetic_creature(),
        ],
    )

    with pytest.raises(CommandError, match="unknown gender"):
        call_command("import_mythology_pilot", input=corpus)

    assert Entity.objects.count() == 0


def test_aire_inconnue_donne_une_erreur(tmp_path: Path) -> None:
    """A region outside the prepared areas is not invented."""
    corpus = write_corpus(
        tmp_path,
        [
            synthetic_divinity(
                origin={
                    "country": "Nigeria",
                    "ethnicity": "Yoruba",
                    "cultural_region": "Atlantis",
                }
            ),
            synthetic_hero(),
            synthetic_creature(),
        ],
    )

    with pytest.raises(CommandError, match="refusing to invent"):
        call_command("import_mythology_pilot", input=corpus)


def test_depassement_de_longueur_est_signale_sans_troncature(tmp_path: Path) -> None:
    """A list item that is too long fails validation, without truncation.

    The model limits items to 100 characters. The value is not cut silently:
    the creation fails and the call is rolled back.
    """
    trop_long = "X" * 150
    corpus = write_corpus(
        tmp_path,
        [
            synthetic_divinity(
                story={"description": "Synthetic.", "characteristics": [trop_long]}
            ),
            synthetic_hero(),
            synthetic_creature(),
        ],
    )

    with pytest.raises(CommandError, match="validation failed"):
        call_command("import_mythology_pilot", input=corpus)

    assert Entity.objects.count() == 0


def test_erreur_sur_une_fiche_annule_tout_l_appel(tmp_path: Path) -> None:
    """An error on the third record rolls back the reference data as well.

    This is the transactional guarantee: the call brings nothing at all.
    """
    corpus = write_corpus(
        tmp_path,
        [
            synthetic_divinity(),
            synthetic_hero(),
            synthetic_creature(
                identity={
                    "gender": "Plasma",
                    "cultural_role": "Synthetic role",
                    "alignment": "True Neutral",
                }
            ),
        ],
    )

    with pytest.raises(CommandError):
        call_command("import_mythology_pilot", input=corpus)

    assert Entity.objects.count() == 0
    assert CulturalArea.objects.count() == 0
    assert Country.objects.count() == 0
    assert Domain.objects.count() == 0
    assert Ethnicity.objects.count() == 0


# --- Dry run et relance -------------------------------------------------


def test_dry_run_n_apporte_rien(tmp_path: Path) -> None:
    """The simulation validates and attempts the writes, then rolls everything back."""
    call_command("import_mythology_pilot", input=full_corpus(tmp_path), dry_run=True)

    assert Entity.objects.count() == 0
    assert CulturalArea.objects.count() == 0
    assert Country.objects.count() == 0
    assert DivinityProfile.objects.count() == 0
    assert EntityRelation.objects.count() == 0


def test_relance_ne_duplique_pas(tmp_path: Path) -> None:
    """A second call skips the three records instead of recreating them."""
    corpus = full_corpus(tmp_path)
    call_command("import_mythology_pilot", input=corpus)

    call_command("import_mythology_pilot", input=corpus)

    assert Entity.objects.count() == 3
    assert DivinityProfile.objects.count() == 1
    assert HeroProfile.objects.count() == 1
    assert CreatureProfile.objects.count() == 1


def test_relance_preserve_une_fiche_modifiee(tmp_path: Path) -> None:
    """A change made between two calls is not overwritten."""
    corpus = full_corpus(tmp_path)
    call_command("import_mythology_pilot", input=corpus)

    oya = Entity.objects.get(slug="oya")
    oya.category = "Edited between runs"
    oya.status = EntityStatus.PUBLISHED
    oya.save()
    oya.divinity_profile.cult_offerings = ["Edited offering"]
    oya.divinity_profile.save()

    call_command("import_mythology_pilot", input=corpus)
    oya.refresh_from_db()

    assert oya.category == "Edited between runs"
    assert oya.status == EntityStatus.PUBLISHED
    assert oya.divinity_profile.cult_offerings == ["Edited offering"]


def test_relance_ne_duplique_pas_les_relations(tmp_path: Path) -> None:
    """A skipped record does not see its links recreated."""
    corpus = write_corpus(
        tmp_path,
        [
            synthetic_divinity(
                relations={"parents": ["Yemaya"], "conjoint": [], "descendants": []}
            ),
            synthetic_hero(),
            synthetic_creature(),
        ],
    )
    call_command("import_mythology_pilot", input=corpus)

    call_command("import_mythology_pilot", input=corpus)

    assert EntityRelation.objects.count() == 1


def test_relance_ne_touche_pas_les_collections_d_une_fiche_ignoree(
    tmp_path: Path,
) -> None:
    """The reference data attached to a skipped record stays unchanged."""
    corpus = full_corpus(tmp_path)
    call_command("import_mythology_pilot", input=corpus)

    oya = Entity.objects.get(slug="oya")
    oya.domains.clear()

    call_command("import_mythology_pilot", input=corpus)

    assert oya.domains.count() == 0


def test_conflit_de_slug_donne_une_erreur(tmp_path: Path) -> None:
    """A slug already taken by another figure is an explicit conflict.

    No arbitrary suffixing: the command stops.
    """
    create_entity(name="Autre figure", slug="oya")

    with pytest.raises(CommandError, match="identity conflict"):
        call_command("import_mythology_pilot", input=full_corpus(tmp_path))

    assert Entity.objects.get(slug="oya").name == "Autre figure"


def test_conflit_de_nom_et_type_donne_une_erreur(tmp_path: Path) -> None:
    """Same name and same type under another slug: an explicit conflict."""
    create_entity(name="Oya", slug="oya-autre")

    with pytest.raises(CommandError, match="identity conflict"):
        call_command("import_mythology_pilot", input=full_corpus(tmp_path))


def test_fiche_preexistante_sans_profil_est_preservee(tmp_path: Path) -> None:
    """The historical record without a profile is neither repaired nor deleted."""
    shango = create_entity(name="Shango", slug="shango")

    call_command("import_mythology_pilot", input=full_corpus(tmp_path))
    shango.refresh_from_db()

    assert Entity.objects.filter(pk=shango.pk).exists()
    assert not hasattr(shango, "divinity_profile")
    assert Entity.objects.count() == 4


# --- API de lecture des fiches importées -------------------------------
#
# L'import crée volontairement en `draft`, donc invisible de l'API publique.
# Ces tests publient explicitement les fiches **dans la base de test**, ce qui
# ne change ni le comportement de la commande ni les statuts en développement.


def test_api_de_detail_d_une_fiche_importee(client: Client, tmp_path: Path) -> None:
    """The detail of an imported record does expose its data and its links."""
    corpus = write_corpus(
        tmp_path,
        [
            synthetic_divinity(
                relations={"parents": ["Yemaya"], "conjoint": [], "descendants": []}
            ),
            synthetic_hero(),
            synthetic_creature(),
        ],
    )
    call_command("import_mythology_pilot", input=corpus)
    publish(Entity.objects.get(slug="oya"))

    response = client.get(reverse("entity-detail", kwargs={"slug": "oya"}))

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Oya"
    assert payload["entity_type"] == EntityType.DIVINITY
    assert payload["primary_country"]["iso_code"] == "NG"
    assert payload["primary_ethnicity"]["name"] == "Yoruba"
    assert payload["primary_cultural_area"]["name"] == "West Africa"
    assert sorted(d["name"] for d in payload["domains"]) == ["Cemeteries", "Wind"]
    assert payload["divinity_profile"]["cult_offerings"] == ["Synthetic offering"]
    assert payload["hero_profile"] is None
    assert payload["sources"] == []
    assert payload["relations"][0]["to_name"] == "Yemaya"
    assert payload["relations"][0]["to_entity"] is None


def test_api_de_detail_de_la_creature_importee(client: Client, tmp_path: Path) -> None:
    """The imported creature exposes its precise area and no country."""
    call_command("import_mythology_pilot", input=full_corpus(tmp_path))
    publish(Entity.objects.get(slug="mokele-mbembe"))

    response = client.get(reverse("entity-detail", kwargs={"slug": "mokele-mbembe"}))

    payload = response.json()
    assert payload["primary_country"] is None
    assert payload["primary_cultural_area"]["name"] == "Congo Basin"
    assert payload["creature_profile"]["habitat"] == ["Synthetic habitat"]
    # Le marqueur « None » du corpus n'a pas été inscrit comme objet.
    assert payload["power_objects"] == []


def test_detail_d_une_fiche_importee_coute_sept_requetes(
    client: Client,
    tmp_path: Path,
    django_assert_num_queries: Callable[[int], AbstractContextManager[None]],
) -> None:
    """The detail budget stays at seven queries on a real imported record."""
    call_command("import_mythology_pilot", input=full_corpus(tmp_path))
    publish(Entity.objects.get(slug="oya"))

    with django_assert_num_queries(7):
        response = client.get(reverse("entity-detail", kwargs={"slug": "oya"}))

    assert response.status_code == 200


def test_fiche_importee_se_serialise_sans_requete(
    tmp_path: Path,
    django_assert_num_queries: Callable[[int], AbstractContextManager[None]],
) -> None:
    """The view queryset supplies the serializer, with no residual query.

    It is this test, and not the overall budget, that proves the prefetching.
    """
    corpus = write_corpus(
        tmp_path,
        [
            synthetic_divinity(
                relations={"parents": ["Anansi"], "conjoint": [], "descendants": []}
            ),
            synthetic_hero(),
            synthetic_creature(),
        ],
    )
    call_command("import_mythology_pilot", input=corpus)
    # La cible résolue doit elle aussi être publique pour rester exposée.
    publish(Entity.objects.get(slug="oya"))
    publish(Entity.objects.get(slug="anansi"))

    view = EntityViewSet()
    view.action = "retrieve"
    loaded = view.get_queryset().get(slug="oya")

    with django_assert_num_queries(0):
        payload = EntityDetailSerializer(loaded).data

    assert payload["name"] == "Oya"
    assert payload["relations"][0]["to_entity"]["slug"] == "anansi"
    assert len(payload["domains"]) == 2


# --- Option `--all` : corpus complet ------------------------------------
#
# Les cas ci-dessous reprennent les constructeurs du pilote plutôt que de
# recopier des fiches : seules les différences réellement rencontrées dans
# les 44 figures du corpus V2 sont représentées — aires culturelles au-delà
# des quatre régions du pilote, pays sans code ISO retenu, cibles de relation
# hors fichier, et volume suffisant pour que le bilan reste lisible.


def extra_divinity(name: str, **overrides: Any) -> dict[str, Any]:
    return synthetic_divinity(name=name, **overrides)


def corpus_with_extras(tmp_path: Path, *extras: dict[str, Any]) -> str:
    return write_corpus(
        tmp_path,
        [synthetic_divinity(), synthetic_hero(), synthetic_creature(), *extras],
    )


def test_all_importe_toutes_les_figures_du_fichier(tmp_path: Path) -> None:
    corpus = corpus_with_extras(
        tmp_path, extra_divinity("Olokun"), extra_divinity("Nyame")
    )

    call_command("import_mythology_pilot", input=corpus, all=True)

    assert Entity.objects.count() == 5
    assert set(Entity.objects.values_list("slug", flat=True)) == {
        "oya",
        "anansi",
        "mokele-mbembe",
        "olokun",
        "nyame",
    }
    # Garanties du pilote inchangées : brouillon, sans propriétaire ni revue.
    for entity in Entity.objects.all():
        assert entity.status == EntityStatus.DRAFT
        assert entity.created_by_id is None
        assert entity.reviewed_by_id is None
        assert entity.submitted_at is None
        assert entity.deleted_at is None
    # Un profil, et exactement celui du type.
    assert DivinityProfile.objects.count() == 3
    assert HeroProfile.objects.count() == 1
    assert CreatureProfile.objects.count() == 1


def test_sans_all_le_pilote_reste_inchange(tmp_path: Path) -> None:
    corpus = corpus_with_extras(
        tmp_path, extra_divinity("Olokun"), extra_divinity("Nyame")
    )

    call_command("import_mythology_pilot", input=corpus)

    assert set(Entity.objects.values_list("slug", flat=True)) == {
        "oya",
        "anansi",
        "mokele-mbembe",
    }


def test_all_resout_les_relations_entre_figures_hors_pilote(tmp_path: Path) -> None:
    corpus = corpus_with_extras(
        tmp_path,
        extra_divinity(
            "Olokun",
            relations={"parents": ["Nyame"], "conjoint": ["Oya"], "descendants": []},
        ),
        extra_divinity("Nyame"),
    )

    call_command("import_mythology_pilot", input=corpus, all=True)

    olokun = Entity.objects.get(slug="olokun")
    parent = EntityRelation.objects.get(from_entity=olokun, kind=RelationKind.PARENT)
    consort = EntityRelation.objects.get(from_entity=olokun, kind=RelationKind.CONSORT)
    assert parent.to_entity is not None
    assert parent.to_entity.slug == "nyame"
    assert parent.to_name == ""
    assert consort.to_entity is not None
    assert consort.to_entity.slug == "oya"


def test_all_preserve_une_cible_absente_du_fichier_sous_to_name(
    tmp_path: Path,
) -> None:
    corpus = corpus_with_extras(
        tmp_path,
        extra_divinity(
            "Nyame",
            relations={"parents": ["Olokun"], "conjoint": [], "descendants": []},
        ),
    )
    output = StringIO()

    call_command("import_mythology_pilot", input=corpus, all=True, stdout=output)

    relation = EntityRelation.objects.get(from_entity__slug="nyame")
    assert relation.to_entity is None
    assert relation.to_name == "Olokun"
    assert "unresolved" in output.getvalue()
    # Aucune fiche fantôme n'a été créée pour accueillir la cible.
    assert not Entity.objects.filter(slug="olokun").exists()


def test_all_couvre_les_aires_culturelles_au_dela_des_regions_du_pilote(
    tmp_path: Path,
) -> None:
    corpus = corpus_with_extras(
        tmp_path,
        extra_divinity(
            "Nyame",
            origin={
                "country": "Egypt",
                "ethnicity": "Akan",
                "pantheon": "Synthetic pantheon",
                "cultural_region": "North Africa",
            },
        ),
        extra_divinity(
            "Olokun",
            origin={
                "country": "Nigeria",
                "ethnicity": "Yoruba",
                "pantheon": "Synthetic pantheon",
                "cultural_region": "Pan-African",
            },
        ),
    )

    call_command("import_mythology_pilot", input=corpus, all=True)

    north = CulturalArea.objects.get(name="North Africa")
    assert north.kind == CulturalAreaKind.AFRICAN_REGION
    # `Pan-African` et `Cross-Regional` sont des portées, pas des régions.
    for name in ("Pan-African", "Cross-Regional"):
        area = CulturalArea.objects.get(name=name)
        assert area.kind == CulturalAreaKind.TRANSREGIONAL
    basin = CulturalArea.objects.get(name="Congo Basin")
    assert basin.parent is not None
    assert basin.parent.name == "Central Africa"
    assert Entity.objects.get(slug="nyame").primary_cultural_area == north


def test_all_applique_les_codes_iso_connus_et_signale_les_autres(
    tmp_path: Path,
) -> None:
    corpus = corpus_with_extras(
        tmp_path,
        extra_divinity(
            "Nyame",
            origin={
                "country": "Congo",
                "ethnicity": "Akan",
                "pantheon": "Synthetic pantheon",
                "cultural_region": "Central Africa",
            },
        ),
    )
    output = StringIO()

    call_command("import_mythology_pilot", input=corpus, all=True, stdout=output)

    assert Country.objects.get(name="Nigeria").iso_code == "NG"
    assert Country.objects.get(name="Congo").iso_code == ""
    assert "Congo" in output.getvalue()


def test_all_refuse_une_figure_sans_nom(tmp_path: Path) -> None:
    corpus = corpus_with_extras(tmp_path, extra_divinity("   "))

    with pytest.raises(CommandError, match="missing or empty"):
        call_command("import_mythology_pilot", input=corpus, all=True)

    assert Entity.objects.count() == 0


def test_all_refuse_un_nom_duplique_dans_le_fichier(tmp_path: Path) -> None:
    corpus = corpus_with_extras(tmp_path, extra_divinity("Oya"))

    with pytest.raises(CommandError, match="appears more than once"):
        call_command("import_mythology_pilot", input=corpus, all=True)

    assert Entity.objects.count() == 0


def test_all_refuse_un_type_inconnu(tmp_path: Path) -> None:
    corpus = corpus_with_extras(
        tmp_path, extra_divinity("Nyame", entity_type="Trickster")
    )

    with pytest.raises(CommandError, match="unknown entity_type"):
        call_command("import_mythology_pilot", input=corpus, all=True)

    assert Entity.objects.count() == 0


def test_all_refuse_un_fichier_sans_figure(tmp_path: Path) -> None:
    corpus = write_corpus(tmp_path, [])

    with pytest.raises(CommandError, match="selection empty"):
        call_command("import_mythology_pilot", input=corpus, all=True)


def test_all_annule_tous_les_apports_sur_une_erreur_tardive(tmp_path: Path) -> None:
    corpus = corpus_with_extras(
        tmp_path,
        extra_divinity(
            "Nyame",
            identity={
                "gender": "Plasma",
                "cultural_role": "Synthetic role",
                "alignment": "Lawful Neutral",
            },
        ),
    )

    with pytest.raises(CommandError, match="unknown gender"):
        call_command("import_mythology_pilot", input=corpus, all=True)

    assert Entity.objects.count() == 0
    assert EntityRelation.objects.count() == 0
    assert Country.objects.count() == 0
    assert Ethnicity.objects.count() == 0
    assert Domain.objects.count() == 0
    assert CulturalArea.objects.count() == 0
    assert DivinityProfile.objects.count() == 0


def test_all_en_dry_run_ne_persiste_rien(tmp_path: Path) -> None:
    corpus = corpus_with_extras(
        tmp_path, extra_divinity("Olokun"), extra_divinity("Nyame")
    )
    output = StringIO()

    call_command(
        "import_mythology_pilot", input=corpus, all=True, dry_run=True, stdout=output
    )

    assert Entity.objects.count() == 0
    assert CulturalArea.objects.count() == 0
    assert Domain.objects.count() == 0
    report = output.getvalue()
    assert "DRY RUN (rolled back)" in report
    # Le bilan reste celui d'un import complet, avec ses décomptes réels.
    assert "Entities created: 5" in report


def test_all_relance_sans_doublon_et_preserve_les_fiches_existantes(
    tmp_path: Path, django_user_model: Any
) -> None:
    corpus = corpus_with_extras(tmp_path, extra_divinity("Nyame"))
    call_command("import_mythology_pilot", input=corpus, all=True)

    owner = django_user_model.objects.create_user(username="editeur")
    oya = Entity.objects.get(slug="oya")
    oya.status = EntityStatus.PUBLISHED
    oya.created_by = owner
    oya.review_notes = "Revue éditoriale à conserver."
    oya.cultural_role = "Role corrige en revue."
    oya.save()
    oya.domains.clear()
    before = {
        entity.pk: (entity.status, entity.created_by_id, entity.updated_at)
        for entity in Entity.objects.all()
    }
    relations_before = EntityRelation.objects.count()
    output = StringIO()

    call_command("import_mythology_pilot", input=corpus, all=True, stdout=output)

    assert Entity.objects.count() == len(before)
    assert EntityRelation.objects.count() == relations_before
    after = Entity.objects.get(slug="oya")
    assert after.status == EntityStatus.PUBLISHED
    assert after.created_by_id == owner.pk
    assert after.review_notes == "Revue éditoriale à conserver."
    assert after.cultural_role == "Role corrige en revue."
    # Ni restauration des domaines retirés, ni réécriture d'un champ.
    assert after.domains.count() == 0
    for entity in Entity.objects.all():
        assert before[entity.pk] == (
            entity.status,
            entity.created_by_id,
            entity.updated_at,
        )
    report = output.getvalue()
    assert "Entities created: 0" in report
    assert "already exists" in report


def test_all_ne_reutilise_pas_une_fiche_supprimee_comme_cible(tmp_path: Path) -> None:
    deleted = create_entity(
        name="Nyame",
        slug="nyame",
        deleted_at=timezone.now(),
        status=EntityStatus.DRAFT,
    )
    corpus = corpus_with_extras(
        tmp_path,
        extra_divinity(
            "Olokun",
            relations={"parents": ["Nyame"], "conjoint": [], "descendants": []},
        ),
        extra_divinity("Nyame"),
    )
    output = StringIO()

    call_command("import_mythology_pilot", input=corpus, all=True, stdout=output)

    relation = EntityRelation.objects.get(from_entity__slug="olokun")
    assert relation.to_entity is None
    assert relation.to_name == "Nyame"
    reloaded = Entity.objects.get(pk=deleted.pk)
    assert reloaded.deleted_at is not None
    assert Entity.objects.filter(slug="nyame").count() == 1
    assert "logically deleted" in output.getvalue()


def test_all_resume_les_descendants_en_une_seule_note(tmp_path: Path) -> None:
    corpus = corpus_with_extras(
        tmp_path,
        extra_divinity(
            "Nyame",
            relations={"parents": [], "conjoint": [], "descendants": ["Olokun"]},
        ),
        extra_divinity(
            "Olokun",
            relations={"parents": [], "conjoint": [], "descendants": ["Nyame", "Oya"]},
        ),
    )
    output = StringIO()

    call_command("import_mythology_pilot", input=corpus, all=True, stdout=output)

    lines = [
        line
        for line in output.getvalue().splitlines()
        if "relations.descendants:" in line
    ]
    assert len(lines) == 1
    assert "3 cited names across 2 entities were NOT imported" in lines[0]
    # Aucun lien n'a été créé dans un sens non garanti par la source.
    assert EntityRelation.objects.count() == 0


def test_all_affiche_un_bilan_lisible(tmp_path: Path) -> None:
    create_entity(name="Nyame", slug="nyame")
    corpus = corpus_with_extras(
        tmp_path,
        extra_divinity(
            "Olokun",
            relations={
                "parents": ["Oya"],
                "conjoint": ["Mami Wata"],
                "descendants": [],
            },
        ),
        extra_divinity("Nyame"),
    )
    output = StringIO()

    call_command("import_mythology_pilot", input=corpus, all=True, stdout=output)
    report = output.getvalue()

    assert "Full corpus import summary" in report
    assert "Selection       : --all" in report
    assert "Figures read    : 5" in report
    assert "Figures selected: 5" in report
    assert "Entities created: 4" in report
    assert "Relations       : 2 (1 resolved, 1 cited by name)" in report
    # Les exclusions restent annoncées, y compris en import complet.
    assert "rendering" in report
    assert "origin.pantheon" in report
