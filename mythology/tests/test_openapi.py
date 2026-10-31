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
        "/api/manage/entities/",
        "/api/manage/entities/{slug}/",
        "/api/manage/entities/{slug}/sources/",
        "/api/manage/entities/{slug}/sources/{source_id}/",
        "/api/manage/entities/{slug}/relations/",
        "/api/manage/entities/{slug}/relations/{relation_id}/",
        "/api/manage/entities/{slug}/submit/",
        "/api/manage/entities/{slug}/withdraw/",
        "/api/manage/entities/{slug}/resume/",
        "/api/auth/token/",
        "/api/auth/token/refresh/",
        "/api/auth/me/",
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


#: Les écritures de contenu autorisées : création et PATCH d'entité, puis
#: écritures individuelles des sources et relations. Le reste du corpus
#: reste en lecture seule dans le schéma. Les routes `/api/auth/` sont exclues :
#: elles portent des identifiants dans un corps de requête, donc en POST, et ne
#: créent aucun contenu.
WRITABLE_OPERATIONS = {
    "/api/manage/entities/": {"get", "post"},
    "/api/manage/entities/{slug}/": {"get", "patch"},
    "/api/manage/entities/{slug}/sources/": {"post"},
    "/api/manage/entities/{slug}/sources/{source_id}/": {"patch", "delete"},
    "/api/manage/entities/{slug}/relations/": {"post"},
    "/api/manage/entities/{slug}/relations/{relation_id}/": {"patch", "delete"},
    "/api/manage/entities/{slug}/submit/": {"post"},
    "/api/manage/entities/{slug}/withdraw/": {"post"},
    "/api/manage/entities/{slug}/resume/": {"post"},
}


def test_content_paths_only_declare_their_expected_methods(
    schema: dict[str, Any],
) -> None:
    """Only the designated private routes advertise content writes."""
    content_paths = {
        path for path in schema["paths"] if not path.startswith("/api/auth/")
    }
    assert content_paths  # garde-fou : un préfixe mal écrit viderait la boucle
    for path in content_paths:
        expected = WRITABLE_OPERATIONS.get(path, {"get"})
        assert set(schema["paths"][path]) == expected, path


def test_authentication_paths_only_declare_post_or_get(schema: dict[str, Any]) -> None:
    """Token issuance and refresh are POST; the identity check is GET."""
    assert set(schema["paths"]["/api/auth/token/"]) == {"post"}
    assert set(schema["paths"]["/api/auth/token/refresh/"]) == {"post"}
    assert set(schema["paths"]["/api/auth/me/"]) == {"get"}


def test_documentation_routes_are_not_in_the_schema(schema: dict[str, Any]) -> None:
    """The schema describes the API, not its own documentation routes."""
    for path in ("/api/schema/", "/api/docs/", "/api/redoc/"):
        assert path not in schema["paths"]


#: Les seules opérations autorisées à annoncer une exigence de sécurité :
#: la vérification d'identité et les deux routes éditoriales privées. Tout le
#: reste est public et doit le rester dans le schéma.
PROTECTED_PATHS = {
    "/api/auth/me/",
    "/api/manage/entities/",
    "/api/manage/entities/{slug}/",
    "/api/manage/entities/{slug}/sources/",
    "/api/manage/entities/{slug}/sources/{source_id}/",
    "/api/manage/entities/{slug}/relations/",
    "/api/manage/entities/{slug}/relations/{relation_id}/",
    "/api/manage/entities/{slug}/submit/",
    "/api/manage/entities/{slug}/withdraw/",
    "/api/manage/entities/{slug}/resume/",
}


def test_authentication_is_advertised_only_on_the_protected_paths(
    schema: dict[str, Any],
) -> None:
    """Only the identity endpoint and the private routes require a token.

    A global `security` entry would make Swagger present every read as
    protected, which would be false: public reading is anonymous, and
    obtaining a token cannot itself require a token.
    """
    assert "security" not in schema
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            advertised = "security" in operation
            assert advertised is (path in PROTECTED_PATHS), f"{method.upper()} {path}"


#: Les deux routes privées qui portent une lecture.
PRIVATE_READ_PATHS = ["/api/manage/entities/", "/api/manage/entities/{slug}/"]


@pytest.mark.parametrize("path", PRIVATE_READ_PATHS)
def test_private_routes_require_a_bearer_token(
    schema: dict[str, Any], path: str
) -> None:
    """Swagger must offer Bearer authentication on the private routes."""
    assert schema["paths"][path]["get"]["security"] == [{"jwtAuth": []}]


@pytest.mark.parametrize("path", PRIVATE_READ_PATHS)
def test_private_routes_declare_their_refusals(
    schema: dict[str, Any], path: str
) -> None:
    """A reader must know that `401` and `403` mean different things."""
    responses = schema["paths"][path]["get"]["responses"]

    assert {"401", "403"} <= set(responses)
    assert "JWT" in responses["401"]["description"]
    assert "contributor" in responses["403"]["description"]


def test_private_detail_404_does_not_disclose_existence(
    schema: dict[str, Any],
) -> None:
    """The private 404 is documented as deliberately indistinguishable."""
    documented = schema["paths"]["/api/manage/entities/{slug}/"]["get"]["responses"][
        "404"
    ]

    assert "never reveals which" in documented["description"]


def test_private_list_reuses_the_five_parameters(schema: dict[str, Any]) -> None:
    """The private collection documents the same navigation, not another one."""
    private = schema["paths"]["/api/manage/entities/"]["get"]["parameters"]
    public = schema["paths"]["/api/entities/"]["get"]["parameters"]

    assert private == public


def test_private_detail_declares_only_the_slug_parameter(
    schema: dict[str, Any],
) -> None:
    parameters = schema["paths"]["/api/manage/entities/{slug}/"]["get"]["parameters"]

    assert [parameter["name"] for parameter in parameters] == ["slug"]


def test_private_components_add_exactly_the_editorial_fields(
    schema: dict[str, Any],
) -> None:
    """The private payloads extend the public ones; they do not replace them."""
    components = schema["components"]["schemas"]

    assert set(components["PrivateEntityList"]["properties"]) == set(
        components["EntityList"]["properties"]
    ) | {"status", "created_by"}
    assert set(components["PrivateEntityDetail"]["properties"]) == set(
        components["EntityDetail"]["properties"]
    ) | {
        "status",
        "created_by",
        "submitted_at",
        "reviewed_at",
        "reviewed_by",
        "review_notes",
    }


def test_private_components_never_expose_the_deletion_marks(
    schema: dict[str, Any],
) -> None:
    """Deletion stays outside the contract, private payloads included."""
    for component in ("PrivateEntityList", "PrivateEntityDetail"):
        properties = schema["components"]["schemas"][component]["properties"]
        assert "deleted_at" not in properties, component
        assert "deleted_by" not in properties, component


@pytest.mark.parametrize(
    ("component", "field"),
    [
        ("PrivateEntityList", "created_by"),
        ("PrivateEntityDetail", "created_by"),
        ("PrivateEntityDetail", "reviewed_by"),
    ],
)
def test_private_actors_are_declared_as_nullable_identifiers(
    schema: dict[str, Any], component: str, field: str
) -> None:
    """The three actors are account identifiers, never nested accounts."""
    declared = schema["components"]["schemas"][component]["properties"][field]

    assert declared.get("nullable") is True
    assert "$ref" not in declared


def test_private_detail_example_matches_its_component(
    schema: dict[str, Any],
) -> None:
    """The hand-written private example cannot drift from the serializer."""
    detail = schema["paths"]["/api/manage/entities/{slug}/"]["get"]["responses"]["200"]
    examples = detail["content"]["application/json"]["examples"]
    example = next(iter(examples.values()))["value"]
    declared = schema["components"]["schemas"]["PrivateEntityDetail"]["properties"]

    assert set(example) == set(declared)


def test_private_list_example_matches_its_component(schema: dict[str, Any]) -> None:
    liste = schema["paths"]["/api/manage/entities/"]["get"]["responses"]["200"]
    examples = liste["content"]["application/json"]["examples"]
    envelope = next(iter(examples.values()))["value"]
    declared = schema["components"]["schemas"]["PrivateEntityList"]["properties"]

    assert set(envelope["results"][0]) == set(declared)


# --- Private editorial creation -----------------------------------------

PRIVATE_CREATE = "/api/manage/entities/"

#: Les champs d'entrée acceptés par la création, déclarés une fois ici. Le
#: schéma et le serializer doivent dire la même chose : un champ ajouté au
#: contrat sans intention apparaîtra comme un écart.
CREATE_INPUT_FIELDS = {
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
}


def create_operation(schema: dict[str, Any]) -> dict[str, Any]:
    operation = schema["paths"][PRIVATE_CREATE]["post"]
    assert isinstance(operation, dict)
    return operation


def test_creation_requires_a_bearer_token(schema: dict[str, Any]) -> None:
    """Creation is never offered anonymously."""
    assert create_operation(schema)["security"] == [{"jwtAuth": []}]


def test_creation_declares_its_refusals(schema: dict[str, Any]) -> None:
    """A reader must know that 400, 401 and 403 mean different things."""
    responses = create_operation(schema)["responses"]

    assert sorted(responses) == ["201", "400", "401", "403"]
    assert "JWT" in responses["401"]["description"]
    assert "contributor" in responses["403"]["description"]
    assert "nothing was created" in responses["400"]["description"]


def test_creation_answers_with_the_private_detail(schema: dict[str, Any]) -> None:
    """The created record is returned with the private detail representation."""
    created = create_operation(schema)["responses"]["201"]
    reference = created["content"]["application/json"]["schema"]["$ref"]

    assert reference.endswith("/PrivateEntityDetail")


def test_the_request_body_declares_exactly_the_accepted_fields(
    schema: dict[str, Any],
) -> None:
    """The documented input is the explicit field list, nothing more."""
    body = create_operation(schema)["requestBody"]
    reference = body["content"]["application/json"]["schema"]["$ref"]
    component = reference.rsplit("/", 1)[-1]
    declared = schema["components"]["schemas"][component]["properties"]

    assert set(declared) == CREATE_INPUT_FIELDS


@pytest.mark.parametrize(
    "field",
    [
        "id",
        "status",
        "created_by",
        "submitted_at",
        "reviewed_at",
        "reviewed_by",
        "review_notes",
        "deleted_at",
        "deleted_by",
        "created_at",
        "updated_at",
        "sources",
        "relations",
    ],
)
def test_no_server_controlled_field_is_offered_as_input(
    schema: dict[str, Any], field: str
) -> None:
    """Swagger must not invite a client to fill a field the server imposes."""
    body = create_operation(schema)["requestBody"]
    reference = body["content"]["application/json"]["schema"]["$ref"]
    component = reference.rsplit("/", 1)[-1]

    declared = schema["components"]["schemas"][component]["properties"]
    assert field not in declared


def test_the_request_body_requires_the_four_fields(schema: dict[str, Any]) -> None:
    body = create_operation(schema)["requestBody"]
    reference = body["content"]["application/json"]["schema"]["$ref"]
    component = reference.rsplit("/", 1)[-1]

    required = schema["components"]["schemas"][component]["required"]
    assert sorted(required) == ["entity_type", "gender", "name", "slug"]


def test_the_creation_description_states_what_the_server_imposes(
    schema: dict[str, Any],
) -> None:
    """The contract must say who decides the owner, the status and the rest."""
    description = create_operation(schema)["description"]

    assert "`draft`" in description
    assert "created_by" in description
    assert "not even by an administrator" in description
    assert "never confirms" in description
    assert "single transaction" in description
    assert "`sources` and `relations` cannot be created" in description
    assert "the dedicated routes" in description


def test_the_creation_examples_are_labelled_as_synthetic(
    schema: dict[str, Any],
) -> None:
    """Neither example may pass for a validated mythological fact."""
    operation = create_operation(schema)
    request = operation["requestBody"]["content"]["application/json"]["examples"]
    created = operation["responses"]["201"]["content"]["application/json"]["examples"]

    for examples in (request, created):
        for example in examples.values():
            text = f"{example.get('summary', '')} {example.get('description', '')}"
            assert "synthetic" in text.lower() or "invented" in text.lower()


def test_the_created_example_matches_the_private_detail_component(
    schema: dict[str, Any],
) -> None:
    """The hand-written 201 example cannot drift from the serializer."""
    created = create_operation(schema)["responses"]["201"]
    examples = created["content"]["application/json"]["examples"]
    example = next(iter(examples.values()))["value"]
    declared = schema["components"]["schemas"]["PrivateEntityDetail"]["properties"]

    assert set(example) == set(declared)
    assert example["status"] == "draft"


def test_the_request_example_supplies_no_server_controlled_field(
    schema: dict[str, Any],
) -> None:
    request = create_operation(schema)["requestBody"]
    examples = request["content"]["application/json"]["examples"]
    example = next(iter(examples.values()))["value"]

    assert set(example) <= CREATE_INPUT_FIELDS


# --- Private editorial update -------------------------------------------

PRIVATE_DETAIL = "/api/manage/entities/{slug}/"


def update_operation(schema: dict[str, Any]) -> dict[str, Any]:
    operation = schema["paths"][PRIVATE_DETAIL]["patch"]
    assert isinstance(operation, dict)
    return operation


def update_request_component(schema: dict[str, Any]) -> dict[str, Any]:
    body = update_operation(schema)["requestBody"]
    reference = body["content"]["application/json"]["schema"]["$ref"]
    component = schema["components"]["schemas"][reference.rsplit("/", 1)[-1]]
    assert isinstance(component, dict)
    return component


def test_the_update_requires_a_bearer_token(schema: dict[str, Any]) -> None:
    assert update_operation(schema)["security"] == [{"jwtAuth": []}]


def test_the_update_declares_its_refusals(schema: dict[str, Any]) -> None:
    """A reader must know that 400, 401, 403 and 404 mean different things."""
    responses = update_operation(schema)["responses"]

    assert sorted(responses) == ["200", "400", "401", "403", "404"]
    assert "JWT" in responses["401"]["description"]
    assert "not modify it" in responses["403"]["description"]
    assert "never reveals which" in responses["404"]["description"]
    assert "nothing was changed" in responses["400"]["description"]


def test_the_update_answers_with_the_private_detail(schema: dict[str, Any]) -> None:
    updated = update_operation(schema)["responses"]["200"]
    reference = updated["content"]["application/json"]["schema"]["$ref"]

    assert reference.endswith("/PrivateEntityDetail")


def test_the_update_input_is_the_creation_input_without_the_type(
    schema: dict[str, Any],
) -> None:
    """The type cannot be patched, and nothing else was added or dropped."""
    declared = set(update_request_component(schema)["properties"])

    assert declared == CREATE_INPUT_FIELDS - {"entity_type"}


def test_every_update_field_is_optional(schema: dict[str, Any]) -> None:
    """A patch body carries only what it changes."""
    assert "required" not in update_request_component(schema)


def test_the_update_description_states_the_partial_contract(
    schema: dict[str, Any],
) -> None:
    description = update_operation(schema)["description"]

    assert "An omitted field keeps its value" in description
    assert "`[]` empties it" in description
    assert "entity type cannot change" in description
    assert "final state" in description
    assert "single transaction" in description
    assert "locked row" in description


def test_the_update_example_is_labelled_as_synthetic(schema: dict[str, Any]) -> None:
    examples = update_operation(schema)["requestBody"]["content"]["application/json"][
        "examples"
    ]

    for example in examples.values():
        text = f"{example.get('summary', '')} {example.get('description', '')}"
        assert "synthetic" in text.lower() or "invented" in text.lower()


def test_the_update_example_supplies_no_server_controlled_field(
    schema: dict[str, Any],
) -> None:
    examples = update_operation(schema)["requestBody"]["content"]["application/json"][
        "examples"
    ]
    example = next(iter(examples.values()))["value"]

    assert set(example) <= CREATE_INPUT_FIELDS - {"entity_type"}


# --- Private editorial writes on a record's children --------------------

#: Chemin → méthodes attendues, pour les six opérations ajoutées.
CHILD_OPERATIONS = {
    "/api/manage/entities/{slug}/sources/": ["post"],
    "/api/manage/entities/{slug}/sources/{source_id}/": ["patch", "delete"],
    "/api/manage/entities/{slug}/relations/": ["post"],
    "/api/manage/entities/{slug}/relations/{relation_id}/": ["patch", "delete"],
}

CHILD_OPERATION_IDS = [
    (path, method) for path, methods in CHILD_OPERATIONS.items() for method in methods
]


@pytest.mark.parametrize(("path", "method"), CHILD_OPERATION_IDS)
def test_every_child_operation_is_protected_and_declares_its_refusals(
    schema: dict[str, Any], path: str, method: str
) -> None:
    """Each child write needs a token and documents 401, 403 and 404."""
    operation = schema["paths"][path][method]

    assert operation["security"] == [{"jwtAuth": []}]
    assert {"401", "403", "404"} <= set(operation["responses"])
    assert "not modify it" in operation["responses"]["403"]["description"]


@pytest.mark.parametrize(("path", "method"), CHILD_OPERATION_IDS)
def test_every_child_operation_states_the_parent_right(
    schema: dict[str, Any], path: str, method: str
) -> None:
    """The right that governs a child write is the parent's update right."""
    description = schema["paths"][path][method]["description"]

    assert "update the record named by the slug" in description
    assert "The record itself is never touched" in description


@pytest.mark.parametrize(
    ("path", "method", "component"),
    [
        ("/api/manage/entities/{slug}/sources/", "post", "Source"),
        ("/api/manage/entities/{slug}/sources/{source_id}/", "patch", "Source"),
        ("/api/manage/entities/{slug}/relations/", "post", "EntityRelation"),
        (
            "/api/manage/entities/{slug}/relations/{relation_id}/",
            "patch",
            "EntityRelation",
        ),
    ],
)
def test_a_child_write_answers_with_the_existing_read_representation(
    schema: dict[str, Any], path: str, method: str, component: str
) -> None:
    """No new output shape is introduced for the children."""
    code = "201" if method == "post" else "200"
    body = schema["paths"][path][method]["responses"][code]

    reference = body["content"]["application/json"]["schema"]["$ref"]
    assert reference.endswith(f"/{component}")


@pytest.mark.parametrize(
    "path",
    [
        "/api/manage/entities/{slug}/sources/{source_id}/",
        "/api/manage/entities/{slug}/relations/{relation_id}/",
    ],
)
def test_a_child_deletion_answers_204_without_a_body(
    schema: dict[str, Any], path: str
) -> None:
    operation = schema["paths"][path]["delete"]

    assert "content" not in operation["responses"]["204"]
    assert "400" not in operation["responses"]
    assert "only that" in operation["description"].lower()


@pytest.mark.parametrize(
    ("path", "method", "component", "accepted"),
    [
        (
            "/api/manage/entities/{slug}/sources/",
            "post",
            "SourceWriteRequest",
            {"label", "kind", "url", "accessed_at", "notes"},
        ),
        (
            "/api/manage/entities/{slug}/sources/{source_id}/",
            "patch",
            "PatchedSourceWriteRequest",
            {"label", "kind", "url", "accessed_at", "notes"},
        ),
        (
            "/api/manage/entities/{slug}/relations/",
            "post",
            "RelationWriteRequest",
            {"kind", "to_entity", "to_name", "notes"},
        ),
        (
            "/api/manage/entities/{slug}/relations/{relation_id}/",
            "patch",
            "PatchedRelationWriteRequest",
            {"kind", "to_entity", "to_name", "notes"},
        ),
    ],
)
def test_a_child_input_declares_exactly_its_accepted_fields(
    schema: dict[str, Any],
    path: str,
    method: str,
    component: str,
    accepted: set[str],
) -> None:
    """Neither the identifier nor the owning record is offered as input."""
    body = schema["paths"][path][method]["requestBody"]
    reference = body["content"]["application/json"]["schema"]["$ref"]

    assert reference.endswith(f"/{component}")
    declared = schema["components"]["schemas"][component]
    assert set(declared["properties"]) == accepted


def test_a_child_creation_requires_its_mandatory_fields(
    schema: dict[str, Any],
) -> None:
    components = schema["components"]["schemas"]

    assert sorted(components["SourceWriteRequest"]["required"]) == ["kind", "label"]
    assert components["RelationWriteRequest"]["required"] == ["kind"]
    assert "required" not in components["PatchedSourceWriteRequest"]


def test_the_relation_contract_states_its_target_rules(schema: dict[str, Any]) -> None:
    """One target, readable, never resolved by name, never reciprocal."""
    created = schema["paths"]["/api/manage/entities/{slug}/relations/"]["post"]
    patched = schema["paths"]["/api/manage/entities/{slug}/relations/{relation_id}/"][
        "patch"
    ]

    assert "**exactly one** target" in created["description"]
    assert "never confirms that a record exists" in created["description"]
    assert "No inverse or reciprocal relation is created" in created["description"]
    assert "exactly one target" in patched["description"]
    assert "excluding this relation itself" in patched["description"]


def test_the_child_identifier_is_declared_as_an_integer_path_parameter(
    schema: dict[str, Any],
) -> None:
    for path, name in (
        ("/api/manage/entities/{slug}/sources/{source_id}/", "source_id"),
        ("/api/manage/entities/{slug}/relations/{relation_id}/", "relation_id"),
    ):
        parameters = schema["paths"][path]["patch"]["parameters"]
        declared = next(item for item in parameters if item["name"] == name)
        assert declared["in"] == "path"
        assert declared["schema"]["type"] == "integer"
        assert {item["name"] for item in parameters} == {"slug", name}


def test_child_validation_errors_accept_the_actual_field_names(
    schema: dict[str, Any],
) -> None:
    """Describe field-keyed errors, not entity creation fields on child writes."""
    for path, methods in CHILD_OPERATIONS.items():
        for method in set(methods) - {"delete"}:
            error = schema["paths"][path][method]["responses"]["400"]
            body = error["content"]["application/json"]["schema"]
            assert body["type"] == "object"
            assert body["additionalProperties"] == {
                "type": "array",
                "items": {"type": "string"},
            }


# --- Editorial transitions ----------------------------------------------

TRANSITION_PATHS = {
    "submit": "/api/manage/entities/{slug}/submit/",
    "withdraw": "/api/manage/entities/{slug}/withdraw/",
    "resume": "/api/manage/entities/{slug}/resume/",
}

TRANSITION_NAMES = sorted(TRANSITION_PATHS)


def transition_operation(schema: dict[str, Any], action: str) -> dict[str, Any]:
    operation = schema["paths"][TRANSITION_PATHS[action]]["post"]
    assert isinstance(operation, dict)
    return operation


@pytest.mark.parametrize("action", TRANSITION_NAMES)
def test_a_transition_is_protected_and_declares_its_refusals(
    schema: dict[str, Any], action: str
) -> None:
    """Each transition needs a token and documents 400, 401, 403 and 404."""
    operation = transition_operation(schema, action)

    assert operation["security"] == [{"jwtAuth": []}]
    assert sorted(operation["responses"]) == ["200", "400", "401", "403", "404"]
    assert "an actor of its transitions" in operation["responses"]["403"]["description"]
    assert "was **not** changed" in operation["responses"]["400"]["description"]


@pytest.mark.parametrize("action", TRANSITION_NAMES)
def test_a_transition_takes_no_input_and_documents_the_two_empty_forms(
    schema: dict[str, Any], action: str
) -> None:
    """No request body is declared, and the accepted empty forms are stated."""
    operation = transition_operation(schema, action)

    assert "requestBody" not in operation
    assert (
        "Send no body at all, or an empty JSON object `{}`"
        in (operation["description"])
    )


@pytest.mark.parametrize("action", TRANSITION_NAMES)
def test_a_transition_answers_with_the_private_detail(
    schema: dict[str, Any], action: str
) -> None:
    body = transition_operation(schema, action)["responses"]["200"]
    reference = body["content"]["application/json"]["schema"]["$ref"]

    assert reference.endswith("/PrivateEntityDetail")


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("submit", "`draft` record for review"),
        ("withdraw", "`submitted` record"),
        ("resume", "`rejected` record"),
    ],
)
def test_a_transition_states_its_starting_status(
    schema: dict[str, Any], action: str, expected: str
) -> None:
    description = transition_operation(schema, action)["description"]

    assert expected in description
    assert "a reviewer or an administrator" in description


def test_the_transitions_state_what_happens_to_the_review_marks(
    schema: dict[str, Any],
) -> None:
    """Each action says what it does with the dates and the last review."""
    submit = transition_operation(schema, "submit")["description"]
    withdraw = transition_operation(schema, "withdraw")["description"]
    resume = transition_operation(schema, "resume")["description"]

    assert "A submission opens a fresh review" in submit
    assert "neither a publication nor a documentary certification" in submit
    assert "A withdrawal is not a rejection" in withdraw
    assert "left exactly as they were" in withdraw
    assert "**The last review is kept**" in resume
    assert "cleared by the next submission" in resume


def test_no_moderation_decision_is_announced(schema: dict[str, Any]) -> None:
    """Publication, rejection and reopening must not look available."""
    description = schema["info"]["description"]
    detail = schema["paths"]["/api/manage/entities/{slug}/"]["get"]["description"]

    assert "publication, rejection" in description
    assert "not** part of this" in description
    assert "Publication, rejection, reopening" in detail
    assert "On the entity collection and detail themselves" in description
    assert "clear `submitted_at` and preserve the review marks" in description
    for path in TRANSITION_PATHS.values():
        assert set(schema["paths"][path]) == {"post"}, path


def test_the_private_descriptions_no_longer_claim_a_read_only_api(
    schema: dict[str, Any],
) -> None:
    """The texts must not keep announcing that every private route is read-only."""
    operations = schema["paths"]
    liste = operations[PRIVATE_CREATE]["get"]["description"]
    detail = operations[PRIVATE_DETAIL]["get"]["description"]

    assert "`POST` on this collection creates a draft entity" in liste
    assert "`PUT`, `PATCH` and `DELETE` are refused" in liste
    assert "`PATCH` updates this record" in detail
    assert "`PUT` and `DELETE` are refused" in detail
    for description in (liste, detail):
        assert "Write methods are refused" not in description


def test_the_global_description_states_what_can_be_written(
    schema: dict[str, Any],
) -> None:
    description = schema["info"]["description"]

    assert "POST /api/manage/entities/" in description
    assert "stay read-only" in description
    assert "405" in description


def test_the_public_detail_example_stays_on_the_public_route(
    schema: dict[str, Any],
) -> None:
    """Each route documents its own payload, with no example bleeding across.

    drf-spectacular accumulates annotations along an inheritance chain, so a
    private view inheriting the public one would publish the public example
    next to a private component. The two views therefore share only their
    navigation, through a base class carrying no annotation.
    """
    public = schema["paths"]["/api/entities/{slug}/"]["get"]["responses"]["200"]
    private = schema["paths"]["/api/manage/entities/{slug}/"]["get"]["responses"]["200"]

    assert len(public["content"]["application/json"]["examples"]) == 1
    assert len(private["content"]["application/json"]["examples"]) == 1


def test_token_responses_describe_their_payload(schema: dict[str, Any]) -> None:
    """Simple JWT's own serializers are input-only; the 200 must still be described.

    Without an explicit response serializer, drf-spectacular emits
    "No response body" for both routes, which would tell a client nothing
    about where to find its tokens.
    """
    pair = schema["paths"]["/api/auth/token/"]["post"]["responses"]["200"]
    refresh = schema["paths"]["/api/auth/token/refresh/"]["post"]["responses"]["200"]

    pair_schema = pair["content"]["application/json"]["schema"]
    refresh_schema = refresh["content"]["application/json"]["schema"]

    assert pair_schema["$ref"].endswith("/TokenPair")
    assert refresh_schema["$ref"].endswith("/AccessToken")
    assert set(schema["components"]["schemas"]["TokenPair"]["properties"]) == {
        "access",
        "refresh",
    }
    # Le renouvellement ne renvoie pas de nouveau `refresh` : la rotation est
    # désactivée, et le schéma doit dire la même chose que l'API.
    assert set(schema["components"]["schemas"]["AccessToken"]["properties"]) == {
        "access"
    }


def test_token_requests_declare_their_credentials(schema: dict[str, Any]) -> None:
    pair = schema["paths"]["/api/auth/token/"]["post"]["requestBody"]
    body = pair["content"]["application/json"]["schema"]

    assert body["$ref"].endswith("/TokenObtainPairRequest")
    declared = schema["components"]["schemas"]["TokenObtainPairRequest"]["properties"]
    assert set(declared) == {"username", "password"}


def test_me_requires_a_bearer_token(schema: dict[str, Any]) -> None:
    """Swagger must offer Bearer authentication for the identity endpoint."""
    operation = schema["paths"]["/api/auth/me/"]["get"]
    assert operation["security"] == [{"jwtAuth": []}]

    scheme = schema["components"]["securitySchemes"]["jwtAuth"]
    assert scheme == {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}


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


def test_no_account_data_leaks_into_content_components(
    schema: dict[str, Any],
) -> None:
    """Mythological components must not describe accounts.

    `CurrentUser` and the two token serializers are excluded: they exist to
    describe authentication and legitimately mention a username. Everything
    else — entities, profiles, reference data, sources, relations — must say
    nothing about accounts.
    """
    components = schema["components"]["schemas"]
    authentication = {
        "CurrentUser",
        "TokenPair",
        "TokenObtainPairRequest",
        "AccessToken",
        "TokenRefreshRequest",
        "CredentialsError",
        "FieldError",
    }
    content = {
        name: body for name, body in components.items() if name not in authentication
    }
    assert content  # garde-fou : une faute de nom viderait la comparaison

    serialized = json.dumps(content).lower()
    assert "password" not in serialized
    assert "email" not in serialized
    assert "username" not in serialized


def test_the_identity_component_exposes_only_id_and_username(
    schema: dict[str, Any],
) -> None:
    """`CurrentUser` must not grow into a profile endpoint by accident."""
    component = schema["components"]["schemas"]["CurrentUser"]

    assert set(component["properties"]) == {"id", "username"}


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


def test_global_description_states_the_token_caveats(schema: dict[str, Any]) -> None:
    """The absence of revocation and of authorisation must be stated."""
    description = schema["info"]["description"]

    assert "not authorisation" in description
    assert "cannot be revoked" in description
    assert "no logout endpoint" in description
    # Les lectures publiques restent anonymes : il faut le dire, sinon un
    # client suppose qu'un jeton est nécessaire pour consulter le corpus.
    assert "not** required to read entities" in description


def test_global_description_separates_the_two_read_contracts(
    schema: dict[str, Any],
) -> None:
    """A reader must not mistake the private route for the public one."""
    description = schema["info"]["description"]

    assert "/api/manage/entities/" in description
    assert "contributor" in description
    assert "reviewer" in description
    assert "administrator" in description
    # Les rôles viennent de la base, pas du jeton : c'est ce qui explique
    # qu'un changement de groupe agisse sans réémission.
    assert "never from a claim inside the token" in description
