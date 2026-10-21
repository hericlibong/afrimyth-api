"""Import pilote de trois figures réelles du corpus V2.

Pilote volontairement restreint à trois fiches — une par type — afin de
confronter le modèle à des données réelles avant l'import complet, qui relève
de la phase 5. Les transformations sont écrites explicitement : il n'y a pas
de moteur d'import générique, et chaque correspondance est lisible ici.

Le corpus source reste **externe** au dépôt : son chemin est fourni par
`--input`, aucun chemin absolu n'est codé en dur, et rien n'en est recopié.
"""

from __future__ import annotations

import json
from argparse import ArgumentParser
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from mythology.models import (
    Country,
    CulturalArea,
    CulturalAreaKind,
    Domain,
    Entity,
    EntityRelation,
    EntityType,
    Ethnicity,
    Gender,
    RelationKind,
)
from mythology.services import create_entity_with_profile

# --- Sélection du pilote -------------------------------------------------

#: Les trois seules fiches importées, avec le type attendu. Toute divergence
#: entre le type du JSON et celui attendu est une erreur : le pilote ne doit
#: pas importer silencieusement autre chose que ce qui a été validé.
PILOT_SELECTION: dict[str, str] = {
    "Oya": EntityType.DIVINITY,
    "Anansi": EntityType.HERO,
    "Mokele-mbembe": EntityType.CREATURE,
}

# --- Tables de correspondance -------------------------------------------

ENTITY_TYPES: dict[str, str] = {
    "Divinity": EntityType.DIVINITY,
    "Hero": EntityType.HERO,
    "Creature": EntityType.CREATURE,
}

GENDERS: dict[str, str] = {
    "Male": Gender.MALE,
    "Female": Gender.FEMALE,
    "Neutral": Gender.NEUTRAL,
    "Androgynous": Gender.ANDROGYNOUS,
    "Fluid": Gender.FLUID,
}

#: Codes ISO 3166-1 alpha-2 des seuls pays rencontrés par le pilote. Table
#: explicite plutôt que dépendance de géocodage.
COUNTRY_ISO_CODES: dict[str, str] = {
    "Nigeria": "NG",
    "Ghana": "GH",
}

#: Les quatre grandes régions continentales, préparées même si le pilote n'en
#: utilise pas toutes, plus la diaspora. `Pan-African` n'est pas créé : aucune
#: des trois fiches ne le réclame.
BASE_CULTURAL_AREAS: tuple[tuple[str, str, str | None], ...] = (
    ("West Africa", CulturalAreaKind.AFRICAN_REGION, None),
    ("Central Africa", CulturalAreaKind.AFRICAN_REGION, None),
    ("East Africa", CulturalAreaKind.AFRICAN_REGION, None),
    ("Southern Africa", CulturalAreaKind.AFRICAN_REGION, None),
    ("Diaspora", CulturalAreaKind.DIASPORIC, None),
    # Sous-région précise, rattachée à sa région par `parent`.
    ("Congo Basin", CulturalAreaKind.AFRICAN_REGION, "Central Africa"),
)

#: Valeurs d'`origin.country` qui ne désignent pas un pays. Elles relèvent de
#: `CulturalArea`, conformément à la décision 2 de l'ADR 0002, et ne doivent
#: jamais produire une ligne dans `Country`.
NON_COUNTRY_ORIGINS: dict[str, str] = {
    "Congo Basin": "Congo Basin",
    "Pan-African": "Pan-African",
    "Diaspora": "Diaspora",
}

#: Corrections orthographiques validées en phase 0. Seules les erreurs
#: certaines sont corrigées : les synonymes discutables — `Change` et
#: `Transformation` — sont conservés côte à côte et signalés.
DOMAIN_CORRECTIONS: dict[str, str] = {"Ceteris": "Cemeteries"}

#: Marqueurs textuels d'absence rencontrés dans les listes du corpus. Les
#: conserver inscrirait un faux fait — « None » n'est pas un objet de pouvoir.
LIST_SENTINELS: frozenset[str] = frozenset({"none", "n/a", "na", "unknown", "-", ""})

#: Valeurs d'ethnie trop vagues pour devenir une ligne de référentiel.
VAGUE_ETHNICITIES: frozenset[str] = frozenset(
    {"multi-ethnic", "southern nations", "unknown"}
)

#: Blocs du corpus volontairement non importés, avec leur raison.
EXCLUDED_SOURCE_KEYS: dict[str, str] = {
    "rendering": (
        "Rendering data (canonical prompt, variants, images, style matrix) is "
        "out of V1 scope — ADR 0002, section 8."
    ),
    "appearance.image_generation_prompt": (
        "Image prompt is rendering data, not a mythological fact — ADR 0002, "
        "section 8."
    ),
    "appearance.imageUrl": (
        "Image URL belongs to the rendering module, not to the entity model."
    ),
    "origin.pantheon": (
        "Pantheon is excluded from the V1 target model: the observed values mix "
        "religious traditions, folklore, regions and narrative categories."
    ),
}


def clean_list(values: Any, *, label: str, notes: list[str]) -> list[str]:
    """Normalise une liste de chaînes du corpus.

    Retire les espaces de bord, écarte les marqueurs d'absence et déduplique
    en conservant l'ordre d'apparition. Chaque retrait est signalé : un
    `["None"]` doit se lire comme une absence, pas devenir un fait.
    """
    if values is None:
        notes.append(f"{label}: null value replaced by an empty list.")
        return []
    if not isinstance(values, list):
        notes.append(
            f"{label}: unexpected shape {type(values).__name__}, expected a list; "
            "imported as empty."
        )
        return []

    cleaned: list[str] = []
    for value in values:
        if not isinstance(value, str):
            notes.append(
                f"{label}: non-string item {value!r} skipped (unexpected shape)."
            )
            continue
        stripped = value.strip()
        if stripped.lower() in LIST_SENTINELS:
            notes.append(
                f"{label}: placeholder {value!r} skipped — recorded as absence, "
                "not as a fact."
            )
            continue
        if stripped in cleaned:
            notes.append(f"{label}: duplicate {stripped!r} removed.")
            continue
        cleaned.append(stripped)
    return cleaned


def clean_text(value: Any, *, label: str, notes: list[str]) -> str:
    """Normalise un champ textuel ; une valeur nulle devient une chaîne vide."""
    if value is None:
        notes.append(f"{label}: null value replaced by an empty string.")
        return ""
    if not isinstance(value, str):
        notes.append(
            f"{label}: unexpected shape {type(value).__name__}; imported as empty."
        )
        return ""
    return value.strip()


def check_array_item_lengths(
    values: Sequence[str], *, label: str, notes: list[str], limit: int = 100
) -> None:
    """Signale tout élément dépassant la longueur du champ, sans tronquer.

    Tronquer altérerait silencieusement une donnée réelle ; mieux vaut un
    signalement et, si le cas se présente, une migration ciblée.
    """
    for value in values:
        if len(value) > limit:
            notes.append(
                f"{label}: item of {len(value)} characters exceeds the {limit}-"
                f"character limit and was NOT truncated: {value[:40]!r}…"
            )


def reconcile_domains(
    item: Mapping[str, Any], *, name: str, notes: list[str]
) -> list[str]:
    """Union dédupliquée des domaines communs et des domaines de divinité.

    Décision 4 de l'ADR 0002 : `Entity.domains` est l'emplacement unique.
    L'union évite la perte constatée à l'audit, où aucun des deux
    emplacements n'était un sur-ensemble de l'autre.
    """
    common = clean_list(
        item.get("attributes", {}).get("domains"),
        label=f"{name}.attributes.domains",
        notes=notes,
    )

    # Le bloc `divinity` n'existe que pour les divinités : son absence est
    # normale pour un héros ou une créature et ne doit pas être signalée.
    divinity_block = (item.get("type_specific") or {}).get("divinity") or {}
    specific: list[str] = []
    if "domains" in divinity_block:
        specific = clean_list(
            divinity_block["domains"],
            label=f"{name}.type_specific.divinity.domains",
            notes=notes,
        )

    merged: list[str] = []
    for value in [*common, *specific]:
        corrected = DOMAIN_CORRECTIONS.get(value, value)
        if corrected != value:
            notes.append(
                f"{name}: domain {value!r} corrected to {corrected!r} "
                "(validated spelling fix)."
            )
        if corrected not in merged:
            merged.append(corrected)

    only_specific = [
        value for value in merged if value in specific and value not in common
    ]
    if only_specific:
        notes.append(
            f"{name}: domains present only in type_specific and kept by the "
            f"union: {', '.join(only_specific)}. Debatable synonyms are NOT "
            "merged and need editorial review."
        )
    return merged


class Command(BaseCommand):
    """Importe les trois figures du pilote depuis le corpus V2 externe."""

    help = (
        "Import the three pilot figures (Oya, Anansi, Mokele-mbembe) from an "
        "external V2 corpus JSON file. Re-running the command never "
        "duplicates nor overwrites existing entities."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--input",
            required=True,
            help="Path to the external mythology_data.json corpus file.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Validate and attempt every write inside a transaction that is "
                "rolled back at the end. Nothing is persisted."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        corpus_path = Path(options["input"])
        dry_run: bool = options["dry_run"]

        corpus = self._load_corpus(corpus_path)
        selected = self._select_pilot(corpus)

        notes: list[str] = []
        created: list[Entity] = []
        skipped: list[str] = []
        relations_created: list[str] = []

        for key, reason in EXCLUDED_SOURCE_KEYS.items():
            notes.append(f"Not imported — {key}: {reason}")

        # Une seule transaction pour l'ensemble de l'appel : référentiels,
        # fiches, collections et relations. Une erreur bloquante annule donc
        # tous les apports de cet appel, référentiels compris.
        with transaction.atomic():
            areas = self._ensure_base_cultural_areas(notes)
            pilot_by_name: dict[str, Entity] = {}

            for name in PILOT_SELECTION:
                item = selected[name]
                existing = self._find_existing(item, name=name)
                if existing is not None:
                    pilot_by_name[name] = existing
                    skipped.append(f"{existing.name} ({existing.entity_type})")
                    notes.append(
                        f"{name}: an entity with the same identity already "
                        "exists; skipped without touching its fields, profile "
                        "or collections."
                    )
                    continue
                entity = self._import_entity(item, name=name, areas=areas, notes=notes)
                created.append(entity)
                pilot_by_name[name] = entity

            # Seconde passe : les relations, une fois toutes les fiches du
            # pilote créées, afin que les références internes soient
            # résolvables.
            for entity in created:
                item = selected[entity.name]
                relations_created.extend(
                    self._import_relations(
                        entity,
                        item,
                        resolvable=pilot_by_name,
                        notes=notes,
                    )
                )

            if dry_run:
                transaction.set_rollback(True)

        self._report(
            corpus_path=corpus_path,
            dry_run=dry_run,
            created=created,
            skipped=skipped,
            relations_created=relations_created,
            notes=notes,
        )

    # --- Chargement et sélection ----------------------------------------

    def _load_corpus(self, path: Path) -> list[Mapping[str, Any]]:
        """Charge le corpus, avec des erreurs lisibles."""
        if not path.is_file():
            raise CommandError(f"Corpus file not found: {path}")
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as error:
            raise CommandError(f"Cannot read corpus file {path}: {error}") from error
        try:
            corpus = json.loads(raw)
        except json.JSONDecodeError as error:
            raise CommandError(f"Invalid JSON in {path}: {error}") from error
        if not isinstance(corpus, list):
            raise CommandError(
                f"Invalid corpus in {path}: expected a JSON list of entities, "
                f"got {type(corpus).__name__}."
            )
        return corpus

    def _select_pilot(
        self, corpus: Sequence[Mapping[str, Any]]
    ) -> dict[str, Mapping[str, Any]]:
        """Isole les trois fiches du pilote et vérifie leur unicité et leur type."""
        selected: dict[str, Mapping[str, Any]] = {}
        for name, expected_type in PILOT_SELECTION.items():
            matches = [item for item in corpus if item.get("name") == name]
            if not matches:
                raise CommandError(f"Pilot selection incomplete: {name!r} not found.")
            if len(matches) > 1:
                raise CommandError(
                    f"Pilot selection ambiguous: {name!r} appears "
                    f"{len(matches)} times."
                )
            item = matches[0]
            raw_type = item.get("entity_type")
            mapped = ENTITY_TYPES.get(str(raw_type))
            if mapped is None:
                raise CommandError(
                    f"{name!r}: unknown entity_type {raw_type!r} in corpus."
                )
            if mapped != expected_type:
                raise CommandError(
                    f"{name!r}: expected type {expected_type!r} but corpus says "
                    f"{mapped!r}."
                )
            selected[name] = item
        return selected

    # --- Identité et relance --------------------------------------------

    def _find_existing(self, item: Mapping[str, Any], *, name: str) -> Entity | None:
        """Retourne la fiche déjà présente, ou lève en cas de conflit d'identité.

        Concordance complète — nom, type et slug — : la fiche est ignorée.
        Concordance partielle : c'est un conflit, signalé comme erreur plutôt
        que contourné par un suffixe de slug arbitraire.
        """
        entity_type = ENTITY_TYPES[str(item["entity_type"])]
        slug = slugify(name)

        by_slug = Entity.objects.filter(slug=slug).first()
        by_identity = Entity.objects.filter(name=name, entity_type=entity_type).first()

        if by_slug is not None and by_identity is not None:
            if by_slug.pk == by_identity.pk:
                return by_slug
            raise CommandError(
                f"{name!r}: identity conflict — slug {slug!r} and "
                f"(name, type) point to two different entities."
            )
        if by_slug is not None:
            raise CommandError(
                f"{name!r}: identity conflict — slug {slug!r} is already used by "
                f"{by_slug.name!r} ({by_slug.entity_type}). Refusing to rename or "
                "to suffix the slug."
            )
        if by_identity is not None:
            raise CommandError(
                f"{name!r}: identity conflict — an entity named {name!r} of type "
                f"{entity_type!r} already exists with slug {by_identity.slug!r}."
            )
        return None

    # --- Référentiels ----------------------------------------------------

    def _ensure_base_cultural_areas(self, notes: list[str]) -> dict[str, CulturalArea]:
        """Crée ou réutilise les aires de référence, parents d'abord."""
        areas: dict[str, CulturalArea] = {}
        for name, kind, parent_name in BASE_CULTURAL_AREAS:
            parent = areas.get(parent_name) if parent_name else None
            areas[name] = self._get_or_create_area(
                name, kind=kind, parent=parent, notes=notes
            )
        return areas

    def _get_or_create_area(
        self,
        name: str,
        *,
        kind: str,
        parent: CulturalArea | None,
        notes: list[str],
    ) -> CulturalArea:
        slug = slugify(name)
        existing = CulturalArea.objects.filter(slug=slug).first()
        if existing is not None:
            self._warn_reference_conflict(
                existing,
                {
                    "name": name,
                    "kind": kind,
                    "parent_id": parent.pk if parent else None,
                },
                notes=notes,
            )
            return existing
        area = CulturalArea(name=name, slug=slug, kind=kind, parent=parent)
        area.full_clean()
        area.save()
        return area

    def _get_or_create_country(self, name: str, *, notes: list[str]) -> Country:
        slug = slugify(name)
        existing = Country.objects.filter(slug=slug).first()
        iso_code = COUNTRY_ISO_CODES.get(name, "")
        if not iso_code:
            notes.append(
                f"Country {name!r}: no ISO code in the explicit mapping; left empty."
            )
        if existing is not None:
            self._warn_reference_conflict(
                existing, {"name": name, "iso_code": iso_code}, notes=notes
            )
            return existing
        country = Country(name=name, slug=slug, iso_code=iso_code)
        country.full_clean()
        country.save()
        return country

    def _get_or_create_ethnicity(self, name: str, *, notes: list[str]) -> Ethnicity:
        slug = slugify(name)
        existing = Ethnicity.objects.filter(slug=slug).first()
        if existing is not None:
            self._warn_reference_conflict(existing, {"name": name}, notes=notes)
            return existing
        # `primary_cultural_area` est laissé nul : le corpus donne la région de
        # la *figure*, pas celle de l'*ethnie*. L'inférer serait inventer.
        ethnicity = Ethnicity(name=name, slug=slug)
        ethnicity.full_clean()
        ethnicity.save()
        return ethnicity

    def _get_or_create_domain(self, name: str, *, notes: list[str]) -> Domain:
        slug = slugify(name)
        existing = Domain.objects.filter(slug=slug).first()
        if existing is not None:
            self._warn_reference_conflict(existing, {"name": name}, notes=notes)
            return existing
        domain = Domain(name=name, slug=slug)
        domain.full_clean()
        domain.save()
        return domain

    def _warn_reference_conflict(
        self, existing: Any, expected: Mapping[str, Any], *, notes: list[str]
    ) -> None:
        """Signale un référentiel existant divergent, sans le réécrire."""
        for field, value in expected.items():
            current = getattr(existing, field)
            if (field == "parent_id" or value not in (None, "")) and current != value:
                notes.append(
                    f"{type(existing).__name__} {existing.slug!r}: existing "
                    f"{field}={current!r} differs from corpus value {value!r}; "
                    "kept as is, not overwritten."
                )

    # --- Import d'une fiche ---------------------------------------------

    def _import_entity(
        self,
        item: Mapping[str, Any],
        *,
        name: str,
        areas: Mapping[str, CulturalArea],
        notes: list[str],
    ) -> Entity:
        """Transforme puis crée une fiche et son profil, via le service."""
        entity_type = ENTITY_TYPES[str(item["entity_type"])]
        origin = item.get("origin", {})
        identity = item.get("identity", {})
        attributes = item.get("attributes", {})
        appearance = item.get("appearance", {})
        story = item.get("story", {})

        raw_gender = str(identity.get("gender", ""))
        gender = GENDERS.get(raw_gender)
        if gender is None:
            raise CommandError(
                f"{name!r}: unknown gender {raw_gender!r}; refusing to guess."
            )

        characteristics = clean_list(
            story.get("characteristics"),
            label=f"{name}.story.characteristics",
            notes=notes,
        )
        physical_signs = clean_list(
            appearance.get("physical_signs"),
            label=f"{name}.appearance.physical_signs",
            notes=notes,
        )
        symbols = clean_list(
            attributes.get("symbols"), label=f"{name}.attributes.symbols", notes=notes
        )
        power_objects = clean_list(
            attributes.get("power_objects"),
            label=f"{name}.attributes.power_objects",
            notes=notes,
        )
        symbolic_animals = clean_list(
            attributes.get("symbolic_animals"),
            label=f"{name}.attributes.symbolic_animals",
            notes=notes,
        )
        for label, values in (
            ("characteristics", characteristics),
            ("physical_signs", physical_signs),
            ("symbols", symbols),
            ("power_objects", power_objects),
            ("symbolic_animals", symbolic_animals),
        ):
            check_array_item_lengths(values, label=f"{name}.{label}", notes=notes)

        primary_country, secondary_countries, primary_area = self._resolve_origin(
            origin, name=name, areas=areas, notes=notes
        )
        primary_ethnicity = self._resolve_ethnicity(origin, name=name, notes=notes)

        entity_data: dict[str, Any] = {
            "name": name,
            "slug": slugify(name),
            "entity_type": entity_type,
            "category": clean_text(
                item.get("category"), label=f"{name}.category", notes=notes
            ),
            "gender": gender,
            "cultural_role": clean_text(
                identity.get("cultural_role"),
                label=f"{name}.identity.cultural_role",
                notes=notes,
            ),
            "alignment": clean_text(
                identity.get("alignment"),
                label=f"{name}.identity.alignment",
                notes=notes,
            ),
            "story_description": clean_text(
                story.get("description"), label=f"{name}.story.description", notes=notes
            ),
            "characteristics": characteristics,
            "physical_signs": physical_signs,
            "symbols": symbols,
            "power_objects": power_objects,
            "symbolic_animals": symbolic_animals,
            "manifestations": clean_text(
                appearance.get("manifestations"),
                label=f"{name}.appearance.manifestations",
                notes=notes,
            ),
            "primary_country": primary_country,
            "primary_cultural_area": primary_area,
            "primary_ethnicity": primary_ethnicity,
        }

        try:
            entity = create_entity_with_profile(
                entity_data=entity_data,
                profile_data=self._build_profile_data(
                    item, entity_type=entity_type, name=name, notes=notes
                ),
            )
        except ValidationError as error:
            raise CommandError(f"{name!r}: validation failed — {error}") from error

        # Collections, après création : le service s'arrête volontairement au
        # couple entité/profil.
        for country in secondary_countries:
            entity.secondary_countries.add(country)

        domains = reconcile_domains(item, name=name, notes=notes)
        for domain_name in domains:
            entity.domains.add(self._get_or_create_domain(domain_name, notes=notes))

        notes.append(
            f"{name}: created as draft, without owner, review or deletion marks; "
            "sources left empty (the pilot corpus carries none)."
        )
        return entity

    def _resolve_origin(
        self,
        origin: Mapping[str, Any],
        *,
        name: str,
        areas: Mapping[str, CulturalArea],
        notes: list[str],
    ) -> tuple[Country | None, list[Country], CulturalArea | None]:
        """Résout pays principal, pays secondaires et aire principale."""
        raw_country = clean_text(
            origin.get("country"), label=f"{name}.origin.country", notes=notes
        )
        raw_region = clean_text(
            origin.get("cultural_region"),
            label=f"{name}.origin.cultural_region",
            notes=notes,
        )

        parts = [part.strip() for part in raw_country.split("/") if part.strip()]
        real_countries: list[str] = []
        area_override: str | None = None
        for part in parts:
            if part in NON_COUNTRY_ORIGINS:
                area_override = NON_COUNTRY_ORIGINS[part]
                notes.append(
                    f"{name}: origin.country {part!r} is not a country; mapped to "
                    "a cultural area and primary_country left null."
                )
                continue
            real_countries.append(part)

        primary: Country | None = None
        secondary: list[Country] = []
        for index, country_name in enumerate(real_countries):
            country = self._get_or_create_country(country_name, notes=notes)
            if index == 0:
                primary = country
            elif country.pk != (primary.pk if primary else None):
                secondary.append(country)
        if len(real_countries) > 1:
            notes.append(
                f"{name}: composite origin {raw_country!r} split into primary "
                f"{real_countries[0]!r} and secondary "
                f"{', '.join(real_countries[1:])}."
            )

        area_name = area_override or raw_region
        area: CulturalArea | None = None
        if area_name:
            area = areas.get(area_name)
            if area is None:
                raise CommandError(
                    f"{name!r}: cultural area {area_name!r} is not part of the "
                    "prepared reference areas; refusing to invent it."
                )
            if area_override:
                notes.append(
                    f"{name}: precise area {area_override!r} used as primary; its "
                    "parent region remains reachable through `parent`, without "
                    "artificial duplication."
                )
        return primary, secondary, area

    def _resolve_ethnicity(
        self, origin: Mapping[str, Any], *, name: str, notes: list[str]
    ) -> Ethnicity | None:
        """Résout l'ethnie principale, en écartant les valeurs vagues."""
        raw = clean_text(
            origin.get("ethnicity"), label=f"{name}.origin.ethnicity", notes=notes
        )
        if not raw:
            return None
        if raw.lower() in VAGUE_ETHNICITIES:
            notes.append(
                f"{name}: ethnicity {raw!r} is too vague to become a reference "
                "row; reported instead of created, primary_ethnicity left null."
            )
            return None
        return self._get_or_create_ethnicity(raw, notes=notes)

    def _build_profile_data(
        self,
        item: Mapping[str, Any],
        *,
        entity_type: str,
        name: str,
        notes: list[str],
    ) -> dict[str, Any]:
        """Extrait les seuls champs métier de `type_specific` pour le bon profil.

        Les clés absentes ne sont pas fournies : le profil utilise alors ses
        propres valeurs par défaut, sans qu'une absence devienne un fait.
        """
        specific = item.get("type_specific", {}) or {}
        if entity_type == EntityType.DIVINITY:
            block = specific.get("divinity", {}) or {}
            cult = block.get("cult", {}) or {}
            return self._drop_empty(
                {
                    "cult_offerings": clean_list(
                        cult.get("offerings"),
                        label=f"{name}.divinity.cult.offerings",
                        notes=notes,
                    ),
                    "cult_taboos": clean_list(
                        cult.get("taboos"),
                        label=f"{name}.divinity.cult.taboos",
                        notes=notes,
                    ),
                }
            )
        if entity_type == EntityType.HERO:
            block = specific.get("hero", {}) or {}
            return self._drop_empty(
                {
                    "titles": clean_list(
                        block.get("titles"), label=f"{name}.hero.titles", notes=notes
                    ),
                    "achievements": clean_list(
                        block.get("achievements"),
                        label=f"{name}.hero.achievements",
                        notes=notes,
                    ),
                    "weapons_or_artifacts": clean_list(
                        block.get("weapons_or_artifacts"),
                        label=f"{name}.hero.weapons_or_artifacts",
                        notes=notes,
                    ),
                    "legacy": clean_text(
                        block.get("legacy"), label=f"{name}.hero.legacy", notes=notes
                    ),
                }
            )
        block = specific.get("creature", {}) or {}
        return self._drop_empty(
            {
                "habitat": clean_list(
                    block.get("habitat"), label=f"{name}.creature.habitat", notes=notes
                ),
                "powers": clean_list(
                    block.get("powers"), label=f"{name}.creature.powers", notes=notes
                ),
                "strengths": clean_list(
                    block.get("strengths"),
                    label=f"{name}.creature.strengths",
                    notes=notes,
                ),
                "weaknesses": clean_list(
                    block.get("weaknesses"),
                    label=f"{name}.creature.weaknesses",
                    notes=notes,
                ),
                "diet": clean_text(
                    block.get("diet"), label=f"{name}.creature.diet", notes=notes
                ),
                "size": clean_text(
                    block.get("size"), label=f"{name}.creature.size", notes=notes
                ),
            }
        )

    def _drop_empty(self, data: Mapping[str, Any]) -> dict[str, Any]:
        """Retire les valeurs vides afin de laisser jouer les défauts du modèle."""
        return {key: value for key, value in data.items() if value not in ([], "")}

    # --- Relations, seconde passe ---------------------------------------

    def _import_relations(
        self,
        entity: Entity,
        item: Mapping[str, Any],
        *,
        resolvable: Mapping[str, Entity],
        notes: list[str],
    ) -> list[str]:
        """Crée les relations sortantes de la fiche.

        Le sens suit celui du modèle : `parents` donne des liens `parent` dont
        la cible est le parent de la fiche, `conjoint` donne des `consort`.
        `descendants` n'est **pas** converti : rien ne garantit qu'un nom cité
        soit un enfant direct plutôt qu'un descendant lointain.

        Seules les références exactes vers les fiches **du pilote** sont
        résolues. Aucun rapprochement n'est tenté avec les fiches
        préexistantes hors sélection. Une cible du pilote déjà présente peut
        être utilisée après concordance explicite de son nom, type et slug,
        sans modifier sa fiche ni ses propres liens.
        """
        relations = item.get("relations", {}) or {}
        created: list[str] = []

        for key, kind in (
            ("parents", RelationKind.PARENT),
            ("conjoint", RelationKind.CONSORT),
        ):
            for target_name in clean_list(
                relations.get(key), label=f"{entity.name}.relations.{key}", notes=notes
            ):
                target = resolvable.get(target_name)
                if target is not None and target.pk == entity.pk:
                    notes.append(
                        f"{entity.name}: self-reference {target_name!r} in "
                        f"relations.{key} skipped."
                    )
                    continue
                if target is None:
                    notes.append(
                        f"{entity.name}: relation target {target_name!r} "
                        f"({kind}) left unresolved in `to_name`; no match within "
                        "the pilot selection, and no fuzzy matching against "
                        "pre-existing entities is attempted."
                    )
                relation = EntityRelation(
                    from_entity=entity,
                    to_entity=target,
                    to_name="" if target is not None else target_name,
                    kind=kind,
                )
                relation.full_clean()
                relation.save()
                created.append(
                    f"{entity.name} —{kind}→ "
                    f"{target.name if target else target_name}"
                    f"{'' if target else ' (unresolved)'}"
                )

        descendants = clean_list(
            relations.get("descendants"),
            label=f"{entity.name}.relations.descendants",
            notes=notes,
        )
        if descendants:
            notes.append(
                f"{entity.name}: relations.descendants carries "
                f"{', '.join(descendants)} — NOT imported. A cited descendant is "
                "not necessarily a direct child; the direction needs editorial "
                "arbitration. Information preserved in this report only."
            )
        return created

    # --- Bilan -----------------------------------------------------------

    def _report(
        self,
        *,
        corpus_path: Path,
        dry_run: bool,
        created: Sequence[Entity],
        skipped: Sequence[str],
        relations_created: Sequence[str],
        notes: Sequence[str],
    ) -> None:
        write = self.stdout.write
        write("=" * 72)
        write("Pilot import summary")
        write("=" * 72)
        write(f"Corpus          : {corpus_path}")
        write(f"Mode            : {'DRY RUN (rolled back)' if dry_run else 'COMMIT'}")
        write(f"Entities created: {len(created)}")
        for entity in created:
            write(f"  + {entity.name} ({entity.entity_type}) slug={entity.slug}")
        write(f"Entities skipped: {len(skipped)}")
        for label in skipped:
            write(f"  = {label}")
        write(f"Relations       : {len(relations_created)}")
        for label in relations_created:
            write(f"  → {label}")
        write(f"Notes           : {len(notes)}")
        for note in notes:
            write(f"  - {note}")
        if dry_run:
            write("")
            write("Dry run: the transaction was rolled back, nothing was persisted.")
