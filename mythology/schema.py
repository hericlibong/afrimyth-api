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
    "Write methods are refused with `405 Method Not Allowed`, for every role."
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
    "Write methods are refused with `405 Method Not Allowed`, for every role."
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
