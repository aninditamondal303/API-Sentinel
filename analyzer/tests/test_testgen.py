"""Contract-test generator: decisions, safety, and proof that generated suites really run."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from builders import get_spec, json_response, obj, op, param, post_spec, spec
from reference_server import VALID_TOKEN, running_server

from apisentinel.engine import SpecInput, load_spec
from apisentinel.testgen import (
    TEMPLATE_FILES,
    GeneratedSuite,
    GenerationOptions,
    generate_contract_tests,
    write_suite,
)

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "examples" / "inventory-api" / "openapi.yaml"
TEMPLATES = Path(__file__).resolve().parents[1] / "src/apisentinel/templates/contract_tests"
Json = dict[str, Any]


def generate(doc: Json | Path, **options: Any) -> GeneratedSuite:
    if isinstance(doc, Path):
        data, name = doc.read_bytes(), doc.name
    else:
        data, name = json.dumps(doc).encode(), "spec.json"
    return generate_contract_tests(load_spec(SpecInput(data, name)), GenerationOptions(**options))


def by_id(suite: GeneratedSuite) -> dict[str, Json]:
    return {o["id"]: o for o in suite.operations}


def run_suite(
    directory: Path, base_url: str | None, token: str | None = None
) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("APISENTINEL_")}
    if token:
        env["APISENTINEL_AUTH_TOKEN"] = token
    args = [sys.executable, "-m", "pytest", str(directory), "-p", "no:cacheprovider", "-q"]
    if base_url:
        args += ["--base-url", base_url]
    return subprocess.run(args, capture_output=True, text=True, env=env, cwd=directory,
                          check=False, timeout=120)  # fmt: skip


def outcome_counts(output: str) -> dict[str, int]:
    last = output.strip().splitlines()[-1]
    return {word: int(n) for n, word in re.findall(r"(\d+) (passed|failed|skipped|error)", last)}


# ------------------------------------------------------- the suite really runs
def test_generated_suite_passes_against_a_conforming_server(tmp_path: Path) -> None:
    write_suite(generate(INVENTORY, include_unsafe_methods=True), tmp_path)
    with running_server("correct") as url:
        proc = run_suite(tmp_path, url, token=VALID_TOKEN)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    # 6 ready operations pass; GET /search is skipped (no example for required 'q').
    assert outcome_counts(proc.stdout) == {"passed": 6, "skipped": 1}
    assert "required query parameter 'q' has no example" in proc.stdout


def test_generated_suite_fails_against_a_violating_server(tmp_path: Path) -> None:
    write_suite(generate(INVENTORY), tmp_path)
    with running_server("broken") as url:
        proc = run_suite(tmp_path, url, token=VALID_TOKEN)
    assert proc.returncode == 1
    out = proc.stdout
    assert "GET /health: expected status 200, got 503" in out
    assert "at /items/0/price: '42.00' is not of type 'number'" in out
    assert "'name' is a required property" in out
    assert "at /0/quantity: -5 is less than the minimum of 0" in out
    assert outcome_counts(out)["failed"] == 4


def test_authenticated_operations_skip_without_token(tmp_path: Path) -> None:
    write_suite(generate(INVENTORY), tmp_path)
    with running_server("correct") as url:
        proc = run_suite(tmp_path, url, token=None)
    assert proc.returncode == 0
    assert "requires authentication (scheme 'bearerAuth')" in proc.stdout


def test_missing_base_url_is_a_clear_usage_error(tmp_path: Path) -> None:
    write_suite(generate(INVENTORY), tmp_path)
    proc = run_suite(tmp_path, None)
    assert proc.returncode == 4  # pytest's usage-error exit code
    assert "No base URL configured" in proc.stderr


def test_unreachable_server_fails_with_message(tmp_path: Path) -> None:
    write_suite(generate(INVENTORY), tmp_path)
    proc = run_suite(tmp_path, "http://127.0.0.1:9")  # discard port: nothing listens
    assert proc.returncode == 1
    assert "Could not reach http://127.0.0.1:9" in proc.stdout


# -------------------------------------------------------------- code safety
def test_spec_content_cannot_inject_code(tmp_path: Path) -> None:
    payload = '"""; import pathlib; pathlib.Path("PWNED").write_text("x"); """'
    doc = get_spec(op(operationId=payload, summary=payload,
                      parameters=[param("q", required=True, example=payload)]),
                   path="/items")  # fmt: skip
    doc["info"]["title"] = payload
    suite = generate(doc)
    for name in TEMPLATE_FILES:  # generated code is byte-identical to the shipped templates
        assert suite.files[name] == (TEMPLATES / f"{name}.template").read_text()
    write_suite(suite, tmp_path)
    with running_server("correct") as url:
        run_suite(tmp_path, url)
    assert not (tmp_path / "PWNED").exists()
    assert json.loads(suite.files["operations.json"])["operations"][0]["operationId"] == payload


def test_write_suite_refuses_to_overwrite(tmp_path: Path) -> None:
    suite = generate(INVENTORY)
    (tmp_path / "notes.txt").write_text("mine")
    write_suite(suite, tmp_path)
    with pytest.raises(FileExistsError):
        write_suite(suite, tmp_path)
    write_suite(suite, tmp_path, overwrite=True)
    assert (tmp_path / "notes.txt").read_text() == "mine"


# ------------------------------------------------------- generation decisions
def test_unsafe_methods_skipped_by_default() -> None:
    ops = by_id(generate(INVENTORY))
    assert ops["POST /products"]["status"] == "skipped"
    assert ops["POST /products"]["requiresAuth"] is True  # known even when skipped
    assert ops["GET /health"]["requiresAuth"] is False
    assert "changes server state" in ops["POST /products"]["skipReason"]
    assert by_id(generate(INVENTORY, include_unsafe_methods=True))["POST /products"]["status"] == (
        "ready"
    )


def test_input_sources_are_recorded() -> None:
    ops = by_id(generate(INVENTORY, include_unsafe_methods=True))
    assert ops["GET /products"]["inputSources"] == {"query.category": "first enum value"}
    assert ops["GET /products/{sku}"]["inputSources"] == {"path.sku": "example"}
    assert ops["GET /warehouses/{warehouseId}/stock"]["inputSources"] == {
        "path.warehouseId": "example 'pune'"
    }
    assert ops["POST /products"]["inputSources"] == {"body": "example"}
    assert ops["GET /products"]["request"]["query"] == {
        "category": {"value": "books", "style": "form", "explode": True}
    }  # optional 'limit' is omitted


def test_example_precedence() -> None:
    p = param("q", required=True, example="from-param",
              schema={"type": "string", "example": "from-schema", "default": "d"})  # fmt: skip
    assert (
        by_id(generate(get_spec(op(parameters=[p]))))["GET /items"]["request"]["query"]["q"][
            "value"
        ]
        == "from-param"
    )
    p2 = param("q", required=True, schema={"type": "string", "default": "e", "enum": ["d", "e"]})
    record = by_id(generate(get_spec(op(parameters=[p2]))))["GET /items"]
    assert record["inputSources"] == {"query.q": "schema default"}
    assert record["request"]["query"]["q"]["value"] == "e"  # default wins over first enum value


@pytest.mark.parametrize(
    ("doc", "reason"),
    [
        (get_spec(op(responses={"404": {"description": "nf"}})), "no documented 2xx response"),
        (post_spec(op(requestBody={"required": True, "content": {"application/json": {
            "schema": obj({"a": {"type": "string"}})}}})), "changes server state"),
        (get_spec(op(parameters=[param("q", required=True)])), "has no example"),
        (get_spec(op(parameters=[param("f", required=True, example={"a": 1})])),
         "object-valued query parameter"),
        (get_spec(op(security=[{"mtls": []}]),
                  components={"securitySchemes": {"mtls": {"type": "mutualTLS"}}}),
         "authentication not supported"),
    ],
)  # fmt: skip
def test_honest_skip_reasons(doc: Json, reason: str) -> None:
    record = generate(doc).operations[0]
    assert record["status"] == "skipped"
    assert reason in record["skipReason"]


def test_required_body_without_example_is_skipped_even_when_unsafe_allowed() -> None:
    doc = post_spec(op(requestBody={"required": True, "content": {"application/json": {
        "schema": obj({"a": {"type": "string"}})}}}))  # fmt: skip
    record = generate(doc, include_unsafe_methods=True).operations[0]
    assert record["skipReason"] == "required request body has no example in the specification"


def test_openapi_30_nullable_is_converted_for_validation() -> None:
    doc = get_spec(op(responses=json_response(obj({"a": {"type": "string", "nullable": True,
                                                         "enum": ["x"]}}))), version="3.0.3")  # fmt: skip
    schema = generate(doc).operations[0]["responseSchemas"]["200"]["allOf"][0]
    assert schema["properties"]["a"] == {"type": ["string", "null"], "enum": ["x", None]}


def test_write_only_required_property_is_not_required_in_responses() -> None:
    doc = get_spec(op(responses=json_response(
        obj({"id": {"type": "string"}, "pw": {"type": "string", "writeOnly": True}},
            ["id", "pw"]))))  # fmt: skip
    schema = generate(doc).operations[0]["responseSchemas"]["200"]["allOf"][0]
    assert schema["required"] == ["id"]


def test_non_json_response_is_status_only_with_note() -> None:
    ops = by_id(generate(INVENTORY))
    csv = ops["GET /reports/stock.csv"]
    assert csv["status"] == "ready"
    assert csv["responseSchemas"] == {}
    assert csv["notes"] == ["response 200 body not validated (non-JSON media type)"]


def test_base_url_default_is_optional_and_stored_as_data() -> None:
    suite = generate(INVENTORY, default_base_url="http://localhost:8080")
    assert json.loads(suite.files["operations.json"])["defaultBaseUrl"] == "http://localhost:8080"
    assert suite.files["conftest.py"] == (TEMPLATES / "conftest.py.template").read_text()


def test_generation_is_deterministic() -> None:
    assert generate(INVENTORY).files == generate(INVENTORY).files


@pytest.mark.parametrize("name", sorted(p.name for p in (ROOT / "analyzer/tests/fixtures/real")
                                        .glob("*.yaml")))  # fmt: skip
def test_generator_handles_every_real_spec(name: str) -> None:
    suite = generate(ROOT / "analyzer/tests/fixtures/real" / name)
    assert suite.summary()["total"] == len(suite.operations)
    for record in suite.operations:
        assert (record["status"] == "ready") == (record["skipReason"] is None)


def test_minimal_spec_without_paths_generates_empty_suite() -> None:
    assert generate(spec({})).operations == []
