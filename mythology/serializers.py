"""Read and create serializers for the mythology domain.

Four read representations of `Entity`: a compact one and a detailed one for
the **public** collection and detail, and their **private** counterparts,
which add the editorial fields and apply the caller's own visibility rule to
nested references. One write representation, `PrivateEntityCreateSerializer`,
which creates a draft entity and its profile on the private collection.
Updating, status transitions and deletion arrive with later increments.

The private representations are subclasses, not copies: they inherit every
business field and only declare what differs. Nothing switches a public
serializer into private mode — a request parameter least of all. The two are
distinct classes, chosen by the view that owns the route.

**These docstrings are public.** drf-spectacular turns each class docstring
into the `description` of the matching OpenAPI component, rendered in Swagger
UI and ReDoc. They are therefore written in English, per ADR 0003, and
addressed to an API consumer rather than to a maintainer. Internal reasoning
stays in French comments.
"""

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from accounts.models import User
from mythology.models import (
    Country,
    CreatureProfile,
    CulturalArea,
    DivinityProfile,
    Domain,
    Entity,
    EntityRelation,
    EntityStatus,
    EntityType,
    Ethnicity,
    HeroProfile,
    Source,
)
from mythology.selectors import (
    is_privately_readable,
    is_publicly_visible,
    private_entities,
    private_entity_detail,
)
from mythology.services import create_entity_with_profile


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


# --- Private editorial representations ----------------------------------
#
# Deux serializers privés, obtenus par héritage : ils ajoutent les champs
# éditoriaux et remplacent la garde des références imbriquées. Les classes
# publiques restent inchangées, donc leurs réponses aussi.
#
# Le propriétaire et le relecteur sont rendus par `account_identifier_field()` :
# un identifiant nullable, en lecture seule.


def caller_policy(
    context: Mapping[str, Any],
) -> tuple[frozenset[str], int | None]:
    """Return the caller's roles and identifier, taken from a serializer context.

    Restrictive by default. A serializer used without a valid caller — a test,
    a future internal call, a forgotten context — gets no role at all, so every
    structured reference is hidden. It never falls back to the public rule,
    which would be more permissive than this caller is entitled to.
    """
    roles = context.get("caller_roles") or frozenset()
    assert isinstance(roles, frozenset)
    caller_id = context.get("caller_id")
    return roles, caller_id


def account_identifier_field(
    help_text: str,
) -> serializers.PrimaryKeyRelatedField[User]:
    """Build a read-only, nullable account identifier field.

    The identifier is read from the record's own `*_id` column, so no account
    is queried — and no account data can be serialised through this field.
    """
    return serializers.PrimaryKeyRelatedField(
        read_only=True, allow_null=True, help_text=help_text
    )


class PrivateEntityListSerializer(EntityListSerializer):
    """Compact representation of an entity on the private collection.

    The five public fields, plus the editorial state and the owner. Profiles,
    reference data, relations and documentary sources are only available on
    the private detail endpoint, exactly as on the public one.
    """

    created_by = account_identifier_field(
        "Identifier of the account that owns this record, or `null` for an "
        "imported record that has no owner. No other account data is exposed."
    )

    class Meta(EntityListSerializer.Meta):
        fields = [*EntityListSerializer.Meta.fields, "status", "created_by"]


class PrivateEntityDetailSerializer(EntityDetailSerializer):
    """Full representation of one entity on the private detail endpoint.

    Carries every business field of the public detail, plus the editorial
    state, the owner and the review marks. Account records themselves are
    never serialised: the owner and reviewer appear as identifiers only.

    Nested references honour the **caller's own** visibility rule, not the
    public one: `variant_of` is `null` and a relation is omitted entirely when
    its resolved target is not readable by this caller. A reviewer therefore
    sees a draft reference that a contributor does not.
    """

    created_by = account_identifier_field(
        "Identifier of the account that owns this record, or `null` for an "
        "imported record that has no owner."
    )
    reviewed_by = account_identifier_field(
        "Identifier of the account that last reviewed this record, or `null` "
        "when it has never been reviewed."
    )

    # Les deux `SerializerMethodField` sont redéclarés pour leur `help_text` :
    # celui de la classe publique décrit la règle publique, qui n'est pas
    # celle appliquée ici.
    variant_of = serializers.SerializerMethodField(
        help_text=(
            "The reference figure this entity is a cultural variant of, or "
            "`null`. Also `null` when the reference exists but is not "
            "readable by the calling account."
        )
    )
    relations = serializers.SerializerMethodField(
        help_text=(
            "Outgoing relations. Links whose resolved target is not readable "
            "by the calling account are omitted entirely, and the hidden "
            "target's name is never copied into `to_name`. Incoming relations "
            "are not exposed."
        )
    )

    class Meta(EntityDetailSerializer.Meta):
        fields = [
            *EntityDetailSerializer.Meta.fields,
            "status",
            "created_by",
            "submitted_at",
            "reviewed_at",
            "reviewed_by",
            "review_notes",
        ]

    @extend_schema_field(EntityReferenceSerializer(allow_null=True))
    def get_variant_of(self, entity: Entity) -> dict[str, Any] | None:
        """Expose the reference figure only when this caller may read it."""
        roles, caller_id = caller_policy(self.context)
        if not is_privately_readable(
            entity.variant_of, roles=roles, caller_id=caller_id
        ):
            return None
        return EntityReferenceSerializer(entity.variant_of).data

    @extend_schema_field(EntityRelationSerializer(many=True))
    def get_relations(self, entity: Entity) -> list[dict[str, Any]]:
        """Expose the outgoing relations whose target this caller may read.

        The filtering is **repeated here**, as on the public serializer and
        for the same reason: no use of this class can publish a link to a
        target the caller is not entitled to see, whatever queryset it
        receives. A discarded link disappears entirely; its `to_name` is not
        filled with the hidden target's name.

        Genuinely unresolved links — `to_entity` is `null` — stay readable, as
        they already were on the public endpoint.
        """
        roles, caller_id = caller_policy(self.context)
        visible = [
            relation
            for relation in entity.relations_from.all()
            if relation.to_entity_id is None
            or is_privately_readable(
                relation.to_entity, roles=roles, caller_id=caller_id
            )
        ]
        return list(EntityRelationSerializer(visible, many=True).data)


# --- Private editorial creation ------------------------------------------

IDENTIFIER_REASON = "The identifier is generated by the server; it cannot be supplied."
STATUS_REASON = (
    "A new record is always created as a draft; the editorial status cannot be "
    "supplied. Submission, publication and rejection are separate actions."
)
OWNER_REASON = (
    "The owner is the authenticated account; it cannot be supplied, not even "
    "by an administrator."
)
REVIEW_REASON = (
    "Review marks are set by the review actions, which are not available yet."
)
DELETION_REASON = (
    "Deletion marks are set by the deletion action, which is not available yet."
)
TIMESTAMP_REASON = (
    "Technical timestamps are set by the server; they cannot be supplied."
)
NESTED_SOURCES_REASON = (
    "Creating documentary sources together with an entity is not available "
    "yet. Create the entity first; attaching sources comes with a later "
    "increment."
)
NESTED_RELATIONS_REASON = (
    "Creating relations together with an entity is not available yet. Create "
    "the entity first; attaching relations comes with a later increment."
)
PROFILE_ATTACHMENT_REASON = (
    "The profile is attached to the created entity automatically; it cannot "
    "name its entity."
)
UNKNOWN_ENTITY_FIELD_REASON = "Unknown input field for entity creation."
UNKNOWN_PROFILE_FIELD_REASON = "Unknown input field for this profile."

# DRF ignore les clés inconnues ; ces refus doivent au contraire être explicites.
REJECTED_ENTITY_FIELDS: dict[str, str] = {
    "id": IDENTIFIER_REASON,
    "pk": IDENTIFIER_REASON,
    "status": STATUS_REASON,
    "created_by": OWNER_REASON,
    "created_by_id": OWNER_REASON,
    "submitted_at": REVIEW_REASON,
    "reviewed_at": REVIEW_REASON,
    "reviewed_by": REVIEW_REASON,
    "review_notes": REVIEW_REASON,
    "deleted_at": DELETION_REASON,
    "deleted_by": DELETION_REASON,
    "created_at": TIMESTAMP_REASON,
    "updated_at": TIMESTAMP_REASON,
    "sources": NESTED_SOURCES_REASON,
    "relations": NESTED_RELATIONS_REASON,
    "relations_from": NESTED_RELATIONS_REASON,
    "relations_to": NESTED_RELATIONS_REASON,
}

REJECTED_PROFILE_FIELDS: dict[str, str] = {
    "entity": PROFILE_ATTACHMENT_REASON,
    "entity_id": PROFILE_ATTACHMENT_REASON,
    "id": IDENTIFIER_REASON,
    "pk": IDENTIFIER_REASON,
}

# Correspondance API de `services.PROFILE_MODELS`.
PROFILE_FIELD_BY_TYPE: dict[str, str] = {
    EntityType.DIVINITY: "divinity_profile",
    EntityType.HERO: "hero_profile",
    EntityType.CREATURE: "creature_profile",
}

PROFILE_FIELDS = tuple(PROFILE_FIELD_BY_TYPE.values())

ATTACHED_COLLECTIONS = (
    "secondary_countries",
    "secondary_ethnicities",
    "secondary_cultural_areas",
    "domains",
)

OVERLAPPING_ATTACHMENTS = (
    ("primary_country", "secondary_countries"),
    ("primary_ethnicity", "secondary_ethnicities"),
    ("primary_cultural_area", "secondary_cultural_areas"),
)


def attach_collections(
    entity: Entity, collections: Mapping[str, Sequence[Any]]
) -> None:
    """Attach validated M2M selections inside the caller's transaction."""
    for name, values in collections.items():
        getattr(entity, name).set(values)


def string_array_errors(
    data: Mapping[str, Any], fields: Mapping[str, Any]
) -> dict[str, list[str]]:
    """Reject non-string array items before DRF can coerce numbers to strings."""
    errors = {}
    for name, value in data.items():
        field = fields.get(name)
        if (
            isinstance(field, serializers.ListField)
            and isinstance(field.child, serializers.CharField)
            and isinstance(value, list)
            and any(not isinstance(item, str) for item in value)
        ):
            errors[name] = ["Expected a list of strings."]
    return errors


class CreatureProfileWriteSerializer(CreatureProfileSerializer):
    """Creature profile input with a single representation of an unset threat."""

    def validate_threat_level(self, value: str | None) -> str | None:
        """Normalise the empty string to `null`."""
        return value or None


class PrivateEntityCreateSerializer(serializers.ModelSerializer[Entity]):
    """Create a caller-owned draft with exactly its matching profile.

    An omitted or empty matching profile uses its defaults. References use
    existing identifiers; server-controlled fields and nested sources or
    relations are refused. Success returns the private detail representation.
    """

    # Profil absent ou vide accepté ; null refusé. Le type est vérifié dans validate().
    divinity_profile = DivinityProfileSerializer(required=False)
    hero_profile = HeroProfileSerializer(required=False)
    creature_profile = CreatureProfileWriteSerializer(required=False)

    # Résolution privée avec un refus identique pour une cible inconnue ou interdite.
    variant_of = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text=(
            "Identifier of the reference figure this entity is a cultural "
            "variant of. Only a figure readable by the calling account can be "
            "selected; anything else is refused identically, whether it is "
            "unreadable, deleted or unknown."
        ),
    )

    class Meta:
        model = Entity
        fields = [
            "name",
            "slug",
            "entity_type",
            "gender",
            "category",
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
            "divinity_profile",
            "hero_profile",
            "creature_profile",
        ]

    # --- Refus des clés d'entrée, avant toute conversion ----------------

    def to_internal_value(self, data: Any) -> Any:
        """Reject forbidden keys and non-string array items before conversion."""
        if isinstance(data, Mapping):
            self.reject_entity_keys(data)
            self.reject_profile_keys(data)
        return super().to_internal_value(data)

    def reject_entity_keys(self, data: Mapping[str, Any]) -> None:
        """Report every top-level key this operation does not accept."""
        errors = {
            name: [REJECTED_ENTITY_FIELDS.get(name, UNKNOWN_ENTITY_FIELD_REASON)]
            for name in data
            if name in REJECTED_ENTITY_FIELDS or name not in self.fields
        }
        errors.update(string_array_errors(data, self.fields))
        if errors:
            raise serializers.ValidationError(errors)

    def reject_profile_keys(self, data: Mapping[str, Any]) -> None:
        """Reject unknown profile keys and non-string array items."""
        errors: dict[str, dict[str, list[str]]] = {}
        for field_name in PROFILE_FIELDS:
            payload = data.get(field_name)
            if not isinstance(payload, Mapping):
                continue
            profile_fields = self.fields[field_name].fields  # type: ignore[attr-defined]
            accepted = set(profile_fields)
            refused = {
                key: [REJECTED_PROFILE_FIELDS.get(key, UNKNOWN_PROFILE_FIELD_REASON)]
                for key in payload
                if key in REJECTED_PROFILE_FIELDS or key not in accepted
            }
            refused.update(string_array_errors(payload, profile_fields))
            if refused:
                errors[field_name] = refused
        if errors:
            raise serializers.ValidationError(errors)

    # --- Validations de champ et de cohérence ---------------------------

    def validate_variant_of(self, value: uuid.UUID | None) -> Entity | None:
        """Resolve a privately readable reference without disclosing hidden targets."""
        if value is None:
            return None
        roles, caller_id = caller_policy(self.context)
        reference = (
            private_entities(roles=roles, caller_id=caller_id).filter(pk=value).first()
        )
        if reference is None:
            raise serializers.ValidationError(
                "No reference figure selectable by this account matches this "
                "identifier."
            )
        return reference

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Check the profile key against the type, then the attachments."""
        attrs = super().validate(attrs)
        self.reject_mismatched_profiles(attrs["entity_type"])
        self.reject_overlapping_attachments(attrs)
        return attrs

    def reject_mismatched_profiles(self, entity_type: str) -> None:
        """Accept only the profile key matching the requested type."""
        expected = PROFILE_FIELD_BY_TYPE[entity_type]
        errors = {
            name: [
                f"An entity of type '{entity_type}' carries its profile under "
                f"'{expected}'; this key is not accepted."
            ]
            for name in PROFILE_FIELDS
            if name != expected and name in self.initial_data
        }
        if errors:
            raise serializers.ValidationError(errors)

    def reject_overlapping_attachments(self, attrs: Mapping[str, Any]) -> None:
        """Keep primary and secondary attachments disjoint, per ADR 0002."""
        errors = {}
        for primary, secondary in OVERLAPPING_ATTACHMENTS:
            anchor = attrs.get(primary)
            if anchor is not None and anchor in attrs.get(secondary, []):
                errors[secondary] = [
                    f"'{anchor}' is already this entity's {primary}; a value "
                    f"cannot be both a primary anchor and a secondary "
                    f"attachment."
                ]
        if errors:
            raise serializers.ValidationError(errors)

    # --- Écriture -------------------------------------------------------

    def create(self, validated_data: dict[str, Any]) -> Entity:
        """Create the entity, its matching profile and its attachments atomically."""
        profile_data: dict[str, Any] = {}
        for name in PROFILE_FIELDS:
            payload = validated_data.pop(name, None)
            if payload is not None:
                profile_data = payload

        collections = {
            name: validated_data.pop(name)
            for name in ATTACHED_COLLECTIONS
            if name in validated_data
        }

        try:
            with transaction.atomic():
                entity = create_entity_with_profile(
                    entity_data={
                        **validated_data,
                        "created_by": self.caller_account(),
                        "status": EntityStatus.DRAFT,
                    },
                    profile_data=profile_data,
                )
                attach_collections(entity, collections)
        except DjangoValidationError as error:
            # Seule `ValidationError` est convertie. Une autre exception reste
            # une erreur serveur visible, et non un 400 trompeur.
            raise serializers.ValidationError(
                serializers.as_serializer_error(error)
            ) from error
        return entity

    def caller_account(self) -> User:
        """Return the account this record belongs to, read from the request."""
        user = self.context["request"].user
        # Les permissions garantissent un compte réel ; aucun repli sans propriétaire.
        assert isinstance(user, User)
        return user

    def to_representation(self, instance: Entity) -> Any:
        """Reload the readable record with prefetching and return private detail."""
        roles, caller_id = caller_policy(self.context)
        loaded = private_entity_detail(roles=roles, caller_id=caller_id).get(
            pk=instance.pk
        )
        return PrivateEntityDetailSerializer(loaded, context=self.context).data
