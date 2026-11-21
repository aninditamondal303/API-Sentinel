from __future__ import annotations

import copy
from typing import Any

import pytest

from apisentinel.errors import SpecValidationError
from apisentinel.validation import validate_document

BASE: dict[str, Any] = {
    "openapi": "3.1.0",
    "info": {"title": "Pets", "version": "1.2.0"},
    "paths": {
        "/pets/{id}": {
            "get": {
                "parameters": [
                    {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/Pet"}}
                        },
                    }
                },
            },
            "delete": {
                "parameters": [
                    {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "responses": {"204": {"description": "gone"}},
            },
        }
    },
    "components": {
        "schemas": {"Pet": {"type": "object", "properties": {"id": {"type": "string"}}}}
    },
}


def spec(**changes: Any) -> dict[str, Any]:
    doc = copy.deepcopy(BASE)
    doc.update(changes)
    return doc


@pytest.mark.parametrize("version", ["3.0.3", "3.1.0", "3.1.1"])
def test_valid_documents_report_their_facts(version: str) -> None:
    info = validate_document(spec(openapi=version))
    assert info.openapi_version == version
    assert info.title == "Pets"
    assert info.api_version == "1.2.0"
    assert info.operation_count == 2


@pytest.mark.parametrize(
    ("doc", "code"),
    [
        ({"swagger": "2.0", "info": {}, "paths": {}}, "UNSUPPORTED_OPENAPI_VERSION"),
        (spec(openapi="3.2.0"), "UNSUPPORTED_OPENAPI_VERSION"),
        (spec(openapi="4.0"), "UNSUPPORTED_OPENAPI_VERSION"),
        (spec(openapi=3.1), "SPEC_INVALID"),
    ],
)
def test_rejects_unsupported_versions(doc: dict[str, Any], code: str) -> None:
    with pytest.raises(SpecValidationError) as info:
        validate_document(doc)
    assert info.value.code == code


@pytest.mark.parametrize(
    "ref",
    [
        "https://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "other.yaml#/components/schemas/Pet",
    ],
)
def test_external_references_are_rejected_without_fetching(ref: str) -> None:
    doc = spec()
    doc["components"]["schemas"]["Pet"] = {"$ref": ref}
    with pytest.raises(SpecValidationError) as info:
        validate_document(doc)
    assert info.value.issues[0].pointer == "/components/schemas/Pet/$ref"
    assert "not allowed" in info.value.issues[0].message


def test_dangling_local_reference_is_reported_with_pointer() -> None:
    doc = spec()
    doc["components"]["schemas"] = {}
    with pytest.raises(SpecValidationError) as info:
        validate_document(doc)
    issue = info.value.issues[0]
    assert issue.pointer == (
        "/paths/~1pets~1{id}/get/responses/200/content/application~1json/schema/$ref"
    )
    assert "does not resolve" in issue.message


def test_schema_violations_are_reported() -> None:
    doc = spec()
    doc["paths"]["/pets/{id}"]["get"]["parameters"][0]["in"] = "body"
    with pytest.raises(SpecValidationError) as info:
        validate_document(doc)
    assert info.value.code == "SPEC_INVALID"
    assert info.value.issues


def test_undeclared_path_parameter_is_invalid_in_30() -> None:
    doc = spec(openapi="3.0.3")
    del doc["paths"]["/pets/{id}"]["delete"]["parameters"]
    with pytest.raises(SpecValidationError):
        validate_document(doc)
