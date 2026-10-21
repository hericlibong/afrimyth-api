"""Tests de la commande `import_mythology_pilot`.

**Autonomes** : aucun test ne lit le corpus réel. Chaque cas écrit son propre
JSON synthétique dans un répertoire temporaire, de forme équivalente au
corpus V2 mais à contenu inventé. Les tests restent donc exécutables sans le
dossier `_audit`.

Les trois noms de la sélection — `Oya`, `Anansi`, `Mokele-mbembe` — sont en
revanche repris tels quels, puisque c'est précisément la sélection que la
commande applique.
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
    """Divinité synthétique, de forme identique au corpus V2."""
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
    """Héros synthétique."""
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
    """Créature synthétique, dont l'origine est une aire et non un pays."""
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
    """Écrit un corpus synthétique et retourne son chemin."""
    path = tmp_path / "synthetic_corpus.json"
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return str(path)


def full_corpus(tmp_path: Path, **kwargs: Any) -> str:
    """Corpus synthétique complet : les trois fiches de la sélection."""
    return write_corpus(
        tmp_path,
        [synthetic_divinity(**kwargs), synthetic_hero(), synthetic_creature()],
    )


# --- Fonctions de transformation ---------------------------------------


def test_clean_list_ecarte_les_marqueurs_d_absence() -> None:
    """`["None"]` est une absence, pas un objet de pouvoir."""
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
    """Une chaîne au lieu d'une liste est signalée, pas devinée."""
    notes: list[str] = []

    assert clean_list("Wind", label="x", notes=notes) == []
    assert any("unexpected shape" in note for note in notes)


def test_clean_list_conserve_l_unicode() -> None:
    """Les caractères non ASCII traversent l'import sans altération."""
    notes: list[str] = []

    assert clean_list(["Ṣàngó", "Mmuo"], label="x", notes=notes) == ["Ṣàngó", "Mmuo"]


def test_clean_text_signale_une_valeur_nulle() -> None:
    notes: list[str] = []

    assert clean_text(None, label="x", notes=notes) == ""
    assert any("null value" in note for note in notes)


def test_domaines_reconcilies_avec_correction() -> None:
    """Union dédupliquée, `Ceteris` corrigé, synonymes conservés."""
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
    """L'absence du bloc `divinity` n'est pas signalée comme une anomalie."""
    notes: list[str] = []
    item = {"attributes": {"domains": ["Stories"]}, "type_specific": {"hero": {}}}

    assert reconcile_domains(item, name="Synthetic", notes=notes) == ["Stories"]
    assert not any("divinity.domains" in note for note in notes)


# --- Import des trois types --------------------------------------------


def test_import_des_trois_types(tmp_path: Path) -> None:
    """Les trois fiches sont créées, chacune avec son seul profil."""
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
    """Textes et listes du tronc commun arrivent intacts en base."""
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
    """Chaque profil reçoit les champs de son bloc `type_specific`."""
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
    """Aucun statut public, aucun propriétaire, aucune marque de revue."""
    call_command("import_mythology_pilot", input=full_corpus(tmp_path))

    for entity in Entity.objects.all():
        assert entity.status == EntityStatus.DRAFT
        assert entity.created_by is None
        assert entity.reviewed_by is None
        assert entity.reviewed_at is None
        assert entity.deleted_at is None
        assert entity.sources.count() == 0


def test_les_donnees_de_rendu_ne_sont_pas_importees(tmp_path: Path) -> None:
    """`rendering`, le prompt d'image et `imageUrl` restent hors du modèle."""
    call_command("import_mythology_pilot", input=full_corpus(tmp_path))

    oya = Entity.objects.get(slug="oya")
    stored = " ".join(
        [oya.story_description, oya.manifestations, oya.category, *oya.symbols]
    )

    assert "prompt" not in stored.lower()
    assert "ignored" not in stored.lower()


# --- Référentiels -------------------------------------------------------


def test_les_aires_de_reference_sont_preparees(tmp_path: Path) -> None:
    """Les quatre régions, la diaspora et la sous-région sont créées."""
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
    """`Congo Basin` est une région africaine dont le parent est Central Africa."""
    call_command("import_mythology_pilot", input=full_corpus(tmp_path))

    congo = CulturalArea.objects.get(name="Congo Basin")

    assert congo.kind == CulturalAreaKind.AFRICAN_REGION
    assert congo.parent is not None
    assert congo.parent.name == "Central Africa"


def test_une_aire_geographique_ne_devient_pas_un_pays(tmp_path: Path) -> None:
    """`Congo Basin` n'entre pas dans `Country` et laisse le pays nul.

    C'est la décision 2 de l'ADR 0002 : seuls de véritables pays sont
    enregistrés comme tels.
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
    """Pays avec code ISO de la table explicite ; ethnies sans aire déduite."""
    call_command("import_mythology_pilot", input=full_corpus(tmp_path))

    nigeria = Country.objects.get(name="Nigeria")
    yoruba = Ethnicity.objects.get(name="Yoruba")

    assert nigeria.iso_code == "NG"
    assert Country.objects.get(name="Ghana").iso_code == "GH"
    # Le corpus donne la région de la figure, pas celle de l'ethnie :
    # l'inférer serait inventer.
    assert yoruba.primary_cultural_area is None


def test_origine_composite_scinde_principal_et_secondaires(tmp_path: Path) -> None:
    """Le premier pays réel est principal, les suivants secondaires."""
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
    """Un pays répété ne se retrouve pas à la fois principal et secondaire."""
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
    """`Multi-ethnic` est signalée, pas inscrite comme ethnie réelle."""
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
    """L'union des domaines est appliquée à la fiche importée."""
    call_command("import_mythology_pilot", input=full_corpus(tmp_path))

    oya = Entity.objects.get(slug="oya")
    noms = sorted(oya.domains.values_list("name", flat=True))

    assert noms == ["Cemeteries", "Wind"]
    assert not Domain.objects.filter(name="Ceteris").exists()


def test_referentiel_existant_divergent_n_est_pas_reecrit(tmp_path: Path) -> None:
    """Un pays déjà présent avec un autre code ISO est conservé tel quel."""
    Country.objects.create(name="Nigeria", slug="nigeria", iso_code="XX")

    call_command("import_mythology_pilot", input=full_corpus(tmp_path))

    assert Country.objects.get(slug="nigeria").iso_code == "XX"
    assert Country.objects.filter(slug="nigeria").count() == 1


# --- Relations en deux passes ------------------------------------------


def test_cible_absente_reste_dans_to_name(tmp_path: Path) -> None:
    """Un nom cité hors du pilote est conservé, non résolu."""
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
    """Une référence vers une autre fiche du pilote est résolue.

    C'est la démonstration de la seconde passe : `Anansi` est créé après
    `Oya`, et le lien d'Oya vers lui n'en est pas moins résolu.
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
    """Recréer une source peut viser une cible du pilote déjà importée."""
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
    """Un parent existant est préservé mais signalé si une racine est attendue."""
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
    """Une fiche homonyme déjà en base ne résout pas la cible.

    `Shango` existe historiquement ; le lien d'Oya vers « Shango » reste
    pourtant non résolu, et la fiche historique n'est pas touchée.
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
    """`descendants` n'est pas transformé en lien `child`."""
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
    """Résoudre une cible ne crée pas de relation réciproque."""
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
    """Un nom cité deux fois ne produit qu'un seul lien."""
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
    """Il manque Mokele-mbembe : la commande refuse d'importer à moitié."""
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
    """Oya déclarée `Creature` : la commande refuse plutôt que d'obéir."""
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
    """Un genre hors table n'est pas deviné."""
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
    """Une région hors des aires préparées n'est pas inventée."""
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
    """Un élément de liste trop long fait échouer la validation, sans tronquer.

    Le modèle limite les éléments à 100 caractères. La valeur n'est pas
    coupée en silence : la création échoue et l'appel est annulé.
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
    """Une erreur sur la troisième fiche annule aussi les référentiels.

    C'est la garantie transactionnelle : l'appel n'apporte rien du tout.
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
    """La simulation valide et tente les écritures, puis annule tout."""
    call_command("import_mythology_pilot", input=full_corpus(tmp_path), dry_run=True)

    assert Entity.objects.count() == 0
    assert CulturalArea.objects.count() == 0
    assert Country.objects.count() == 0
    assert DivinityProfile.objects.count() == 0
    assert EntityRelation.objects.count() == 0


def test_relance_ne_duplique_pas(tmp_path: Path) -> None:
    """Un second appel ignore les trois fiches au lieu de les recréer."""
    corpus = full_corpus(tmp_path)
    call_command("import_mythology_pilot", input=corpus)

    call_command("import_mythology_pilot", input=corpus)

    assert Entity.objects.count() == 3
    assert DivinityProfile.objects.count() == 1
    assert HeroProfile.objects.count() == 1
    assert CreatureProfile.objects.count() == 1


def test_relance_preserve_une_fiche_modifiee(tmp_path: Path) -> None:
    """Une modification entre deux appels n'est pas écrasée."""
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
    """Une fiche ignorée ne voit pas ses liens recréés."""
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
    """Les référentiels rattachés à une fiche ignorée restent inchangés."""
    corpus = full_corpus(tmp_path)
    call_command("import_mythology_pilot", input=corpus)

    oya = Entity.objects.get(slug="oya")
    oya.domains.clear()

    call_command("import_mythology_pilot", input=corpus)

    assert oya.domains.count() == 0


def test_conflit_de_slug_donne_une_erreur(tmp_path: Path) -> None:
    """Un slug déjà pris par une autre figure est un conflit explicite.

    Aucun suffixage arbitraire : la commande s'arrête.
    """
    create_entity(name="Autre figure", slug="oya")

    with pytest.raises(CommandError, match="identity conflict"):
        call_command("import_mythology_pilot", input=full_corpus(tmp_path))

    assert Entity.objects.get(slug="oya").name == "Autre figure"


def test_conflit_de_nom_et_type_donne_une_erreur(tmp_path: Path) -> None:
    """Même nom et même type sous un autre slug : conflit explicite."""
    create_entity(name="Oya", slug="oya-autre")

    with pytest.raises(CommandError, match="identity conflict"):
        call_command("import_mythology_pilot", input=full_corpus(tmp_path))


def test_fiche_preexistante_sans_profil_est_preservee(tmp_path: Path) -> None:
    """La fiche historique sans profil n'est ni réparée ni supprimée."""
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
    """Le détail d'une fiche importée expose bien ses données et ses liens."""
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
    """La créature importée expose son aire précise et aucun pays."""
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
    """Le budget du détail reste de sept requêtes sur une fiche réelle importée."""
    call_command("import_mythology_pilot", input=full_corpus(tmp_path))
    publish(Entity.objects.get(slug="oya"))

    with django_assert_num_queries(7):
        response = client.get(reverse("entity-detail", kwargs={"slug": "oya"}))

    assert response.status_code == 200


def test_fiche_importee_se_serialise_sans_requete(
    tmp_path: Path,
    django_assert_num_queries: Callable[[int], AbstractContextManager[None]],
) -> None:
    """Le queryset de la vue fournit tout au serializer, sans requête résiduelle.

    C'est ce test, et non le budget global, qui prouve le préchargement.
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
