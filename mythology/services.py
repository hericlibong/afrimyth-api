"""Business functions of the mythological domain.

This module is not a service layer: it holds only the functions the
roadmap explicitly asked for, where a business rule cannot be carried by
a model alone. Decision 6 of ADR 0002 states that an entity owns exactly
the profile matching its type, and specifies that this consistency is
guaranteed by the creation service, not by a polymorphic abstraction.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models, transaction

from mythology.models import (
    CreatureProfile,
    DivinityProfile,
    Entity,
    EntityType,
    HeroProfile,
)

ProfileModel = type[DivinityProfile] | type[HeroProfile] | type[CreatureProfile]

#: Le type de l'entité choisit seul le modèle de profil. Il n'existe
#: volontairement aucun paramètre concurrent qui permettrait de demander un
#: profil d'un autre type que celui de l'entité.
PROFILE_MODELS: dict[str, ProfileModel] = {
    EntityType.DIVINITY: DivinityProfile,
    EntityType.HERO: HeroProfile,
    EntityType.CREATURE: CreatureProfile,
}


def _writable_field_names(model: type[models.Model]) -> set[str]:
    """Return the concrete, editable field names of a model.

    Derived by introspection rather than hard-coded: the list therefore
    follows the models as they evolve, without intervention. Non-editable
    fields - `id`, `created_at` and `updated_at` - are excluded outright, as
    are many-to-many relations, which are not columns.
    """
    names: set[str] = set()
    for field in model._meta.concrete_fields:
        if not field.editable:
            continue
        names.add(field.name)
        if field.name != field.attname:
            # Autorise aussi la forme `primary_country_id` pour une clé
            # étrangère déjà résolue, utile à l'import.
            names.add(field.attname)
    return names


def _many_to_many_field_names(model: type[models.Model]) -> set[str]:
    """Return the names of the many-to-many relations of the model."""
    return {field.name for field in model._meta.many_to_many}


def _reject_unknown_fields(
    data: Mapping[str, Any],
    model: type[models.Model],
    *,
    label: str,
    forbidden: Mapping[str, str],
) -> None:
    """Refuse any forbidden or unknown field, before the slightest write.

    The messages are in English, as required by ADR 0003, and name the
    offending fields so that the caller can correct its input.
    """
    for name, reason in forbidden.items():
        if name in data:
            raise ValidationError({name: reason})

    unknown = sorted(set(data) - _writable_field_names(model))
    if unknown:
        raise ValidationError(
            {
                "__all__": (
                    f"Unknown or non-writable {label} field(s): "
                    f"{', '.join(unknown)}."
                )
            }
        )


def create_entity_with_profile(
    *,
    entity_data: Mapping[str, Any],
    profile_data: Mapping[str, Any] | None = None,
) -> Entity:
    """Create an entity and exactly the profile matching its type.

    Both writes happen in the same transaction: either the entity and its
    profile exist, or nothing is created. That is the guarantee decision 6 of
    ADR 0002 expects from a creation service.

    Args:
        entity_data: simple fields and foreign keys of the entity.
            `entity_type` is required. Many-to-many relations are refused,
            see the Boundary section below.
        profile_data: fields of the profile matching the type. A missing or
            empty dictionary creates the profile with its default values -
            **never** an entity without a profile.

    Returns:
        The created entity, saved, with its profile in the database.

    Raises:
        ValidationError: missing or unknown type, unknown field, field out of
            scope, or `full_clean()` failure on the entity or the profile. In
            every case, no row is left behind.

    **Scope of the guarantee.** This function guarantees the outcome of its
    own successful calls. It does not control the other write paths: a direct
    `Entity.objects.create()`, a data import or the Django admin can still
    produce an entity without a profile, and nothing prevents changing
    `entity_type` afterwards. Covering those paths belongs to phase 4.

    **Boundary.** Many-to-many relations - `secondary_countries`,
    `secondary_ethnicities`, `secondary_cultural_areas`, `domains` - as well
    as relations between figures and sources are not handled here, and
    passing one of them in `entity_data` is refused, in order to keep the
    role of this function to the entity/profile pair. They require an already
    saved entity, but could be added within the same transaction without
    weakening its atomicity. The import calls this function inside its own
    transaction, then attaches those collections.

    **Creation only.** The function never modifies a pre-existing record or
    profile: `id` and `pk` are not accepted, and the profile attachment is
    imposed by the function, not by the caller. The dictionaries received are
    not modified.
    """
    entity_type = entity_data.get("entity_type")
    if not entity_type:
        raise ValidationError(
            {"entity_type": "Provide an entity type to select the matching profile."}
        )
    if entity_type not in PROFILE_MODELS:
        expected = ", ".join(PROFILE_MODELS)
        raise ValidationError(
            {
                "entity_type": (
                    f"Unknown entity type {entity_type!r}. Expected: {expected}."
                )
            }
        )

    profile_model = PROFILE_MODELS[entity_type]

    collection_reason = (
        "Many-to-many and related collections are out of scope for this "
        "function. Create the entity first, then attach them."
    )
    _reject_unknown_fields(
        entity_data,
        Entity,
        label="entity",
        forbidden={
            "id": "The identifier is generated; it cannot be supplied.",
            "pk": "The identifier is generated; it cannot be supplied.",
            **{name: collection_reason for name in _many_to_many_field_names(Entity)},
            "sources": collection_reason,
            "relations_from": collection_reason,
            "relations_to": collection_reason,
        },
    )
    _reject_unknown_fields(
        profile_data or {},
        profile_model,
        label=f"{profile_model.__name__}",
        forbidden={
            "entity": "The profile is attached to the created entity automatically.",
            "entity_id": (
                "The profile is attached to the created entity automatically."
            ),
            "id": "The identifier is generated; it cannot be supplied.",
            "pk": "The identifier is generated; it cannot be supplied.",
        },
    )

    # Copies défensives : les dictionnaires de l'appelant ne sont pas touchés.
    with transaction.atomic():
        entity = Entity(**dict(entity_data))
        entity.full_clean()
        entity.save()

        profile = profile_model(entity=entity, **dict(profile_data or {}))
        profile.full_clean()
        profile.save()

    return entity
