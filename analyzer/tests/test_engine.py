"""Engine behaviour beyond single rules: real specs, invariants, versions, policy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from builders import get_spec, json_body, json_response, obj, op, post_spec, rule_ids, run, spec
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from apisentinel.engine import FailurePolicy, InputError, SpecInput, analyze
from apisentinel.rules import Severity

REAL = Path(__file__).parent / "fixtures" / "real"
REAL_SPECS = sorted(p.name for p in REAL.glob("*.yaml"))
STR = {"type": "string"}


def load_real(name: str) -> SpecInput:
    return SpecInput((REAL / name).read_bytes(), name)


# ------------------------------------------------------------- real documents
@pytest.mark.parametrize("name", REAL_SPECS)
def test_real_spec_compared_with_itself_has_no_findings(name: str) -> None:
    result = analyze(load_real(name), load_real(name))
    assert result["findings"] == []
    assert result["decision"]["result"] == "PASS"


def test_real_petstore_commit_9fb97b1_is_detected_exactly() -> None:
    """Upstream commit made two optional query params required; nothing else changed."""
    result = analyze(
        load_real("petstore-v3-before-9fb97b1.yaml"), load_real("petstore-v3-after-9fb97b1.yaml")
    )
    found = sorted((f["ruleId"], f["method"], f["path"], f["field"]) for f in result["findings"])
    assert found == [
        ("REQ-PARAM-003", "GET", "/pet/findByStatus", "query.status"),
        ("REQ-PARAM-003", "GET", "/pet/findByTags", "query.tags"),
    ]
    assert result["decision"]["result"] == "FAIL"


def test_reformatting_real_spec_as_json_changes_nothing() -> None:
    data = yaml.safe_load((REAL / "swagger-petstore-latest.yaml").read_text())
    as_json = SpecInput(json.dumps(data, indent=1).encode(), "petstore.json")
    assert analyze(load_real("swagger-petstore-latest.yaml"), as_json)["findings"] == []


def test_output_is_deterministic() -> None:
    first = analyze(load_real("petstore.yaml"), load_real("petstore-expanded.yaml"))
    second = analyze(load_real("petstore.yaml"), load_real("petstore-expanded.yaml"))
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


# ------------------------------------------------------------- 3.0 vs 3.1
def test_nullable_30_equals_type_array_31() -> None:
    old = get_spec(
        op(responses=json_response(obj({"a": {"type": "string", "nullable": True}}))),
        version="3.0.3",
    )
    new = get_spec(op(responses=json_response(obj({"a": {"type": ["string", "null"]}}))))
    assert run(old, new)["findings"] == []


def test_nullable_added_in_30_is_detected() -> None:
    old = get_spec(op(responses=json_response(obj({"a": STR}))), version="3.0.3")
    new = get_spec(
        op(responses=json_response(obj({"a": {"type": "string", "nullable": True}}))),
        version="3.0.3",
    )
    assert rule_ids(run(old, new)) == {"RES-008"}


def test_exclusive_minimum_30_boolean_equals_31_numeric() -> None:
    old = post_spec(
        op(
            requestBody=json_body(
                obj({"n": {"type": "integer", "minimum": 0, "exclusiveMinimum": True}})
            )
        ),
        version="3.0.3",
    )
    new = post_spec(
        op(requestBody=json_body(obj({"n": {"type": "integer", "exclusiveMinimum": 0}})))
    )
    assert run(old, new)["findings"] == []


# ------------------------------------------------------------- schema handling
def test_read_only_properties_are_ignored_in_requests() -> None:
    old = post_spec(op(requestBody=json_body(obj({"a": STR}))))
    new = post_spec(
        op(
            requestBody=json_body(
                obj({"a": STR, "id": {"type": "string", "readOnly": True}}, ["id"])
            )
        )
    )
    assert rule_ids(run(old, new)) == set()


def test_write_only_properties_are_ignored_in_responses() -> None:
    old = get_spec(
        op(responses=json_response(obj({"a": STR, "pw": {"type": "string", "writeOnly": True}})))
    )
    new = get_spec(op(responses=json_response(obj({"a": STR}))))
    assert rule_ids(run(old, new)) == set()


def test_recursive_schema_change_is_found_without_looping() -> None:
    def tree(leaf_type: str) -> dict[str, Any]:
        node = obj(
            {
                "value": {"type": leaf_type},
                "children": {"type": "array", "items": {"$ref": "#/components/schemas/Node"}},
            }
        )
        return get_spec(
            op(responses=json_response({"$ref": "#/components/schemas/Node"})),
            components={"schemas": {"Node": node}},
        )

    result = run(tree("string"), tree("integer"))
    assert [(f["ruleId"], f["field"]) for f in result["findings"]] == [
        ("RES-007", "response[200].value")
    ]
    assert result["findings"][0]["location"] == "/components/schemas/Node/properties/value"


def test_all_of_is_merged_before_comparison() -> None:
    def composed(required: list[str]) -> dict[str, Any]:
        base = obj({"id": STR})
        extra = obj({"name": STR}, required)
        schema = {"allOf": [{"$ref": "#/components/schemas/Base"}, extra]}
        return post_spec(op(requestBody=json_body(schema)), components={"schemas": {"Base": base}})

    assert rule_ids(run(composed([]), composed(["name"]))) == {"REQ-BODY-004"}


def test_unmergeable_all_of_change_needs_manual_review() -> None:
    def composed(min_len: int) -> dict[str, Any]:
        schema = {"allOf": [{"type": "string"}, {"minLength": min_len}]}
        return post_spec(op(requestBody=json_body(schema)))

    result = run(composed(1), composed(2))
    assert rule_ids(result) == {"MR-001"}
    assert result["findings"][0]["requiresManualReview"] is True


def test_shared_component_change_is_reported_per_endpoint() -> None:
    def api(prop_type: str) -> dict[str, Any]:
        response = json_response({"$ref": "#/components/schemas/Item"})
        return spec(
            {"/a": {"get": op(responses=response)}, "/b": {"get": op(responses=response)}},
            components={"schemas": {"Item": obj({"x": {"type": prop_type}})}},
        )

    paths = {f["path"] for f in run(api("string"), api("integer"))["findings"]}
    assert paths == {"/a", "/b"}


def test_path_level_parameter_is_overridden_by_operation_level() -> None:
    def api(op_required: bool) -> dict[str, Any]:
        return spec(
            {
                "/a": {
                    "parameters": [{"name": "q", "in": "query", "schema": STR}],
                    "get": op(
                        parameters=[
                            {"name": "q", "in": "query", "required": op_required, "schema": STR}
                        ]
                    ),
                }
            }
        )

    assert rule_ids(run(api(False), api(True))) == {"REQ-PARAM-003"}


def test_header_parameter_names_are_case_insensitive() -> None:
    def api(name: str) -> dict[str, Any]:
        return get_spec(op(parameters=[{"name": name, "in": "header", "schema": STR}]))

    assert run(api("X-Trace-Id"), api("x-trace-id"))["findings"] == []


# ------------------------------------------------------------- inputs and policy
def test_invalid_candidate_is_reported_with_its_side() -> None:
    good = json.dumps(get_spec(op())).encode()
    with pytest.raises(InputError) as info:
        analyze(SpecInput(good, "a.json"), SpecInput(b"openapi: [", "b.yaml"))
    assert info.value.side == "candidate"
    assert info.value.code == "SPEC_PARSE_ERROR"


def test_policy_thresholds() -> None:
    base = get_spec(op())
    removed = spec({"/other": {"get": op()}})  # OP-001 (CRITICAL) + OP-006 (INFO)
    assert run(base, removed)["decision"]["result"] == "FAIL"
    lenient = FailurePolicy(fail_on=None, fail_on_manual_review=False)
    assert run(base, removed, lenient)["decision"]["result"] == "PASS"
    info_only = run(spec({"/a": {"get": op()}}), spec({"/a": {"get": op()}, "/b": {"get": op()}}))
    assert info_only["decision"]["result"] == "PASS"
    strict = FailurePolicy(fail_on=Severity.INFO)
    assert (
        run(spec({"/a": {"get": op()}}), spec({"/a": {"get": op()}, "/b": {"get": op()}}), strict)[
            "decision"
        ]["result"]
        == "FAIL"
    )


def test_summary_counts_match_findings() -> None:
    result = run(get_spec(op()), spec({"/other": {"get": op()}}))
    summary = result["summary"]
    assert summary["total"] == len(result["findings"]) == 2
    assert summary["bySeverity"]["CRITICAL"] == 1
    assert summary["bySeverity"]["INFO"] == 1
    assert summary["breakingChanges"] == 1
    assert summary["endpointsAffected"] == 2


# ------------------------------------------------------------- property tests
_scalar = st.sampled_from([
    {"type": "string"}, {"type": "integer"}, {"type": "number"}, {"type": "boolean"},
    {"type": "string", "enum": ["a", "b"]}, {"type": "string", "format": "date"},
    {"type": "integer", "minimum": 0, "maximum": 10}, {"type": "string", "maxLength": 5},
])  # fmt: skip
_names = st.sampled_from(["id", "name", "tags", "price", "owner"])
_schema = st.recursive(
    _scalar,
    lambda children: st.one_of(
        st.builds(lambda item: {"type": "array", "items": item}, children),
        st.dictionaries(_names, children, max_size=4).flatmap(
            lambda props: st.builds(
                lambda req: obj(props, sorted(req)) if req else obj(props),
                st.sets(st.sampled_from(sorted(props)) if props else st.nothing(), max_size=2)
                if props
                else st.just(set()),
            )
        ),
    ),
    max_leaves=10,
)


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(request=_schema, response=_schema)
def test_any_spec_compared_with_itself_has_no_findings(
    request: dict[str, Any], response: dict[str, Any]
) -> None:
    doc = spec(
        {"/x": {"post": op(requestBody=json_body(request), responses=json_response(response))}}
    )
    assert run(doc, doc)["findings"] == []


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(response=_schema)
def test_yaml_and_json_forms_are_equivalent(response: dict[str, Any]) -> None:
    doc = get_spec(op(responses=json_response(response)))
    as_yaml = SpecInput(yaml.safe_dump(doc, sort_keys=False).encode(), "x.yaml")
    as_json = SpecInput(json.dumps(doc).encode(), "x.json")
    assert analyze(as_yaml, as_json)["findings"] == []
