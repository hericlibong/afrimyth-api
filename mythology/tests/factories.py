"""Constructeurs d'objets pour les tests du domaine mythologique.

Des fonctions nommées, pas une bibliothèque de factories : le modèle est
encore petit et la phase 2 le fait encore évoluer.
"""

from typing import Any

from mythology.models import (
    Country,
    CreatureProfile,
    CulturalArea,
    CulturalAreaKind,
    DivinityProfile,
    Domain,
    Entity,
    EntityType,
    Ethnicity,
    Gender,
    HeroProfile,
)


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


def create_hero(name: str = "Soundiata", slug: str = "soundiata") -> Entity:
    """Crée une entité de type `hero`."""
    return create_entity(name=name, slug=slug, entity_type=EntityType.HERO)


def create_creature(name: str = "Mokele-mbembe", slug: str = "mokele-mbembe") -> Entity:
    """Crée une entité de type `creature`."""
    return create_entity(name=name, slug=slug, entity_type=EntityType.CREATURE)


def create_hero_profile(entity: Entity, **extra: Any) -> HeroProfile:
    """Crée un profil de héros rattaché à `entity`."""
    return HeroProfile.objects.create(entity=entity, **extra)


def create_creature_profile(entity: Entity, **extra: Any) -> CreatureProfile:
    """Crée un profil de créature rattaché à `entity`."""
    return CreatureProfile.objects.create(entity=entity, **extra)


def create_cultural_area(
    name: str = "West Africa",
    slug: str = "west-africa",
    kind: str = CulturalAreaKind.AFRICAN_REGION,
    **extra: Any,
) -> CulturalArea:
    """Crée une aire culturelle."""
    return CulturalArea.objects.create(name=name, slug=slug, kind=kind, **extra)


def create_country(
    name: str = "Nigeria",
    slug: str = "nigeria",
    iso_code: str = "NG",
    **extra: Any,
) -> Country:
    """Crée un pays."""
    return Country.objects.create(name=name, slug=slug, iso_code=iso_code, **extra)


def create_ethnicity(
    name: str = "Yoruba",
    slug: str = "yoruba",
    **extra: Any,
) -> Ethnicity:
    """Crée une ethnie."""
    return Ethnicity.objects.create(name=name, slug=slug, **extra)


def create_domain(
    name: str = "Thunder",
    slug: str = "thunder",
    **extra: Any,
) -> Domain:
    """Crée un domaine."""
    return Domain.objects.create(name=name, slug=slug, **extra)
