"""Constructeurs d'objets pour les tests du domaine mythologique.

Deux fonctions nommées, pas une bibliothèque de factories : le modèle est
encore petit et la phase 2 le fera évoluer.
"""

from typing import Any

from mythology.models import DivinityProfile, Entity, EntityType, Gender


def create_entity(
    name: str = "Shango",
    slug: str = "shango",
    entity_type: str = EntityType.DIVINITY,
    gender: str = Gender.MALE,
    **extra: Any,
) -> Entity:
    """Crée une entité valide, surchargeable champ par champ."""
    return Entity.objects.create(
        name=name,
        slug=slug,
        entity_type=entity_type,
        gender=gender,
        **extra,
    )


def create_divinity_profile(entity: Entity, **extra: Any) -> DivinityProfile:
    """Crée un profil de divinité rattaché à `entity`."""
    return DivinityProfile.objects.create(entity=entity, **extra)
