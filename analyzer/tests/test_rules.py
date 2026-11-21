"""Every catalog rule must fire on its positive case and stay silent on a near-miss.

Each case is a real, valid OpenAPI document pair (validated by
openapi-spec-validator inside ``analyze``). ``test_every_rule_has_cases`` fails
if a rule is added to the catalog without both cases here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from builders import (
    OK,
    get_spec,
    json_body,
    json_response,
    obj,
    op,
    param,
    post_spec,
    rule_ids,
    run,
    spec,
)

from apisentinel.rules import RULES, Category

Json = dict[str, Any]
STR = {"type": "string"}
INT = {"type": "integer"}


@dataclass(frozen=True)
class Case:
    rule: str
    positive: tuple[Json, Json]
    negative: tuple[Json, Json]


def q(**extra: Any) -> Json:
    """GET /items with one query parameter 'q' customised by ``extra``."""
    return get_spec(op(parameters=[param("q", **extra)]))


def q_schema(schema: Json, **extra: Any) -> Json:
    return q(schema=schema, **extra)


def req(schema: Json, **body: Any) -> Json:
    return post_spec(op(requestBody=json_body(schema, **body)))


def res(schema: Json, status: str = "200", media: str = "application/json") -> Json:
    return get_spec(op(responses=json_response(schema, status, media)))


def secured(security: list[Json] | None, **kwargs: Any) -> Json:
    operation = op() if security is None else op(security=security)
    schemes = {
        "bearer": {"type": "http", "scheme": "bearer"},
        "apiKey": {"type": "apiKey", "in": "header", "name": "X-API-Key"},
        "oauth": {
            "type": "oauth2",
            "flows": {
                "clientCredentials": {
                    "tokenUrl": "https://auth.example.com/token",
                    "scopes": {"read": "read", "write": "write"},
                }
            },
        },
    }
    return get_spec(operation, components={"securitySchemes": schemes}, **kwargs)


def variants(keyword: str, names: list[str], direction: str) -> Json:
    schemas = {n: obj({"kind": STR}) for n in ("A", "B", "C")}
    schema = {keyword: [{"$ref": f"#/components/schemas/{n}"} for n in names]}
    operation = (
        op(responses=json_response(schema)) if direction == "response"
        else op(requestBody=json_body(schema))
    )  # fmt: skip
    method = "get" if direction == "response" else "post"
    return spec({"/items": {method: operation}}, components={"schemas": schemas})


def ref_chain(length: int, leaf: Json) -> Json:
    schemas: Json = {}
    for i in range(length):
        schemas[f"S{i}"] = obj({"next": {"$ref": f"#/components/schemas/S{i + 1}"}})
    schemas[f"S{length}"] = obj({"value": leaf})
    return get_spec(
        op(responses=json_response({"$ref": "#/components/schemas/S0"})),
        components={"schemas": schemas},
    )


two_paths = spec({"/a": {"get": op()}, "/b": {"get": op()}})
one_path = spec({"/a": {"get": op()}})
get_and_post = spec({"/a": {"get": op(), "post": op()}})
deprecated_b = spec({"/a": {"get": op()}, "/b": {"get": op(deprecated=True)}})
by_id = spec({"/a/{id}": {"get": op(parameters=[param("id", "path")])}})
by_item_id = spec({"/a/{itemId}": {"get": op(parameters=[param("itemId", "path")])}})
object_query = {"type": "object", "properties": {"x": STR}}

CASES: list[Case] = [
    # Operations
    Case("OP-001", (two_paths, one_path), (get_and_post, one_path)),
    Case("OP-002", (get_and_post, one_path), (two_paths, one_path)),
    Case("OP-003", (deprecated_b, one_path), (two_paths, one_path)),
    Case("OP-004", (one_path, spec({"/a": {"get": op(deprecated=True)}})),
         (deprecated_b, deprecated_b)),
    Case("OP-005", (by_id, by_item_id), (by_id, by_id)),
    Case("OP-006", (one_path, two_paths), (one_path, one_path)),
    # Request parameters
    Case("REQ-PARAM-001", (q(), get_spec(op())), (q(), q())),
    Case("REQ-PARAM-002", (get_spec(op()), q(required=True)), (get_spec(op()), q())),
    Case("REQ-PARAM-003", (q(), q(required=True)), (q(required=True), q())),
    Case("REQ-PARAM-004", (q_schema(STR), q_schema(INT)),
         (q_schema(INT), q_schema({"type": "number"}))),
    Case("REQ-PARAM-005",
         (q_schema({"type": "string", "enum": ["a", "b"]}), q_schema({"type": "string", "enum": ["a"]})),
         (q_schema({"type": "string", "enum": ["a"]}), q_schema({"type": "string", "enum": ["a", "b"]}))),
    Case("REQ-PARAM-006",
         (q_schema({"type": "string", "maxLength": 10}), q_schema({"type": "string", "maxLength": 5})),
         (q_schema({"type": "string", "maxLength": 5}), q_schema({"type": "string", "maxLength": 10}))),
    Case("REQ-PARAM-007",
         (q_schema({"type": "array", "items": STR}),
          q_schema({"type": "array", "items": STR}, style="spaceDelimited", explode=False)),
         (q_schema({"type": "array", "items": STR}),
          q_schema({"type": "array", "items": STR}, style="form", explode=True))),
    Case("REQ-PARAM-008",
         (q_schema({"type": "integer", "default": 10}), q_schema({"type": "integer", "default": 20})),
         (q_schema(INT), q_schema({"type": "integer", "default": 20}))),
    Case("REQ-PARAM-009",
         (q_schema({"type": "string", "pattern": "^a"}), q_schema({"type": "string", "pattern": "^b"})),
         (q_schema({"type": "string", "pattern": "^a"}), q_schema(STR))),
    Case("REQ-PARAM-010", (get_spec(op()), q()), (get_spec(op()), q(required=True))),
    Case("REQ-PARAM-011",
         (q_schema(STR), q_schema({"type": "string", "format": "date"})),
         (q_schema({"type": "string", "format": "date"}), q_schema(STR))),
    Case("REQ-PARAM-012",
         (q_schema(object_query, style="deepObject"),
          q_schema({**object_query, "required": ["x"]}, style="deepObject")),
         (q_schema(object_query, style="deepObject"), q_schema(object_query, style="deepObject"))),
    # Request bodies
    Case("REQ-BODY-001", (req(obj({"a": STR}), required=False), req(obj({"a": STR}))),
         (req(obj({"a": STR})), req(obj({"a": STR}), required=False))),
    Case("REQ-BODY-002",
         (req(obj({"a": STR})), req(obj({"a": STR}), media="application/xml")),
         (req(obj({"a": STR})), req(obj({"a": STR}), media="application/json; charset=utf-8"))),
    Case("REQ-BODY-003", (req(obj({"a": STR})), req(obj({"a": STR, "b": STR}, ["b"]))),
         (req(obj({"a": STR})), req(obj({"a": STR, "b": STR})))),
    Case("REQ-BODY-004", (req(obj({"a": STR})), req(obj({"a": STR}, ["a"]))),
         (req(obj({"a": STR}, ["a"])), req(obj({"a": STR})))),
    Case("REQ-BODY-005",
         (req(obj({"a": STR, "b": STR})), req(obj({"a": STR}, additionalProperties=False))),
         (req(obj({"a": STR, "b": STR})), req(obj({"a": STR})))),
    Case("REQ-BODY-006", (req(obj({"a": STR, "b": STR})), req(obj({"a": STR}))),
         (req(obj({"a": STR, "b": STR})), req(obj({"a": STR}, additionalProperties=False)))),
    Case("REQ-BODY-007", (req(obj({"a": STR})), req(obj({"a": INT}))),
         (req(obj({"a": INT})), req(obj({"a": {"type": "number"}})))),
    Case("REQ-BODY-008",
         (req(obj({"a": {"type": "string", "format": "date-time"}})),
          req(obj({"a": {"type": "string", "format": "date"}}))),
         (req(obj({"a": {"type": "string", "format": "date-time"}})), req(obj({"a": STR})))),
    Case("REQ-BODY-009",
         (req(obj({"a": {"enum": ["x", "y"]}})), req(obj({"a": {"enum": ["x"]}}))),
         (req(obj({"a": {"enum": ["x"]}})), req(obj({"a": {"enum": ["x", "y"]}})))),
    Case("REQ-BODY-010",
         (req(obj({"a": {"type": "integer", "minimum": 0}})),
          req(obj({"a": {"type": "integer", "minimum": 1}}))),
         (req(obj({"a": {"type": "integer", "minimum": 1}})),
          req(obj({"a": {"type": "integer", "minimum": 0}})))),
    Case("REQ-BODY-011", (req(obj({"a": STR})), req(obj({"a": STR}, additionalProperties=False))),
         (req(obj({"a": STR}, additionalProperties=False)), req(obj({"a": STR})))),
    Case("REQ-BODY-012", (req(obj({"a": STR})), req(obj({"a": STR, "b": STR}))),
         (req(obj({"a": STR})), req(obj({"a": STR, "b": STR}, ["b"])))),
    Case("REQ-BODY-013",
         (req(obj({"a": {"type": "string", "pattern": "^[a-z]+$"}})),
          req(obj({"a": {"type": "string", "pattern": "^[a-z]{1,5}$"}}))),
         (req(obj({"a": {"type": "string", "pattern": "^[a-z]+$"}})), req(obj({"a": STR})))),
    Case("REQ-BODY-014",
         (req(obj({"a": {"type": "string", "default": "x"}})),
          req(obj({"a": {"type": "string", "default": "y"}}))),
         (req(obj({"a": {"type": "string", "default": "x"}})),
          req(obj({"a": {"type": "string", "default": "x"}})))),
    Case("REQ-BODY-015", (req(obj({"a": STR})), post_spec(op())),
         (req(obj({"a": STR})), req(obj({"a": STR}), required=False))),
    # Responses
    Case("RES-001",
         (get_spec(op()), get_spec(op(responses={"201": {"description": "created"}}))),
         (get_spec(op()), get_spec(op(responses={"2XX": {"description": "any success"}})))),
    Case("RES-002",
         (get_spec(op(responses={**OK, "404": {"description": "nf"}})), get_spec(op())),
         (get_spec(op()), get_spec(op(responses={"201": {"description": "created"}})))),
    Case("RES-003",
         (get_spec(op()), get_spec(op(responses={**OK, "202": {"description": "accepted"}}))),
         (get_spec(op()), get_spec(op(responses={**OK, "404": {"description": "nf"}})))),
    Case("RES-004",
         (res(obj({"a": STR})), res(obj({"a": STR}), media="application/xml")),
         (res(obj({"a": STR})), res(obj({"a": STR}), media="application/*"))),
    Case("RES-005", (res(obj({"a": STR, "b": STR})), res(obj({"a": STR}))),
         (res(obj({"a": STR})), res(obj({"a": STR, "b": STR})))),
    Case("RES-006", (res(obj({"a": STR}, ["a"])), res(obj({"a": STR}))),
         (res(obj({"a": STR})), res(obj({"a": STR}, ["a"])))),
    Case("RES-007", (res(obj({"a": INT})), res(obj({"a": STR}))),
         (res(obj({"a": {"type": "number"}})), res(obj({"a": INT})))),
    Case("RES-008", (res(obj({"a": STR})), res(obj({"a": {"type": ["string", "null"]}}))),
         (res(obj({"a": {"type": ["string", "null"]}})), res(obj({"a": STR})))),
    Case("RES-009",
         (res(obj({"s": {"type": "string", "enum": ["a", "b"]}})),
          res(obj({"s": {"type": "string", "enum": ["a", "b", "c"]}}))),
         (res(obj({"s": {"type": "string", "enum": ["a", "b"]}})),
          res(obj({"s": {"type": "string", "enum": ["a"]}})))),
    Case("RES-010",
         (res(obj({"s": {"type": "string", "enum": ["a", "b"]}})),
          res(obj({"s": {"type": "string", "enum": ["a"]}}))),
         (res(obj({"s": {"type": "string", "enum": ["a"]}})),
          res(obj({"s": {"type": "string", "enum": ["a", "b"]}})))),
    Case("RES-011", (res(obj({"a": STR})), res({"type": "array", "items": obj({"a": STR})})),
         (res(obj({"a": INT})), res(obj({"a": STR})))),
    Case("RES-012",
         (res(obj({"d": {"type": "string", "format": "date-time"}})),
          res(obj({"d": {"type": "string", "format": "date"}}))),
         (res(obj({"d": STR})), res(obj({"d": {"type": "string", "format": "date"}})))),
    Case("RES-013", (res(obj({"a": STR})), res(obj({"a": STR, "b": STR}))),
         (res(obj({"a": STR, "b": STR})), res(obj({"a": STR})))),
    Case("RES-014",
         (res(obj({"a": {"type": "string", "maxLength": 10}})),
          res(obj({"a": {"type": "string", "maxLength": 20}}))),
         (res(obj({"a": {"type": "string", "maxLength": 20}})),
          res(obj({"a": {"type": "string", "maxLength": 10}})))),
    Case("RES-015",
         (res(obj({"a": {"type": "string", "pattern": "^a"}})),
          res(obj({"a": {"type": "string", "pattern": "^b"}}))),
         (res(obj({"a": STR})), res(obj({"a": {"type": "string", "pattern": "^b"}})))),
    # Authentication and security regressions
    Case("AUTH-001", (secured(None), secured([{"bearer": []}])),
         (secured([{"bearer": []}]), secured([{"bearer": []}]))),
    Case("AUTH-002", (secured([{"apiKey": []}]), secured([{"bearer": []}])),
         (secured([{"apiKey": []}]), secured([{"apiKey": []}, {"bearer": []}]))),
    Case("AUTH-003", (secured([{"oauth": ["read"]}]), secured([{"oauth": ["read", "write"]}])),
         (secured([{"oauth": ["read", "write"]}]), secured([{"oauth": ["read"]}]))),
    Case("SEC-R001", (secured([{"bearer": []}]), secured([])),
         (secured([{"bearer": []}]), secured([{"bearer": []}]))),
    Case("SEC-R002", (secured([{"bearer": []}]), secured([{"bearer": []}, {}])),
         (secured([{"bearer": []}]), secured([{"bearer": [], "apiKey": []}]))),
    Case("SEC-R003", (secured([{"oauth": ["read", "write"]}]), secured([{"oauth": ["read"]}])),
         (secured([{"oauth": ["read"]}]), secured([{"oauth": ["read", "write"]}]))),
    Case("SEC-R004",
         (get_spec(op(), servers=[{"url": "https://api.example.com"}]),
          get_spec(op(), servers=[{"url": "http://api.example.com"}])),
         (get_spec(op(), servers=[{"url": "https://api.example.com"}]),
          get_spec(op(), servers=[{"url": "https://api2.example.com"}]))),
    # Manual review
    Case("MR-001", (variants("oneOf", ["A", "B"], "response"), variants("oneOf", ["A", "B", "C"], "response")),
         (variants("oneOf", ["A", "B"], "request"), variants("oneOf", ["A", "B", "C"], "request"))),
    Case("MR-002",
         (req(obj({"a": {"type": "string", "not": {"const": "x"}}})),
          req(obj({"a": {"type": "string", "not": {"const": "y"}}}))),
         (req(obj({"a": {"type": "string", "description": "old"}})),
          req(obj({"a": {"type": "string", "description": "new"}})))),
    Case("MR-003",
         (res({"oneOf": [obj({"kind": STR})], "discriminator": {"propertyName": "kind"}}),
          res({"oneOf": [obj({"kind": STR})], "discriminator": {"propertyName": "type"}})),
         (res({"oneOf": [obj({"kind": STR})], "discriminator": {"propertyName": "kind"}}),
          res({"oneOf": [obj({"kind": STR})], "discriminator": {"propertyName": "kind"}}))),
    Case("MR-004", (ref_chain(70, STR), ref_chain(70, INT)), (ref_chain(70, STR), ref_chain(70, STR))),
]  # fmt: skip


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.rule)
def test_rule_fires_on_positive_case(case: Case) -> None:
    result = run(*case.positive)
    assert case.rule in rule_ids(result), result["findings"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.rule)
def test_rule_silent_on_negative_case(case: Case) -> None:
    result = run(*case.negative)
    assert case.rule not in rule_ids(result), result["findings"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.rule)
def test_finding_fields_are_complete(case: Case) -> None:
    result = run(*case.positive)
    finding = next(f for f in result["findings"] if f["ruleId"] == case.rule)
    rule = RULES[case.rule]
    assert finding["severity"] == rule.severity.name
    assert finding["requiresManualReview"] is rule.manual_review
    assert finding["location"].startswith("/")
    for text in ("message", "impact", "remediation"):
        assert finding[text], text
        assert "'?'" not in finding[text] and " ? " not in finding[text], finding[text]
        assert not finding[text].endswith("?."), finding[text]
    assert len(finding["fingerprint"]) == 16


def test_every_rule_has_cases() -> None:
    """Every diff rule is covered here; SPEC_HYGIENE rules are covered in test_hygiene.py."""
    diff_rules = {r.id for r in RULES.values() if r.category is not Category.SPEC_HYGIENE}
    covered = [c.rule for c in CASES]
    assert len(covered) == len(set(covered)), "duplicate case"
    assert set(covered) == diff_rules, sorted(diff_rules ^ set(covered))
