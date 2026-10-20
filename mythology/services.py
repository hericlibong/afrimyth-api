"""Fonctions métier du domaine mythologique.

Ce module ne contient pas une « couche de services » : seulement les
fonctions explicitement demandées par la roadmap, là où une règle métier ne
peut pas être portée par un modèle seul. La décision 6 de l'ADR 0002 prévoit
qu'une entité possède exactement le profil correspondant à son type, et
précise que cette cohérence est « garantie par le service de création », non
par une abstraction polymorphe.
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
    """Retourne les noms de champs concrets et éditables d'un modèle.

    Déduits par introspection plutôt qu'écrits en dur : la liste suit donc
    l'évolution des modèles sans intervention. Sont exclus d'office les
    champs non éditables — `id`, `created_at` et `updated_at` — ainsi que les
    relations multiples, qui ne sont pas des colonnes.
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
    """Retourne les noms des relations multiples du modèle."""
    return {field.name for field in model._meta.many_to_many}


def _reject_unknown_fields(
    data: Mapping[str, Any],
    model: type[models.Model],
    *,
    label: str,
    forbidden: Mapping[str, str],
) -> None:
    """Refuse tout champ interdit ou inconnu, avant la moindre écriture.

    Les messages sont en anglais, conformément à l'ADR 0003, et nomment les
    champs fautifs afin que l'appelant puisse corriger son entrée.
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
    """Crée une entité et exactement le profil correspondant à son type.

    Les deux écritures ont lieu dans la même transaction : soit l'entité et
    son profil existent, soit rien n'est créé. C'est la garantie que la
    décision 6 de l'ADR 0002 attend d'un service de création.

    Args:
        entity_data: champs simples et clés étrangères de l'entité.
            `entity_type` est obligatoire. Les relations multiples sont
            refusées, voir la section « Frontière » ci-dessous.
        profile_data: champs du profil correspondant au type. Un
            dictionnaire absent ou vide crée le profil avec ses valeurs par
            défaut — **jamais** une entité sans profil.

    Returns:
        L'entité créée, enregistrée, avec son profil en base.

    Raises:
        ValidationError: type absent ou inconnu, champ inconnu, champ hors
            périmètre, ou échec de `full_clean()` sur l'entité ou le profil.
            Dans tous les cas, aucune ligne ne subsiste.

    **Portée de la garantie.** Cette fonction garantit le résultat de ses
    propres appels réussis. Elle ne contrôle pas les autres chemins
    d'écriture : un `Entity.objects.create()` direct, un import de données ou
    l'administration Django peuvent toujours produire une entité sans profil,
    et rien n'empêche de changer `entity_type` après coup. Couvrir ces
    chemins relève de la phase 4.

    **Frontière.** Les relations multiples — `secondary_countries`,
    `secondary_ethnicities`, `secondary_cultural_areas`, `domains` — ainsi
    que les relations entre figures et les sources ne sont pas traitées ici,
    et leur passage dans `entity_data` est refusé pour limiter le rôle de
    cette fonction au couple entité/profil. Elles exigent une entité déjà
    enregistrée, mais pourraient être ajoutées dans une même transaction
    sans affaiblir son atomicité. L'import appellera cette fonction dans sa
    propre transaction, puis rattachera ces collections.

    **Création seulement.** La fonction ne modifie jamais une fiche ou un
    profil préexistant : `id` et `pk` ne sont pas acceptés, et le
    rattachement du profil est imposé par la fonction, non par l'appelant.
    Les dictionnaires reçus ne sont pas modifiés.
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
