"""OpenAPI annotations for the public and private entity endpoints.

Kept in its own module so the long public descriptions and examples do not
crowd out the view logic. It holds no behaviour: only the parameter
declarations, response descriptions and examples that drf-spectacular cannot
infer by introspection.

Every string here is public — it is rendered in the schema, in Swagger UI and
in ReDoc — and is therefore written in English, per ADR 0003.

The example payloads are **synthetic**. They are written by hand to match the
serializers, are never read from a database, and must not be taken for
validated mythological facts.
"""

from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse
from rest_framework import serializers

from mythology.models import EntityType

# --- Query parameters ---------------------------------------------------
#
# Ces cinq paramètres sont documentés explicitement :
# `entity_type`, `country` et `cultural_area` sont appliqués à la main dans
# `get_queryset()`, et `page` comme `search` méritent une description plus
# précise que celle déduite automatiquement. Ils sont déclarés ici une seule
# fois, et n'apparaissent que sur la liste.

PAGE_PARAMETER = OpenApiParameter(
    name="page",
    type=int,
    location=OpenApiParameter.QUERY,
    required=False,
    description=(
        "Page number within the paginated collection. The page size is fixed "
        "at 20 and cannot be changed by the client. A non-existent or "
        "malformed page returns `404`."
    ),
    examples=[OpenApiExample("Second page", value=2)],
)

SEARCH_PARAMETER = OpenApiParameter(
    name="search",
    type=str,
    location=OpenApiParameter.QUERY,
    required=False,
    description=(
        "Case-insensitive search across `name`, `category`, `cultural_role` "
        "and `story_description`. Internal review notes, documentary sources "
        "and related entities are **not** searched: a search is never an "
        "indirect path to data the API does not expose. An empty value does "
        "not filter."
    ),
    examples=[OpenApiExample("By name", value="anansi")],
)

ENTITY_TYPE_PARAMETER = OpenApiParameter(
    name="entity_type",
    type=str,
    location=OpenApiParameter.QUERY,
    required=False,
    enum=list(EntityType.values),
    description=(
        "Exact entity type. An empty value does not filter; an unknown value "
        "returns `400`."
    ),
    examples=[OpenApiExample("Divinities only", value="divinity")],
)

COUNTRY_PARAMETER = OpenApiParameter(
    name="country",
    type=str,
    location=OpenApiParameter.QUERY,
    required=False,
    description=(
        "Two-letter ISO 3166-1 alpha-2 country code, normalised to upper "
        "case, so `ng` and `NG` are equivalent. Matches the **primary or a "
        "secondary** country of the entity; an entity matching through both "
        "appears only once and is counted once.\n\n"
        "A malformed code returns `400`. A well-formed but unknown code "
        "returns an empty collection rather than an error, so the response "
        "does not reveal which countries are recorded."
    ),
    examples=[OpenApiExample("Nigeria", value="NG")],
)

CULTURAL_AREA_PARAMETER = OpenApiParameter(
    name="cultural_area",
    type=str,
    location=OpenApiParameter.QUERY,
    required=False,
    description=(
        "Cultural area slug. Matches a **primary or secondary** attachment to "
        "that area **or to any of its descendants**, following the hierarchy "
        "actually stored in the data: `central-africa` therefore also "
        "returns entities attached to `congo-basin`, at any depth. An entity "
        "matching through several attachments appears only once.\n\n"
        "Filtering by area never infers a country. An unknown slug returns an "
        "empty collection rather than an error."
    ),
    examples=[OpenApiExample("Central Africa and below", value="central-africa")],
)

LIST_PARAMETERS = [
    PAGE_PARAMETER,
    SEARCH_PARAMETER,
    ENTITY_TYPE_PARAMETER,
    COUNTRY_PARAMETER,
    CULTURAL_AREA_PARAMETER,
]


# --- Error responses ----------------------------------------------------


class ErrorDetailSerializer(serializers.Serializer[None]):
    """Standard DRF error body carrying a single `detail` message."""

    detail = serializers.CharField(help_text="Human-readable error message.")


class ParameterErrorSerializer(serializers.Serializer[None]):
    """Validation error body: one key per rejected query parameter."""

    entity_type = serializers.ListField(child=serializers.CharField(), required=False)
    country = serializers.ListField(child=serializers.CharField(), required=False)


class CreationErrorSerializer(serializers.Serializer[None]):
    """Validation error body: one key per rejected input field.

    The keys depend on the request, so only the most common ones are declared
    here. Any accepted or refused field of the creation payload can appear,
    with a list of messages; a profile key carries an object of messages
    instead, keyed by the profile field at fault.
    """

    name = serializers.ListField(child=serializers.CharField(), required=False)
    slug = serializers.ListField(child=serializers.CharField(), required=False)
    entity_type = serializers.ListField(child=serializers.CharField(), required=False)
    gender = serializers.ListField(child=serializers.CharField(), required=False)
    variant_of = serializers.ListField(child=serializers.CharField(), required=False)
    status = serializers.ListField(child=serializers.CharField(), required=False)
    non_field_errors = serializers.ListField(
        child=serializers.CharField(), required=False
    )


# --- Examples -----------------------------------------------------------
#
# Chaque exemple est synthétique et étiqueté comme tel, afin qu'il ne soit
# pas confondu avec une fiche réelle du corpus.

# L'exemple de liste donne **un seul élément** de `results` : la pagination
# fournit elle-même l'enveloppe `count` / `next` / `previous`, et y insère
# l'exemple. Fournir une liste produirait `results: [[…]]`, imbriqué deux
# fois.
LIST_EXAMPLE = OpenApiExample(
    "Collection item (synthetic)",
    description=(
        "One synthetic figure. Invented data, shown to illustrate the shape "
        "of each item inside `results`. The surrounding `count`, `next` and "
        "`previous` values are generic placeholders supplied by the "
        "pagination schema, not part of this example."
    ),
    response_only=True,
    value={
        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "slug": "example-hero",
        "name": "Example Hero",
        "entity_type": "hero",
        "category": "Synthetic subtitle",
    },
)

DETAIL_EXAMPLE = OpenApiExample(
    "Entity with a divinity profile (synthetic)",
    description=(
        "Invented figure, shown to illustrate the response shape. Note that "
        "the two non-matching profile keys are present and `null`, that the "
        "relation to a figure without a record keeps its `to_name`, and that "
        "`variant_of` is `null` here."
    ),
    response_only=True,
    value={
        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "slug": "example-divinity",
        "name": "Example Divinity",
        "entity_type": "divinity",
        "category": "Synthetic subtitle",
        "gender": "female",
        "cultural_role": "Synthetic role",
        "alignment": "Lawful Neutral",
        "story_description": "Synthetic narrative, written for documentation.",
        "characteristics": ["Synthetic trait"],
        "physical_signs": ["Synthetic sign"],
        "symbols": ["Synthetic symbol"],
        "power_objects": [],
        "symbolic_animals": ["Synthetic animal"],
        "manifestations": "Synthetic manifestation.",
        "primary_country": {
            "id": 1,
            "slug": "example-country",
            "name": "Example Country",
            "iso_code": "XX",
        },
        "secondary_countries": [],
        "primary_ethnicity": {
            "id": 1,
            "slug": "example-ethnicity",
            "name": "Example Ethnicity",
        },
        "secondary_ethnicities": [],
        "primary_cultural_area": {
            "id": 1,
            "slug": "example-area",
            "name": "Example Area",
            "kind": "african_region",
        },
        "secondary_cultural_areas": [],
        "domains": [{"id": 1, "slug": "example-domain", "name": "Example Domain"}],
        "variant_of": None,
        "relations": [
            {
                "id": 1,
                "kind": "consort",
                "to_entity": {
                    "id": "9c858901-8a57-4791-81fe-4c455b099bc9",
                    "slug": "example-hero",
                    "name": "Example Hero",
                    "entity_type": "hero",
                },
                "to_name": "",
                "notes": "",
            },
            {
                "id": 2,
                "kind": "parent",
                "to_entity": None,
                "to_name": "Figure Without A Record",
                "notes": "",
            },
        ],
        "sources": [
            {
                "id": 1,
                "label": "Synthetic Reference Work",
                "kind": "book",
                "url": "",
                "accessed_at": None,
                "notes": "Invented reference, for documentation only.",
            }
        ],
        "created_at": "2026-10-21T09:00:00Z",
        "updated_at": "2026-10-21T09:00:00Z",
        "divinity_profile": {
            "cult_offerings": ["Synthetic offering"],
            "cult_taboos": [],
            "cult_rituals": [],
            "cult_places": [],
            "cult_festivals": [],
        },
        "hero_profile": None,
        "creature_profile": None,
    },
)


# --- Response declarations ----------------------------------------------

INVALID_PARAMETER_RESPONSE = OpenApiResponse(
    response=ParameterErrorSerializer,
    description="A query parameter was malformed.",
    examples=[
        OpenApiExample(
            "Unknown entity type",
            response_only=True,
            value={
                "entity_type": [
                    "Unknown entity type 'titan'. Expected one of: divinity, "
                    "hero, creature."
                ]
            },
        ),
        OpenApiExample(
            "Malformed country code",
            response_only=True,
            value={
                "country": [
                    "Invalid country code 'NGA'. Expected a two-letter ISO "
                    "3166-1 alpha-2 code, for example 'NG'."
                ]
            },
        ),
    ],
)

PAGE_NOT_FOUND_RESPONSE = OpenApiResponse(
    response=ErrorDetailSerializer,
    description="The requested page does not exist.",
    examples=[
        OpenApiExample(
            "Invalid page",
            response_only=True,
            value={"detail": "Invalid page."},
        )
    ],
)

ENTITY_NOT_FOUND_RESPONSE = OpenApiResponse(
    response=ErrorDetailSerializer,
    description=(
        "No publicly visible entity matches this slug. The same response is "
        "returned whether the slug does not exist at all or refers to an "
        "entity that is not published or has been deleted: the body never "
        "reveals which."
    ),
    examples=[
        OpenApiExample(
            "Unknown or non-public slug",
            response_only=True,
            value={"detail": "No Entity matches the given query."},
        )
    ],
)

LIST_DESCRIPTION = (
    "Returns the paginated collection of publicly visible entities.\n\n"
    "Only entities whose editorial status is `published` and that have not "
    "been logically deleted are listed, for every caller. `count` reflects "
    "that same restriction combined with the active search and filters, so "
    "it never discloses hidden records.\n\n"
    "**Pagination.** Fixed size of 20 items. `next` and `previous` preserve "
    "every search and filter parameter. Results are ordered by `name`, then "
    "by `id` to break ties between identically named figures — without that "
    "tiebreaker a record could move between pages from one request to the "
    "next.\n\n"
    "**Combining parameters.** The filters combine with AND; within a single "
    "filter, the primary and secondary attachments combine with OR. An entity "
    "matching through several attachments is returned, and counted, only "
    "once.\n\n"
    "Each item carries the five compact fields below. Profiles, reference "
    "data, relations and sources are only available on the detail endpoint.\n\n"
    "**Empty collection.** A database holding only unpublished drafts, an "
    "unknown country code and an unknown area slug all return the same "
    "well-formed empty envelope. This is the expected behaviour, not an "
    "error:\n\n"
    "```json\n"
    '{"count": 0, "next": null, "previous": null, "results": []}\n'
    "```\n\n"
    "Write methods are refused with `405 Method Not Allowed`."
)

DETAIL_DESCRIPTION = (
    "Returns one publicly visible entity, addressed by its `slug`.\n\n"
    "The three profile keys are **always present**: the one matching "
    "`entity_type` carries the object, the other two are `null`. A stable set "
    "of keys spares the client from testing for a key's presence in addition "
    "to its value.\n\n"
    "**Nested visibility.** `variant_of` is `null` when the reference figure "
    "is not publicly visible, revealing neither its id, slug, name nor type. "
    "A relation whose resolved target is not publicly visible is omitted "
    "entirely, and the hidden target's name is never copied into `to_name`. "
    "Targets are rendered as a four-field reference only — the detail is "
    "never nested recursively.\n\n"
    "These rules cover structured references. They do not censor names "
    "appearing in the narrative text, nor in a genuinely unresolved relation: "
    "reviewing the text itself is editorial work.\n\n"
    "The collection's query parameters do not apply here: availability "
    "depends solely on the public visibility of the requested slug.\n\n"
    "Write methods are refused with `405 Method Not Allowed`."
)


# --- Private editorial endpoints ----------------------------------------
#
# Les textes ci-dessous décrivent les deux routes sous `/api/manage/`. Ils
# sont publics comme le reste du schéma : le contrat d'une route protégée est
# documenté, seules ses données le sont pas.

PRIVATE_UNAUTHENTICATED_RESPONSE = OpenApiResponse(
    response=ErrorDetailSerializer,
    description=(
        "No usable access token was provided. These endpoints accept JWT "
        "only: an open administration session is deliberately not enough. "
        "HTTP 401 is returned when the token is missing, malformed, "
        "expired, signed with another key, a refresh token sent in place of "
        "an access token, or issued for an account that has since been "
        "deactivated or deleted. The error body depends on the cause."
    ),
    examples=[
        OpenApiExample(
            "MissingToken",
            response_only=True,
            value={"detail": "Authentication credentials were not provided."},
        )
    ],
)

PRIVATE_FORBIDDEN_RESPONSE = OpenApiResponse(
    response=ErrorDetailSerializer,
    description=(
        "The token is valid but its account holds no editorial role. "
        "Membership of the `contributor`, `reviewer` or `administrator` group "
        "is required, and is granted by an administrator. Being a member of "
        "the Django staff grants nothing here.\n\n"
        "This is returned for every request from such an account, including "
        "one asking for a published record: reading published content is what "
        "the public endpoints are for."
    ),
    examples=[
        OpenApiExample(
            "NoEditorialRole",
            response_only=True,
            value={
                "detail": (
                    "This account holds no editorial role. Private editorial "
                    "access requires membership of the contributor, reviewer "
                    "or administrator group, granted by an administrator."
                )
            },
        )
    ],
)

PRIVATE_NOT_FOUND_RESPONSE = OpenApiResponse(
    response=ErrorDetailSerializer,
    description=(
        "No entity readable by this account matches this slug. The same "
        "response is returned whether the slug does not exist at all, refers "
        "to a record this account may not read, or refers to a deleted "
        "record: the body never reveals which, nor the record's editorial "
        "status."
    ),
    examples=[
        OpenApiExample(
            "UnknownOrUnreadableSlug",
            response_only=True,
            value={"detail": "No Entity matches the given query."},
        )
    ],
)

PRIVATE_LIST_DESCRIPTION = (
    "Returns the paginated collection of entities this account may read for "
    "editorial work. Requires an access token in the `Authorization` header "
    "and an editorial role.\n\n"
    "**What each role reads.** A contributor reads every published record, "
    "plus its own records in `draft`, `submitted` or `rejected`. A reviewer, "
    "an administrator and a superuser read every record that has not been "
    "deleted. Logically deleted records are excluded for everyone; "
    "restoration is a separate, later operation.\n\n"
    "An imported record with no owner (`created_by` is `null`) belongs to no "
    "contributor, and is therefore invisible to contributors while it is "
    "unpublished. Reviewers and administrators still read it.\n\n"
    "**Roles come from the database.** They are read from Django group "
    "membership on every request, not from a claim inside the token. Adding "
    "or removing a group therefore takes effect on the next request, with the "
    "same token.\n\n"
    "**Added fields.** Each item carries the five public compact fields, plus "
    "`status` and `created_by`. The public collection gains neither.\n\n"
    "**Navigation.** Identical to the public collection: fixed page size of "
    "20, the same `page`, `search`, `entity_type`, `country` and "
    "`cultural_area` parameters, with the same validation and the same "
    "ordering. `count` only ever counts records this account may read, and no "
    "parameter can widen that selection.\n\n"
    "`POST` on this collection creates a draft entity; see that operation. "
    "`PUT`, `PATCH` and `DELETE` are refused with `405 Method Not Allowed`, "
    "for every role."
)

PRIVATE_DETAIL_DESCRIPTION = (
    "Returns one entity readable by this account, addressed by its `slug`. "
    "Requires an access token and an editorial role.\n\n"
    "The selection rule is the one described on the private collection. A "
    "record this account may not read and an unknown slug return the same "
    "`404`: the response never reveals that a record exists, nor its "
    "editorial status.\n\n"
    "**Added fields.** Every business field of the public detail, plus "
    "`status`, `created_by`, `submitted_at`, `reviewed_at`, `reviewed_by` and "
    "`review_notes`. The owner and reviewer appear as identifiers only — no "
    "account is serialised here.\n\n"
    "**Nested references follow the caller's own rule.** `variant_of` is "
    "`null` when the reference figure is not readable by this account, "
    "revealing neither its id, slug, name nor type. A relation whose resolved "
    "target is not readable is omitted entirely, and the hidden target's name "
    "is never copied into `to_name`. Deleted records stay hidden in these "
    "references too. Genuinely unresolved relations stay readable. Targets "
    "are rendered as a four-field reference only — the detail is never nested "
    "recursively.\n\n"
    "A reviewer and a contributor can therefore receive different nested "
    "references for the same record, which is the intended behaviour.\n\n"
    "The collection's query parameters do not apply here, and cannot change "
    "which records this account may read.\n\n"
    "`PATCH` updates this record; see that operation. Its documentary sources "
    "and relations are written one by one under `sources/` and `relations/`, "
    "and it is submitted, withdrawn or resumed by a `POST` on `submit/`, "
    "`withdraw/` or `resume/`. `PUT` and `DELETE` are refused with "
    "`405 Method Not Allowed`, for every role, and creation is a `POST` on the "
    "collection. Publication, rejection, reopening and the deletion of an "
    "entity are not available yet."
)

PRIVATE_LIST_EXAMPLE = OpenApiExample(
    "Collection item (synthetic)",
    description=(
        "One synthetic figure. Invented data, shown to illustrate the shape "
        "of each item inside `results`. The surrounding `count`, `next` and "
        "`previous` values are generic placeholders supplied by the "
        "pagination schema, not part of this example."
    ),
    response_only=True,
    value={
        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "slug": "example-hero",
        "name": "Example Hero",
        "entity_type": "hero",
        "category": "Synthetic subtitle",
        "status": "draft",
        "created_by": 1,
    },
)

PRIVATE_DETAIL_EXAMPLE = OpenApiExample(
    "Submitted entity awaiting review (synthetic)",
    description=(
        "Invented figure, shown to illustrate the response shape. Note the "
        "editorial fields added by this endpoint, the owner and reviewer "
        "given as identifiers, and `reviewed_by` left `null` because the "
        "record has not been reviewed yet."
    ),
    response_only=True,
    value={
        **DETAIL_EXAMPLE.value,
        "status": "submitted",
        "created_by": 1,
        "submitted_at": "2026-10-22T08:30:00Z",
        "reviewed_at": None,
        "reviewed_by": None,
        "review_notes": "",
    },
)


# --- Private editorial creation -----------------------------------------

PRIVATE_CREATE_DESCRIPTION = (
    "Creates one entity and the profile of its type, as a draft owned by the "
    "calling account. Requires an access token and an editorial role: a "
    "contributor, a reviewer, an administrator and an active superuser may all "
    "create.\n\n"
    "**The server decides four things.** `created_by` is the authenticated "
    "account, `status` is `draft`, the `id` is generated, and `created_at` and "
    "`updated_at` are set by the server. None of them can be supplied — not "
    "even by an administrator — and neither can the review or deletion marks. "
    "Sending one of these keys returns `400`; it is never silently dropped.\n\n"
    "**Required fields.** `name`, `slug`, `entity_type` and `gender`. The slug "
    "is taken as given: it is never generated or suffixed to resolve a "
    "collision. A name already used by another entity of the same type, or an "
    "already used slug, returns `400`.\n\n"
    "**The profile follows the type.** Put it under the matching key — "
    "`divinity_profile` for `divinity`, `hero_profile` for `hero`, "
    "`creature_profile` for `creature`. The key may be omitted or sent as "
    "`{}`, in which case the profile is created with its default values; an "
    "entity never exists without the profile of its type. The two other keys "
    "are refused, as is a profile sent as `null`, and a profile cannot name "
    "its own entity or identifier.\n\n"
    "**Reference data is attached by identifier**, under the field names the "
    "detail representation already uses: `primary_country`, "
    "`secondary_countries`, `primary_ethnicity`, `secondary_ethnicities`, "
    "`primary_cultural_area`, `secondary_cultural_areas` and `domains`. "
    "Primary anchors are optional and may be `null`; the collections are "
    "optional and default to empty. Reference records are never created here, "
    "and the same value cannot be both a primary anchor and a secondary "
    "attachment of the same dimension.\n\n"
    "**`variant_of`** takes the UUID of a figure the calling account may read "
    "privately. An unreadable record, a deleted record and an unknown "
    "identifier are all refused with the same message, which never confirms "
    "that a record exists.\n\n"
    "**Children are written separately.** `sources` and `relations` cannot be "
    "created together with an entity; sending either returns `400` pointing at "
    "the dedicated routes, rather than ignoring it. Any other unrecognised key "
    "is refused too, so a misspelt field name cannot pass unnoticed.\n\n"
    "**All or nothing.** The entity, its profile and its attachments are "
    "written in a single transaction. An invalid request returns `400` and "
    "creates nothing — never an entity without its profile, nor a record with "
    "half of its attachments.\n\n"
    "**Response.** `201` with the private detail representation of the new "
    "record. It is readable at once on the private endpoints by its owner, and "
    "absent from the public API until it is published."
)

PRIVATE_CREATE_REQUEST_EXAMPLE = OpenApiExample(
    "Hero draft with its profile (synthetic)",
    description=(
        "Invented figure, shown to illustrate the request shape. The numeric "
        "values are reference identifiers that have to exist in the database. "
        "No owner, status, identifier or date appears: the server decides them."
    ),
    request_only=True,
    value={
        "name": "Example Created Hero",
        "slug": "example-created-hero",
        "entity_type": "hero",
        "gender": "female",
        "category": "Synthetic subtitle",
        "story_description": "Synthetic narrative, written for documentation.",
        "characteristics": ["Synthetic trait"],
        "primary_country": 1,
        "secondary_countries": [],
        "domains": [1],
        "variant_of": None,
        "hero_profile": {
            "titles": ["Synthetic title"],
            "quests": [],
        },
    },
)

PRIVATE_CREATE_RESPONSE_EXAMPLE = OpenApiExample(
    "Created draft (synthetic)",
    description=(
        "The private detail representation of the record just created. Note "
        "`status` forced to `draft`, `created_by` set to the calling account, "
        "the hero profile created with its default values for the fields the "
        "request omitted, and the two other profile keys left `null`."
    ),
    response_only=True,
    status_codes=["201"],
    value={
        **PRIVATE_DETAIL_EXAMPLE.value,
        "id": "b3f1c0de-0c3a-4a7f-9f1a-5f0b2d6c7e81",
        "slug": "example-created-hero",
        "name": "Example Created Hero",
        "entity_type": "hero",
        "gender": "female",
        "status": "draft",
        "created_by": 1,
        "submitted_at": None,
        "reviewed_at": None,
        "reviewed_by": None,
        "review_notes": "",
        "variant_of": None,
        "relations": [],
        "sources": [],
        "created_at": "2026-10-27T09:00:00Z",
        "updated_at": "2026-10-27T09:00:00Z",
        "divinity_profile": None,
        "hero_profile": {
            "titles": ["Synthetic title"],
            "achievements": [],
            "quests": [],
            "weapons_or_artifacts": [],
            "legacy": "",
            "historical_context": "",
        },
        "creature_profile": None,
    },
)

PRIVATE_CREATE_INVALID_RESPONSE = OpenApiResponse(
    response=CreationErrorSerializer,
    description=(
        "The request was refused and **nothing was created**. One key per "
        "field at fault, each carrying its messages. A refused key is always "
        "named: a server-controlled field, a deferred nested collection, a "
        "profile that does not match the type and an unrecognised field name "
        "are reported, never ignored."
    ),
    examples=[
        OpenApiExample(
            "ServerControlledField",
            response_only=True,
            value={
                "status": [
                    "A new record is always created as a draft; the editorial "
                    "status cannot be supplied. Submission, publication and "
                    "rejection are separate actions."
                ]
            },
        ),
        OpenApiExample(
            "ProfileDoesNotMatchTheType",
            response_only=True,
            value={
                "divinity_profile": [
                    "An entity of type 'hero' carries its profile under "
                    "'hero_profile'; this key is not accepted."
                ]
            },
        ),
        OpenApiExample(
            "UnselectableVariant",
            response_only=True,
            value={
                "variant_of": [
                    "No reference figure selectable by this account matches "
                    "this identifier."
                ]
            },
        ),
        OpenApiExample(
            "ChildWrittenOnItsOwnRoute",
            response_only=True,
            value={
                "sources": [
                    "Documentary sources are not created together with an "
                    "entity. Create the entity first, then post each source "
                    "to `/api/manage/entities/{slug}/sources/`."
                ]
            },
        ),
    ],
)


# --- Private editorial update -------------------------------------------

PRIVATE_UPDATE_DESCRIPTION = (
    "Updates the business fields, the existing profile and the reference "
    "attachments of one record. Requires an access token and an editorial "
    "role.\n\n"
    "**Who may update what.** A contributor updates its own `draft` and "
    "`rejected` records. A reviewer updates any `draft`, `rejected` or "
    "`submitted` record. An administrator and an active superuser update every "
    "record that has not been deleted. Reading a record does not imply "
    "updating it: a record this account may read but not modify returns "
    "`403`, while an unknown slug, an unreadable record and a deleted record "
    "all return the same `404`.\n\n"
    "**Partial by nature.** An omitted field keeps its value. A supplied list "
    "replaces that list entirely, and `[]` empties it; `null` is accepted only "
    "on fields that are nullable. Omitted collections are left intact.\n\n"
    "**The entity type cannot change.** Supplying `entity_type` returns `400`: "
    "moving a figure to another type means creating the profile of the new "
    "type and deciding what becomes of the previous one, which a reclassifying "
    "operation will handle deliberately. The identifier never changes; the "
    "`slug` may, and keeps its uniqueness.\n\n"
    "**The profile is patched under the key of the current type.** Only the "
    "supplied profile fields change; an omitted or empty profile erases "
    "nothing. A profile sent as `null`, a profile key of another type, and a "
    "profile naming an entity or an identifier are refused. A record that does "
    "not already carry exactly the profile of its type is refused with `400` "
    "and left untouched: an ordinary update does not repair that inconsistency "
    "silently.\n\n"
    "**The server still decides the rest.** The owner, the editorial status, "
    "the identifier, the technical timestamps and the review or deletion marks "
    "cannot be supplied — no ownership transfer, not even for an "
    "administrator. Documentary sources and relations are not written here "
    "either: each one has its own route under this record. Any unrecognised "
    "key is refused too.\n\n"
    "**Attachments use existing identifiers**, and no reference record is ever "
    "created. The rule keeping a primary anchor distinct from the secondary "
    "attachments of the same dimension is checked on the **final state**, "
    "combining the stored values with this request. `variant_of` still accepts "
    "only a figure readable by this account, refuses a self-reference, and "
    "reports an unreadable, deleted or unknown target identically.\n\n"
    "**All or nothing.** The record, its profile and its attachments are "
    "written in a single transaction, and the update right is re-evaluated on "
    "the locked row, so a concurrent status change cannot be overwritten. A "
    "refused request changes nothing at all.\n\n"
    "**Response.** `200` with the private detail representation of the updated "
    "record."
)

PRIVATE_UPDATE_REQUEST_EXAMPLE = OpenApiExample(
    "Partial update of a hero (synthetic)",
    description=(
        "Invented values, shown to illustrate the request shape. Only the keys "
        "present are changed: the other business fields, the other profile "
        "fields and the omitted collections keep their stored values. No "
        "`entity_type`, owner, status or date appears — none of them can be "
        "supplied."
    ),
    request_only=True,
    value={
        "category": "Revised synthetic subtitle",
        "characteristics": ["Revised synthetic trait"],
        "domains": [1, 2],
        "hero_profile": {"titles": ["Revised synthetic title"]},
    },
)

PRIVATE_NOT_EDITABLE_RESPONSE = OpenApiResponse(
    response=ErrorDetailSerializer,
    description=(
        "Either the token is valid but its account holds no editorial role, or "
        "the account may read this record and not modify it — a contributor "
        "facing a published record, or a record owned by someone else, for "
        "instance. The body distinguishes the two cases."
    ),
    examples=[
        OpenApiExample(
            "RecordNotEditableByThisAccount",
            response_only=True,
            value={
                "detail": (
                    "This account may read this record but not modify it. A "
                    "contributor modifies its own draft and rejected records; "
                    "a reviewer also modifies submitted records; every other "
                    "case requires an administrator."
                )
            },
        )
    ],
)

PRIVATE_UPDATE_INVALID_RESPONSE = OpenApiResponse(
    response=CreationErrorSerializer,
    description=(
        "The request was refused and **nothing was changed**. One key per "
        "field at fault, each carrying its messages. A refused key is always "
        "named, never ignored."
    ),
    examples=[
        OpenApiExample(
            "EntityTypeCannotChange",
            response_only=True,
            value={
                "entity_type": [
                    "The entity type cannot be changed by an ordinary update: "
                    "the profile of the new type would have to be created and "
                    "the previous one disposed of. A deliberate "
                    "reclassification operation is required (ADR 0005)."
                ]
            },
        ),
        OpenApiExample(
            "StatusIsNotUpdatedHere",
            response_only=True,
            value={
                "status": [
                    "The editorial status is changed by the submission, review "
                    "and reopening actions, not by an ordinary update."
                ]
            },
        ),
        OpenApiExample(
            "OverlappingAttachmentInTheFinalState",
            response_only=True,
            value={
                "secondary_countries": [
                    "'Example Country' is already this entity's "
                    "primary_country; a value cannot be both a primary anchor "
                    "and a secondary attachment."
                ]
            },
        ),
        OpenApiExample(
            "SelfReference",
            response_only=True,
            value={"variant_of": ["An entity cannot be a variant of itself."]},
        ),
    ],
)


# --- Private editorial writes on a record's children --------------------
#
# Six opérations, deux enfants, un seul contrat de sécurité : celui de la
# fiche porteuse. Les textes communs sont donc assemblés une fois.

CHILD_RIGHTS = (
    "Requires an access token and an editorial role, and the right to "
    "**update the record named by the slug**: a contributor writes on its own "
    "`draft` and `rejected` records, a reviewer on any `draft`, `rejected` or "
    "`submitted` record, an administrator on every record that has not been "
    "deleted. A record this account may read but not update returns `403`; an "
    "unknown slug, an unreadable record and a deleted record all return the "
    "same `404`.\n\n"
    "The record itself is never touched: its status, owner, type, profile, "
    "review marks and `updated_at` are left exactly as they were.\n\n"
)

CHILD_LOOKUP = (
    "The row is looked up **inside that record**, never by its identifier "
    "alone: an identifier that does not exist, or belongs to another record, "
    "returns the same `404`. Nothing is ever moved from one record to "
    "another.\n\n"
)

SOURCE_ID_PARAMETER = OpenApiParameter(
    name="source_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
    description=(
        "Identifier of the documentary source, as returned in the `sources` "
        "array of the private detail."
    ),
)

RELATION_ID_PARAMETER = OpenApiParameter(
    name="relation_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
    description=(
        "Identifier of the relation, as returned in the `relations` array of "
        "the private detail."
    ),
)

SOURCE_CREATE_DESCRIPTION = (
    "Adds one documentary source to the record named by the slug.\n\n"
    + CHILD_RIGHTS
    + "**Input.** `label` and `kind` are required; `url`, `accessed_at` and "
    "`notes` are optional. `url` may be an empty string — a book or an oral "
    "testimony has none — and is only checked for format, never fetched. "
    "`accessed_at` is a consultation date, not a publication date. The "
    "identifier and the owning record cannot be supplied, and any "
    "unrecognised key is refused.\n\n"
    "**No uniqueness is enforced.** Two sources carrying the same label or "
    "URL are legitimate on the same record; discarding duplicates is "
    "editorial work, not a structural rule.\n\n"
    "**Response.** `201` with the created source. Read them back in the "
    "`sources` array of the private detail: there is no separate list route."
)

SOURCE_UPDATE_DESCRIPTION = (
    "Updates one documentary source of the record named by the slug.\n\n"
    + CHILD_RIGHTS
    + CHILD_LOOKUP
    + "**Partial by nature.** An omitted key keeps its value. `accessed_at` is "
    "the only key that accepts `null`; `url` and `notes` accept an empty "
    "string, `label` and `kind` do not. The identifier and the owning record "
    "cannot be supplied, and any unrecognised key is refused.\n\n"
    "**Response.** `200` with the updated source. A refused request returns "
    "`400` and changes nothing."
)

SOURCE_DELETE_DESCRIPTION = (
    "Deletes one documentary source of the record named by the slug.\n\n"
    + CHILD_RIGHTS
    + CHILD_LOOKUP
    + "Only that source row is removed. The record, its profile and every "
    "other source are untouched, and no entity is ever deleted here. The "
    "removal is immediate and final: there is no recycle bin for a source and "
    "no history of the deletion.\n\n"
    "**Response.** `204` with no body."
)

RELATION_CREATE_DESCRIPTION = (
    "Adds one outgoing relation to the record named by the slug.\n\n"
    + CHILD_RIGHTS
    + "**Input.** `kind` is required, together with **exactly one** target: "
    "`to_entity`, the UUID of a figure this account may read, or `to_name`, a "
    "non-blank name for a figure that has no record. Supplying both or "
    "neither returns `400`. `notes` is optional.\n\n"
    "**Reading the target is enough** to link to it; updating it is not "
    "required. An unreadable, deleted or unknown UUID is refused with the "
    "same message, which never confirms that a record exists, and never "
    "discloses its name, identifier or editorial status. A relation from a "
    "record to itself is refused.\n\n"
    "**Direction.** `kind` qualifies the target, read from this record: "
    "`parent` means that the target is a parent of this entity. No inverse or "
    "reciprocal relation is created, and no cycle is detected. A name is "
    "never resolved to a record automatically.\n\n"
    "**Uniqueness.** The same triple — this record, this target, this kind — "
    "cannot be recorded twice, whether the target is resolved or cited by "
    "name. A pair of figures may still carry several kinds of relation.\n\n"
    "**Response.** `201` with the created relation. Read them back in the "
    "`relations` array of the private detail: there is no separate list route."
)

RELATION_UPDATE_DESCRIPTION = (
    "Updates one outgoing relation of the record named by the slug.\n\n"
    + CHILD_RIGHTS
    + CHILD_LOOKUP
    + "A relation whose resolved target is not readable by this account stays "
    "unreachable here too, with the same `404`, even when its identifier is "
    "guessed.\n\n"
    "**Partial by nature, with one rule on the final state.** An omitted key "
    "keeps its value, and neither target form is cleared implicitly. Whatever "
    "the request, the row left behind must still carry exactly one target. "
    "Resolving a cited name therefore means sending both keys in one "
    "request — `to_entity` with the UUID and `to_name` as an empty string — "
    "and un-resolving a target means sending `to_entity: null` together with "
    "a non-blank `to_name`.\n\n"
    "The target rules of the creation apply unchanged, and the uniqueness of "
    "the triple is checked excluding this relation itself.\n\n"
    "**Response.** `200` with the updated relation. A refused request returns "
    "`400` and changes nothing."
)

RELATION_DELETE_DESCRIPTION = (
    "Deletes one outgoing relation of the record named by the slug.\n\n"
    + CHILD_RIGHTS
    + CHILD_LOOKUP
    + "Only that relation row is removed. Neither the record nor the target "
    "figure is affected — deleting a link never deletes a figure — and no "
    "entity is ever deleted here. The removal is immediate and final.\n\n"
    "**Response.** `204` with no body."
)

SOURCE_REQUEST_EXAMPLE = OpenApiExample(
    "Documentary source (synthetic)",
    description=(
        "Invented reference, shown to illustrate the request shape. On a "
        "patch, send only the keys to change."
    ),
    request_only=True,
    value={
        "label": "Synthetic Reference Work",
        "kind": "book",
        "url": "",
        "accessed_at": None,
        "notes": "Invented reference, for documentation only.",
    },
)

RELATION_REQUEST_EXAMPLE = OpenApiExample(
    "Relation to a cited figure (synthetic)",
    description=(
        "Invented link, shown to illustrate the request shape. Here the target "
        "has no record, so it is cited by name and `to_entity` stays `null`. "
        "On a patch, send only the keys to change — plus the other target key "
        "when switching between the two forms."
    ),
    request_only=True,
    value={
        "kind": "parent",
        "to_entity": None,
        "to_name": "Figure Without A Record",
        "notes": "",
    },
)

CHILD_NOT_FOUND_RESPONSE = OpenApiResponse(
    response=ErrorDetailSerializer,
    description=(
        "Nothing was found to write on. The same response is returned whether "
        "the slug does not exist, refers to a record this account may not "
        "read, or refers to a deleted record, and whether the child identifier "
        "does not exist, belongs to another record, or — for a relation — "
        "points at a target this account may not read. The body never reveals "
        "which."
    ),
    examples=[
        OpenApiExample(
            "UnknownOrUnreachableRow",
            response_only=True,
            value={"detail": "No Source matches the given query."},
        )
    ],
)

CHILD_INVALID_RESPONSE = OpenApiResponse(
    response={
        "type": "object",
        "additionalProperties": {"type": "array", "items": {"type": "string"}},
    },
    description=(
        "The request was refused and **nothing was changed**. One key per "
        "field at fault, each carrying its messages; a model-level rule, such "
        "as the one-target rule of a relation or a uniqueness violation, "
        "appears under `non_field_errors` or under the field it names. A "
        "refused key is always named, never ignored."
    ),
    examples=[
        OpenApiExample(
            "NoTarget",
            response_only=True,
            value={"to_name": ["Provide either a target entity or a target name."]},
        ),
        OpenApiExample(
            "TwoTargets",
            response_only=True,
            value={
                "to_name": [
                    "Leave the target name empty when a target entity is selected."
                ]
            },
        ),
        OpenApiExample(
            "UnreadableTarget",
            response_only=True,
            value={
                "to_entity": [
                    "No target figure readable by this account matches this "
                    "identifier."
                ]
            },
        ),
        OpenApiExample(
            "ParentComesFromTheUrl",
            response_only=True,
            value={
                "entity": [
                    "The record this belongs to comes from the URL; it cannot "
                    "be supplied, and an existing row is never moved to "
                    "another record."
                ]
            },
        ),
    ],
)


# --- Editorial transitions ----------------------------------------------
#
# Trois actions, un seul contrat d'accès et de corps. Les parties communes
# sont assemblées une fois.

TRANSITION_ACCESS = (
    "Requires an access token and an editorial role. The actor must be the "
    "record's **own contributor**, a reviewer or an administrator; a reviewer "
    "and an administrator may act on a record that has no owner. A record "
    "this account may read without being one of those actors returns `403`, "
    "and an unknown slug, an unreadable record and a deleted record all "
    "return the same `404`. No transition ever changes the owner.\n\n"
)

TRANSITION_BODY = (
    "**No input.** Send no body at all, or an empty JSON object `{}`. Any "
    "other body — a non-empty object, an array, a string — returns `400` "
    "rather than being ignored: there is no status, date, actor, review note "
    "or business field to supply here.\n\n"
)

TRANSITION_RESULT = (
    "Only the editorial state is written, in a single transaction, on the "
    "locked row: the owner, the type, the business fields, the profile, the "
    "reference data, the sources and the relations are untouched, and "
    "`updated_at` moves only on success. A refused request changes nothing at "
    "all.\n\n"
    "**Response.** `200` with the private detail representation of the "
    "record, whose nested references follow the calling account's own read "
    "rule, exactly as on the private detail endpoint."
)

SUBMIT_DESCRIPTION = (
    "Submits a `draft` record for review: its status becomes `submitted` and "
    "`submitted_at` is set to the server's current time.\n\n"
    + TRANSITION_ACCESS
    + "**Only a draft can be submitted.** Any other starting status returns "
    "`400`, which is also what a second submission of the same record "
    "returns.\n\n"
    "**A submission opens a fresh review.** `reviewed_at`, `reviewed_by` and "
    "`review_notes` are cleared, so an earlier decision cannot look as though "
    "it concerned this submission. Submitting is neither a publication nor a "
    "documentary certification, and no completeness threshold is checked: "
    "nothing is filled in or repaired on the way.\n\n"
    "While a record is `submitted`, its own contributor keeps reading it but "
    "may no longer update it, nor write its sources and relations; a reviewer "
    "still may.\n\n" + TRANSITION_BODY + TRANSITION_RESULT
)

WITHDRAW_DESCRIPTION = (
    "Withdraws a `submitted` record: its status returns to `draft` and "
    "`submitted_at` is cleared.\n\n"
    + TRANSITION_ACCESS
    + "**Only a submitted record can be withdrawn.** Any other starting "
    "status returns `400`.\n\n"
    "**A withdrawal is not a rejection.** `reviewed_at`, `reviewed_by` and "
    "`review_notes` are left exactly as they were. Once back to `draft`, the "
    "ordinary update rights of a draft apply again, for the record and for "
    "its sources and relations.\n\n" + TRANSITION_BODY + TRANSITION_RESULT
)

RESUME_DESCRIPTION = (
    "Resumes a `rejected` record: its status returns to `draft` and "
    "`submitted_at` is cleared.\n\n"
    + TRANSITION_ACCESS
    + "**Only a rejected record can be resumed.** Any other starting status "
    "returns `400`.\n\n"
    "**The last review is kept** — `reviewed_at`, `reviewed_by` and "
    "`review_notes` — so the corrections can be guided by it. It is cleared "
    "by the next submission. These fields carry the current state and the "
    "last review kept, not an exhaustive history.\n\n"
    + TRANSITION_BODY
    + TRANSITION_RESULT
)

TRANSITION_FORBIDDEN_RESPONSE = OpenApiResponse(
    response=ErrorDetailSerializer,
    description=(
        "Either the token is valid but its account holds no editorial role, or "
        "the account may read this record without being an actor of its "
        "transitions — a contributor facing a record owned by someone else, "
        "for instance. The body distinguishes the two cases."
    ),
    examples=[
        OpenApiExample(
            "NotAnActorOfThisRecord",
            response_only=True,
            value={
                "detail": (
                    "This account may read this record but not run an "
                    "editorial transition on it. Submitting, withdrawing and "
                    "resuming require being the record's own contributor, a "
                    "reviewer or an administrator."
                )
            },
        )
    ],
)

TRANSITION_INVALID_RESPONSE = OpenApiResponse(
    response=CreationErrorSerializer,
    description=(
        "The record was **not** changed: either its starting status does not "
        "allow this transition — which includes repeating an action that has "
        "already succeeded — or the request carried a body. No date, note or "
        "field is written in either case."
    ),
    examples=[
        OpenApiExample(
            "WrongStartingStatus",
            response_only=True,
            value={
                "non_field_errors": [
                    "Only a draft record can be submitted for review. This "
                    "record is currently 'submitted'."
                ]
            },
        ),
        OpenApiExample(
            "UnexpectedBody",
            response_only=True,
            value={
                "non_field_errors": [
                    "This action takes no input. Send no body at all, or an "
                    "empty JSON object `{}`; any other body is refused rather "
                    "than ignored."
                ]
            },
        ),
    ],
)
