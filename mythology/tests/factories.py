"""Object builders for the tests of the mythological domain.

Named functions, not a factory library: the model is still small and
phase 2 keeps making it evolve.
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
    EntityRelation,
    EntityStatus,
    EntityType,
    Ethnicity,
    Gender,
    HeroProfile,
    RelationKind,
    Source,
    SourceKind,
)


def create_entity(
    name: str = "Shango",
    slug: str = "shango",
    entity_type: str = EntityType.DIVINITY,
    gender: str = Gender.MALE,
    **extra: Any,
) -> Entity:
    """Create a valid entity, overridable field by field."""
    return Entity.objects.create(
        name=name,
        slug=slug,
        entity_type=entity_type,
        gender=gender,
        **extra,
    )


def create_published_entity(**extra: Any) -> Entity:
    """Create a **published** entity, hence visible to the public API.

    A separate factory, rather than changing the default of `create_entity`:
    the default status of the model stays `draft`, and the tests that check
    that default - models, service, import - must keep observing it. Public
    read tests therefore publish explicitly.
    """
    return create_entity(status=EntityStatus.PUBLISHED, **extra)


def publish(entity: Entity) -> Entity:
    """Publish an already created record, in the test database only.

    Useful after an import, which deliberately creates drafts: public reading
    can only be exercised once the record is published.
    """
    entity.status = EntityStatus.PUBLISHED
    entity.save(update_fields=["status"])
    return entity


def create_divinity_profile(entity: Entity, **extra: Any) -> DivinityProfile:
    """Create a divinity profile attached to `entity`."""
    return DivinityProfile.objects.create(entity=entity, **extra)


def create_hero(name: str = "Soundiata", slug: str = "soundiata") -> Entity:
    """Create an entity of type `hero`."""
    return create_entity(name=name, slug=slug, entity_type=EntityType.HERO)


def create_creature(name: str = "Mokele-mbembe", slug: str = "mokele-mbembe") -> Entity:
    """Create an entity of type `creature`."""
    return create_entity(name=name, slug=slug, entity_type=EntityType.CREATURE)


def create_hero_profile(entity: Entity, **extra: Any) -> HeroProfile:
    """Create a hero profile attached to `entity`."""
    return HeroProfile.objects.create(entity=entity, **extra)


def create_creature_profile(entity: Entity, **extra: Any) -> CreatureProfile:
    """Create a creature profile attached to `entity`."""
    return CreatureProfile.objects.create(entity=entity, **extra)


def create_cultural_area(
    name: str = "West Africa",
    slug: str = "west-africa",
    kind: str = CulturalAreaKind.AFRICAN_REGION,
    **extra: Any,
) -> CulturalArea:
    """Create a cultural area."""
    return CulturalArea.objects.create(name=name, slug=slug, kind=kind, **extra)


def create_country(
    name: str = "Nigeria",
    slug: str = "nigeria",
    iso_code: str = "NG",
    **extra: Any,
) -> Country:
    """Create a country."""
    return Country.objects.create(name=name, slug=slug, iso_code=iso_code, **extra)


def create_ethnicity(
    name: str = "Yoruba",
    slug: str = "yoruba",
    **extra: Any,
) -> Ethnicity:
    """Create an ethnicity."""
    return Ethnicity.objects.create(name=name, slug=slug, **extra)


def create_domain(
    name: str = "Thunder",
    slug: str = "thunder",
    **extra: Any,
) -> Domain:
    """Create a domain."""
    return Domain.objects.create(name=name, slug=slug, **extra)


def create_source(
    entity: Entity,
    label: str = "Fictional Handbook of Test Myths",
    kind: str = SourceKind.BOOK,
    **extra: Any,
) -> Source:
    """Create a **fictitious** documentary source attached to `entity`.

    The references used by the tests are invented for demonstration: no real
    publication is cited, and none is attributed to the corpus.
    """
    return Source.objects.create(entity=entity, label=label, kind=kind, **extra)


def create_relation(
    from_entity: Entity,
    kind: str = RelationKind.PARENT,
    to_entity: Entity | None = None,
    to_name: str = "",
    **extra: Any,
) -> EntityRelation:
    """Create an outgoing link, towards a record or towards a plain name.

    Direction reminder: `from_entity - kind -> target` reads as the target is
    a `kind` of `from_entity`.
    """
    return EntityRelation.objects.create(
        from_entity=from_entity,
        kind=kind,
        to_entity=to_entity,
        to_name=to_name,
        **extra,
    )
