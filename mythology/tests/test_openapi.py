"""Tests for the OpenAPI schema and the two documentation interfaces.

These tests check what the schema **declares**, not the runtime behaviour of
the API: the functional suites already cover visibility, pagination and
filtering, and are not duplicated here.

Scope limit, stated plainly: a `200` on an HTML page proves that Django
serves it, **not** that Swagger UI or ReDoc successfully loaded their
JavaScript and rendered the schema. That remains a manual browser check.
"""

import json
from typing import Any

import pytest
import yaml
from django.test import Client
from django.urls import reverse

from mythology.models import EntityType

pytestmark = pytest.mark.django_db

SCHEMA_URL = reverse("schema")


@pytest.fixture
def schema(client: Client) -> dict[str, Any]:
    """Fetch and parse the schema as an anonymous client would."""
    response = client.get(SCHEMA_URL)
    assert response.status_code == 200
    parsed = yaml.safe_load(response.content.decode())
    assert isinstance(parsed, dict)
    return parsed


# --- Availability -------------------------------------------------------


def test_schema_is_available_anonymously(client: Client) -> None:
    """The schema is readable without logging in, like the API it describes."""
    response = client.get(SCHEMA_URL)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/vnd.oai.openapi")


def test_schema_is_parsable_and_declares_openapi_3(schema: dict[str, Any]) -> None:
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == "Afrimyth API"
    assert schema["info"]["version"] == "0.1.0"


@pytest.mark.parametrize("route", ["swagger-ui", "redoc"])
def test_documentation_pages_are_served_anonymously(client: Client, route: str) -> None:
    """Both interfaces answer anonymously and point at our own schema.

    A `200` here means Django served the HTML shell. Whether the page then
    renders correctly in a browser is checked manually.
    """
    response = client.get(reverse(route))

    assert response.status_code == 200
    body = response.content.decode()
    assert SCHEMA_URL in body


def test_schema_generation_does_not_need_published_data(
    client: Client, schema: dict[str, Any]
) -> None:
    """The schema is produced by introspection, not from the data.

    This test runs on an empty database: if generation depended on existing
    records, it would fail here.
    """
    from mythology.models import Entity

    assert Entity.objects.count() == 0
    assert set(schema["paths"]) == {
        "/api/health/",
        "/api/entities/",
        "/api/entities/{slug}/",
    }


def test_redoc_uses_a_pinned_classic_script(client: Client) -> None:
    """Keep the classic-script template off the incompatible latest bundle."""
    response = client.get(reverse("redoc"))
    body = response.content.decode()

    assert response.status_code == 200
    expected_script = (
        "https://cdn.jsdelivr.net/npm/redoc@2.5.3/bundles/redoc.standalone.js"
    )
    assert expected_script in body
    assert "redoc@latest" not in body


# --- Paths and methods --------------------------------------------------


def test_only_get_is_declared(schema: dict[str, Any]) -> None:
    """No write operation is advertised anywhere in the schema."""
    for path, operations in schema["paths"].items():
        assert set(operations) == {"get"}, f"{path} declares more than GET"


def test_documentation_routes_are_not_in_the_schema(schema: dict[str, Any]) -> None:
    """The schema describes the API, not its own documentation routes."""
    for path in ("/api/schema/", "/api/docs/", "/api/redoc/"):
        assert path not in schema["paths"]


def test_no_authentication_is_advertised(schema: dict[str, Any]) -> None:
    """A client must not believe it has to authenticate to read.

    Neither a global `security` requirement nor a per-operation one is
    declared.
    """
    assert "security" not in schema
    for operations in schema["paths"].values():
        for operation in operations.values():
            assert "security" not in operation


# --- List parameters ----------------------------------------------------


def test_list_declares_the_five_parameters(schema: dict[str, Any]) -> None:
    parameters = schema["paths"]["/api/entities/"]["get"]["parameters"]
    names = sorted(parameter["name"] for parameter in parameters)

    assert names == ["country", "cultural_area", "entity_type", "page", "search"]
    assert all(parameter["in"] == "query" for parameter in parameters)
    assert all(not parameter.get("required", False) for parameter in parameters)


def test_list_parameters_are_not_duplicated(schema: dict[str, Any]) -> None:
    """Automatic detection must not double a hand-declared parameter."""
    parameters = schema["paths"]["/api/entities/"]["get"]["parameters"]
    names = [parameter["name"] for parameter in parameters]

    assert len(names) == len(set(names))


def test_entity_type_parameter_lists_the_three_values(schema: dict[str, Any]) -> None:
    parameters = schema["paths"]["/api/entities/"]["get"]["parameters"]
    entity_type = next(p for p in parameters if p["name"] == "entity_type")

    assert sorted(entity_type["schema"]["enum"]) == sorted(EntityType.values)


@pytest.mark.parametrize(
    ("parameter", "expected"),
    [
        ("search", "story_description"),
        ("country", "ISO 3166-1 alpha-2"),
        ("cultural_area", "descendants"),
        ("page", "fixed at 20"),
    ],
)
def test_list_parameters_document_their_scope(
    schema: dict[str, Any], parameter: str, expected: str
) -> None:
    """Each parameter's description states what it actually does."""
    parameters = schema["paths"]["/api/entities/"]["get"]["parameters"]
    described = next(p for p in parameters if p["name"] == parameter)

    assert expected in described["description"]


def test_detail_declares_only_the_slug_parameter(schema: dict[str, Any]) -> None:
    """Collection parameters must not appear on the detail operation."""
    parameters = schema["paths"]["/api/entities/{slug}/"]["get"]["parameters"]

    assert [parameter["name"] for parameter in parameters] == ["slug"]
    assert parameters[0]["in"] == "path"
    assert parameters[0]["required"] is True


def test_list_description_covers_the_combination_rules(
    schema: dict[str, Any],
) -> None:
    """Combination, deduplication and the empty envelope are documented."""
    description = schema["paths"]["/api/entities/"]["get"]["description"]

    assert "combine with AND" in description
    assert "combine with OR" in description
    assert "only" in description and "once" in description
    assert '"count": 0' in description
    assert "405" in description


# --- Responses ----------------------------------------------------------


def test_list_declares_its_error_responses(schema: dict[str, Any]) -> None:
    responses = schema["paths"]["/api/entities/"]["get"]["responses"]

    assert sorted(responses) == ["200", "400", "404"]


def test_detail_declares_its_error_responses(schema: dict[str, Any]) -> None:
    responses = schema["paths"]["/api/entities/{slug}/"]["get"]["responses"]

    assert sorted(responses) == ["200", "404"]


def test_declared_404_matches_the_message_actually_returned(
    client: Client, schema: dict[str, Any]
) -> None:
    """The documented 404 body is the one the API really sends."""
    documented = schema["paths"]["/api/entities/{slug}/"]["get"]["responses"]["404"]
    examples = documented["content"]["application/json"]["examples"]
    declared = next(iter(examples.values()))["value"]

    actual = client.get(reverse("entity-detail", kwargs={"slug": "never-seen"}))

    assert actual.status_code == 404
    assert actual.json() == declared


@pytest.mark.parametrize(
    ("query", "key", "example_name"),
    [
        ({"entity_type": "titan"}, "entity_type", "UnknownEntityType"),
        ({"country": "NGA"}, "country", "MalformedCountryCode"),
    ],
)
def test_declared_400_matches_the_message_actually_returned(
    client: Client,
    schema: dict[str, Any],
    query: dict[str, str],
    key: str,
    example_name: str,
) -> None:
    """Each documented 400 body is the one the API really sends."""
    documented = schema["paths"]["/api/entities/"]["get"]["responses"]["400"]
    examples = documented["content"]["application/json"]["examples"]
    declared = examples[example_name]["value"]

    actual = client.get(reverse("entity-list"), query)

    assert actual.status_code == 400
    assert actual.json() == declared
    assert key in declared


def test_404_description_does_not_disclose_existence(schema: dict[str, Any]) -> None:
    """The 404 is documented as deliberately indistinguishable."""
    documented = schema["paths"]["/api/entities/{slug}/"]["get"]["responses"]["404"]

    assert "never reveals which" in documented["description"]


# --- Pagination envelope ------------------------------------------------


def test_list_response_is_the_paginated_envelope(schema: dict[str, Any]) -> None:
    content = schema["paths"]["/api/entities/"]["get"]["responses"]["200"]["content"]
    reference = content["application/json"]["schema"]["$ref"]
    component = reference.rsplit("/", 1)[-1]
    envelope = schema["components"]["schemas"][component]["properties"]

    assert sorted(envelope) == ["count", "next", "previous", "results"]
    assert envelope["count"]["type"] == "integer"
    assert envelope["next"]["nullable"] is True
    assert envelope["previous"]["nullable"] is True
    assert envelope["results"]["items"]["$ref"].endswith("/EntityList")


def test_list_items_carry_exactly_five_fields(schema: dict[str, Any]) -> None:
    item = schema["components"]["schemas"]["EntityList"]["properties"]

    assert sorted(item) == ["category", "entity_type", "id", "name", "slug"]


def test_health_response_is_not_paginated(schema: dict[str, Any]) -> None:
    """The health endpoint keeps its own shape."""
    content = schema["paths"]["/api/health/"]["get"]["responses"]["200"]["content"]
    reference = content["application/json"]["schema"]["$ref"]

    assert reference.endswith("/Health")
    assert sorted(schema["components"]["schemas"]["Health"]["properties"]) == ["status"]


# --- Detail shape -------------------------------------------------------


def test_detail_identifier_is_a_uuid(schema: dict[str, Any]) -> None:
    identifier = schema["components"]["schemas"]["EntityDetail"]["properties"]["id"]

    assert identifier["type"] == "string"
    assert identifier["format"] == "uuid"


@pytest.mark.parametrize(
    "field",
    [
        "primary_country",
        "primary_ethnicity",
        "primary_cultural_area",
        "variant_of",
        "divinity_profile",
        "hero_profile",
        "creature_profile",
    ],
)
def test_nullable_references_are_declared_nullable(
    schema: dict[str, Any], field: str
) -> None:
    """Every key that can really be `null` says so in the schema."""
    properties = schema["components"]["schemas"]["EntityDetail"]["properties"]

    assert properties[field].get("nullable") is True, field


@pytest.mark.parametrize(
    "field",
    [
        "secondary_countries",
        "secondary_ethnicities",
        "secondary_cultural_areas",
        "domains",
        "relations",
        "sources",
    ],
)
def test_collections_are_declared_as_arrays(schema: dict[str, Any], field: str) -> None:
    properties = schema["components"]["schemas"]["EntityDetail"]["properties"]

    assert properties[field]["type"] == "array"
    assert "$ref" in properties[field]["items"]


def test_method_fields_are_typed_precisely(schema: dict[str, Any]) -> None:
    """The two `SerializerMethodField` keys reference real components.

    Without explicit typing they would be described as untyped objects, which
    would tell a client nothing.
    """
    properties = schema["components"]["schemas"]["EntityDetail"]["properties"]

    assert properties["variant_of"]["allOf"][0]["$ref"].endswith("/EntityReference")
    assert properties["relations"]["items"]["$ref"].endswith("/EntityRelation")


def test_nested_reference_is_not_recursive(schema: dict[str, Any]) -> None:
    """A target is a four-field reference, with no nested detail."""
    reference = schema["components"]["schemas"]["EntityReference"]["properties"]

    assert sorted(reference) == ["entity_type", "id", "name", "slug"]
    assert "relations" not in reference
    assert "variant_of" not in reference


def test_relation_declares_both_target_forms(schema: dict[str, Any]) -> None:
    relation = schema["components"]["schemas"]["EntityRelation"]["properties"]

    assert sorted(relation) == ["id", "kind", "notes", "to_entity", "to_name"]
    assert relation["to_entity"].get("nullable") is True


def test_detail_description_covers_nested_visibility(schema: dict[str, Any]) -> None:
    description = schema["paths"]["/api/entities/{slug}/"]["get"]["description"]

    assert "omitted entirely" in description
    assert "never copied into `to_name`" in description
    assert "never nested recursively" in description


# --- No internal field leaks -------------------------------------------


INTERNAL_FIELDS = (
    "created_by",
    "status",
    "submitted_at",
    "reviewed_at",
    "reviewed_by",
    "review_notes",
    "deleted_at",
    "deleted_by",
)


@pytest.mark.parametrize("component", ["EntityDetail", "EntityList", "EntityReference"])
def test_no_internal_editorial_field_is_published(
    schema: dict[str, Any], component: str
) -> None:
    """None of the platform fields appears in any published component."""
    properties = schema["components"]["schemas"][component]["properties"]

    for field in INTERNAL_FIELDS:
        assert field not in properties, f"{field} leaked into {component}"


def test_no_user_component_is_published(schema: dict[str, Any]) -> None:
    """No account, email or user identity is described anywhere."""
    serialized = json.dumps(schema["components"]["schemas"]).lower()

    assert "password" not in serialized
    assert "email" not in serialized
    assert "username" not in serialized


# --- Examples -----------------------------------------------------------


def test_examples_are_labelled_as_synthetic(schema: dict[str, Any]) -> None:
    """Examples must not pass for validated mythological facts."""
    liste = schema["paths"]["/api/entities/"]["get"]["responses"]["200"]
    detail = schema["paths"]["/api/entities/{slug}/"]["get"]["responses"]["200"]

    for response in (liste, detail):
        examples = response["content"]["application/json"]["examples"]
        for example in examples.values():
            text = f"{example.get('summary', '')} {example.get('description', '')}"
            assert "synthetic" in text.lower() or "invented" in text.lower()


def test_detail_example_matches_the_serializer_keys(schema: dict[str, Any]) -> None:
    """The hand-written example carries exactly the documented keys.

    This is what keeps the example from drifting away from the serializer.
    """
    detail = schema["paths"]["/api/entities/{slug}/"]["get"]["responses"]["200"]
    examples = detail["content"]["application/json"]["examples"]
    example = next(iter(examples.values()))["value"]
    declared = schema["components"]["schemas"]["EntityDetail"]["properties"]

    assert set(example) == set(declared)


def test_list_example_matches_the_list_serializer_keys(
    schema: dict[str, Any],
) -> None:
    liste = schema["paths"]["/api/entities/"]["get"]["responses"]["200"]
    examples = liste["content"]["application/json"]["examples"]
    envelope = next(iter(examples.values()))["value"]
    item = envelope["results"][0]
    declared = schema["components"]["schemas"]["EntityList"]["properties"]

    assert set(item) == set(declared)


def test_global_description_states_the_main_caveats(schema: dict[str, Any]) -> None:
    """Visibility, read-only, empty collection and editorial caveat."""
    description = schema["info"]["description"]

    assert "if and only if" in description
    assert "405" in description
    assert "drafts" in description
    assert "editorial review" in description
