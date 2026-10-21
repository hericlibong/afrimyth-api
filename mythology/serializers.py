"""Read serializers for the mythology domain.

Two distinct representations of `Entity`: a compact one for the collection
and a detailed one that nests the type profile. Write serializers will arrive
with the CRUD endpoints of a later phase.

**These docstrings are public.** drf-spectacular turns each class docstring
into the `description` of the matching OpenAPI component, rendered in Swagger
UI and ReDoc. They are therefore written in English, per ADR 0003, and
addressed to an API consumer rather than to a maintainer. Internal reasoning
stays in French comments.
"""

from typing import Any

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from mythology.models import (
    Country,
    CreatureProfile,
    CulturalArea,
    DivinityProfile,
    Domain,
    Entity,
    EntityRelation,
    Ethnicity,
    HeroProfile,
    Source,
)
from mythology.selectors import is_publicly_visible


class SourceSerializer(serializers.ModelSerializer[Source]):
    """A documentary source attached to an entity.

    `url` is an empty string when the source has none — a book or an oral
    testimony, for instance — and `accessed_at` is a consultation date, not a
    publication date.
    """

    class Meta:
        model = Source
        fields = ["id", "label", "kind", "url", "accessed_at", "notes"]


class EntityReferenceSerializer(serializers.ModelSerializer[Entity]):
    """A compact reference to another entity.

    Deliberately limited to four fields: nesting a target's full detail would
    restart serialization through its own relations. Use the `slug` to fetch
    the complete record when needed.
    """

    class Meta:
        model = Entity
        fields = ["id", "slug", "name", "entity_type"]


class EntityRelationSerializer(serializers.ModelSerializer[EntityRelation]):
    """An outgoing relation from one entity to another figure.

    Exactly one of the two target forms is filled: `to_entity` for a figure
    that has a record, `to_name` for one that is only cited by name. `kind`
    qualifies the **target**, read from the source: `parent` means "the target
    is a parent of this entity".
    """

    to_entity = EntityReferenceSerializer(read_only=True, allow_null=True)

    class Meta:
        model = EntityRelation
        fields = ["id", "kind", "to_entity", "to_name", "notes"]


class CountrySerializer(serializers.ModelSerializer[Country]):
    """A country, with its optional ISO 3166-1 alpha-2 code.

    `iso_code` is an empty string when no code is recorded.
    """

    class Meta:
        model = Country
        fields = ["id", "slug", "name", "iso_code"]


class CulturalAreaSerializer(serializers.ModelSerializer[CulturalArea]):
    """A cultural area: an African region, a transregional scope or a diaspora.

    The area's own hierarchy — its parent and children — is not nested here.
    Use the `cultural_area` filter on the collection, which already follows
    that hierarchy downwards.
    """

    class Meta:
        model = CulturalArea
        fields = ["id", "slug", "name", "kind"]


class EthnicitySerializer(serializers.ModelSerializer[Ethnicity]):
    """An ethnicity, reduced to its identity.

    Its own cultural area is not nested: the entity's area is already
    exposed, and nesting its ethnicity's area would add a graph level with no
    established client need.
    """

    class Meta:
        model = Ethnicity
        fields = ["id", "slug", "name"]


class DomainSerializer(serializers.ModelSerializer[Domain]):
    """A domain of attribution, shared by all three entity types."""

    class Meta:
        model = Domain
        fields = ["id", "slug", "name"]


class DivinityProfileSerializer(serializers.ModelSerializer[DivinityProfile]):
    """Cult data specific to a divinity.

    Symbolic attributes common to all types — domains, symbols, power
    objects, symbolic animals — live on the entity itself, not here.
    """

    class Meta:
        model = DivinityProfile
        fields = [
            "cult_offerings",
            "cult_taboos",
            "cult_rituals",
            "cult_places",
            "cult_festivals",
        ]


class HeroProfileSerializer(serializers.ModelSerializer[HeroProfile]):
    """Data specific to a hero.

    Allies and enemies are not here: they are relations between figures, and
    appear in the entity's `relations`.
    """

    class Meta:
        model = HeroProfile
        fields = [
            "titles",
            "achievements",
            "quests",
            "weapons_or_artifacts",
            "legacy",
            "historical_context",
        ]


class CreatureProfileSerializer(serializers.ModelSerializer[CreatureProfile]):
    """Data specific to a creature.

    `threat_level` is `null` when no level has been assessed.
    """

    class Meta:
        model = CreatureProfile
        fields = [
            "habitat",
            "powers",
            "strengths",
            "weaknesses",
            "encounter_omens",
            "encounter_rules",
            "known_sightings",
            "diet",
            "size",
            "appearance_notes",
            "threat_level",
        ]


class EntityListSerializer(serializers.ModelSerializer[Entity]):
    """Compact representation of an entity, used in the collection.

    Profiles, reference data, relations and documentary sources are only
    available on the detail endpoint.
    """

    class Meta:
        model = Entity
        fields = ["id", "slug", "name", "entity_type", "category"]


class EntityDetailSerializer(serializers.ModelSerializer[Entity]):
    """Full representation of one entity.

    The three profile keys are **always present**: the one matching
    `entity_type` carries the object, the other two are `null`. A stable set
    of keys spares a client from testing for a key's presence in addition to
    its value.

    Nested references honour the public visibility rule: `variant_of` is
    `null` and a relation is omitted entirely when its resolved target is not
    publicly visible.
    """

    # Note interne : `allow_null=True` ne change pas la charge utile — ces
    # serializers sont en lecture seule — mais il rend le schéma fidèle, car
    # ces références et profils peuvent bel et bien valoir `null` en réponse.
    #
    # Contrat d'utilisation : ce serializer masque de lui-même les références
    # non publiques, via `is_publicly_visible()`, et non par le seul queryset.
    # Il est donc sûr quel que soit le queryset reçu. Il n'est en revanche
    # *gratuit* que sur `selectors.public_entity_detail()`, qui joint
    # `variant_of` et précharge les relations déjà filtrées ; sur un queryset
    # nu, le filtrage reste correct mais coûte une requête par référence.
    divinity_profile = DivinityProfileSerializer(read_only=True, allow_null=True)
    hero_profile = HeroProfileSerializer(read_only=True, allow_null=True)
    creature_profile = CreatureProfileSerializer(read_only=True, allow_null=True)

    primary_country = CountrySerializer(read_only=True, allow_null=True)
    secondary_countries = CountrySerializer(many=True, read_only=True)
    primary_ethnicity = EthnicitySerializer(read_only=True, allow_null=True)
    secondary_ethnicities = EthnicitySerializer(many=True, read_only=True)
    primary_cultural_area = CulturalAreaSerializer(read_only=True, allow_null=True)
    secondary_cultural_areas = CulturalAreaSerializer(many=True, read_only=True)
    domains = DomainSerializer(many=True, read_only=True)

    variant_of = serializers.SerializerMethodField(
        help_text=(
            "The reference figure this entity is a cultural variant of, or "
            "`null`. Also `null` when the reference exists but is not "
            "publicly visible: a hidden reference is indistinguishable from "
            "the absence of one."
        )
    )
    # Seules les relations sortantes sont exposées. Les relations entrantes
    # — `relations_to` — et les variantes inverses viendront si un besoin
    # client le justifie ; les ajouter maintenant doublerait la charge utile
    # sans usage établi.
    relations = serializers.SerializerMethodField(
        help_text=(
            "Outgoing relations. Links whose resolved target is not publicly "
            "visible are omitted entirely, and the hidden target's name is "
            "never copied into `to_name`. Incoming relations are not exposed."
        )
    )
    sources = SourceSerializer(many=True, read_only=True)

    @extend_schema_field(EntityReferenceSerializer(allow_null=True))
    def get_variant_of(self, entity: Entity) -> dict[str, Any] | None:
        """Expose the reference figure only when it is publicly visible.

        A non-public reference is rendered exactly like the absence of a
        reference: no id, slug, name or type leaks.
        """
        if not is_publicly_visible(entity.variant_of):
            return None
        return EntityReferenceSerializer(entity.variant_of).data

    @extend_schema_field(EntityRelationSerializer(many=True))
    def get_relations(self, entity: Entity) -> list[dict[str, Any]]:
        """Expose the outgoing relations that may be published.

        The filtering is **repeated here**, even though the view's queryset
        already prefetches filtered relations. That redundancy is deliberate:
        it guarantees that no use of this serializer — a test, a future
        internal call, a forgotten queryset — can publish a link to a hidden
        target.

        A discarded link disappears entirely; its `to_name` is not filled
        with the hidden target's name.
        """
        visible = [
            relation
            for relation in entity.relations_from.all()
            if relation.to_entity_id is None or is_publicly_visible(relation.to_entity)
        ]
        return list(EntityRelationSerializer(visible, many=True).data)

    class Meta:
        model = Entity
        fields = [
            "id",
            "slug",
            "name",
            "entity_type",
            "category",
            "gender",
            "cultural_role",
            "alignment",
            "story_description",
            "characteristics",
            "physical_signs",
            "symbols",
            "power_objects",
            "symbolic_animals",
            "manifestations",
            "primary_country",
            "secondary_countries",
            "primary_ethnicity",
            "secondary_ethnicities",
            "primary_cultural_area",
            "secondary_cultural_areas",
            "domains",
            "variant_of",
            "relations",
            "sources",
            "created_at",
            "updated_at",
            "divinity_profile",
            "hero_profile",
            "creature_profile",
        ]
