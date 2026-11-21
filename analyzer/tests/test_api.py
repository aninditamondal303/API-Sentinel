"""HTTP service tests: contracts, status codes, auth, limits, logs, engine parity."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import SecretStr
from reference_server import VALID_TOKEN, running_server

from apisentinel.api.app import create_app
from apisentinel.api.contract import build_contract
from apisentinel.api.observability import RequestContextMiddleware
from apisentinel.api.settings import ConfigurationError, Settings, load_settings
from apisentinel.engine import SpecInput, analyze
from apisentinel.rules import RULES

ROOT = Path(__file__).resolve().parents[2]
ORDERS = ROOT / "examples" / "orders-api"
INVENTORY = ROOT / "examples" / "inventory-api" / "openapi.yaml"
REAL = Path(__file__).parent / "fixtures" / "real"
TOKEN = "test-internal-token-" + "0123456789abcdef" * 2
AUTH = {"X-Internal-Token": TOKEN}


def make_client(**overrides: Any) -> TestClient:
    settings = Settings(internal_token=SecretStr(TOKEN), **overrides)
    return TestClient(create_app(settings), raise_server_exceptions=False)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with make_client() as c:
        yield c


def spec(path: Path) -> dict[str, str]:
    return {"content": path.read_text(), "filename": path.name}


def analysis_body(baseline: Path, candidate: Path, **options: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"baseline": spec(baseline), "candidate": spec(candidate)}
    if options:
        body["options"] = options
    return body


def assert_problem(response: Any, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    body: dict[str, Any] = response.json()
    assert body["status"] == status
    assert body["errorCode"] == code
    assert body["requestId"] == response.headers["x-request-id"]
    return body


# ---------------------------------------------------------------- health
def test_health_endpoints_need_no_token(client: TestClient) -> None:
    assert client.get("/health/live").json()["status"] == "ok"
    ready = client.get("/health/ready").json()
    assert ready == {"status": "ready", "analyzerVersion": "0.1.0", "rulesetVersion": "2026.11"}


# ------------------------------------------------------------------ auth
@pytest.mark.parametrize("headers", [{}, {"X-Internal-Token": "wrong"}, {"X-Internal-Token": ""}])
def test_internal_endpoints_require_the_token(client: TestClient, headers: dict[str, str]) -> None:
    response = client.post("/internal/v1/analyses", headers=headers, json={})
    body = assert_problem(response, 401, "UNAUTHENTICATED")
    assert response.headers["www-authenticate"] == "X-Internal-Token"
    assert TOKEN not in response.text and TOKEN not in json.dumps(body)


def test_rules_endpoint_also_requires_token(client: TestClient) -> None:
    assert_problem(client.get("/internal/v1/rules"), 401, "UNAUTHENTICATED")
    rules = client.get("/internal/v1/rules", headers=AUTH).json()
    assert {r["id"] for r in rules["rules"]} == set(RULES)
    assert {r["category"] for r in rules["rules"]} == {
        "COMPATIBILITY", "SECURITY_REGRESSION", "SPEC_HYGIENE"
    }  # fmt: skip


# ------------------------------------------------------------- analyses
def test_analysis_response_is_exactly_the_engine_result(client: TestClient) -> None:
    """The service adds no logic: its JSON equals analyze() called directly."""
    base, cand = ORDERS / "baseline.yaml", ORDERS / "candidate-breaking.yaml"
    response = client.post("/internal/v1/analyses", headers=AUTH, json=analysis_body(base, cand))
    assert response.status_code == 200
    direct = analyze(
        SpecInput(base.read_bytes(), base.name), SpecInput(cand.read_bytes(), cand.name)
    )
    assert response.json() == json.loads(json.dumps(direct))
    assert response.json()["decision"]["result"] == "FAIL"


def test_analysis_accepts_json_and_yaml_inputs(client: TestClient) -> None:
    data = yaml.safe_load((ORDERS / "baseline.yaml").read_text())
    body = {
        "baseline": {"content": json.dumps(data), "filename": "baseline.json"},
        "candidate": spec(ORDERS / "baseline.yaml"),
    }
    response = client.post("/internal/v1/analyses", headers=AUTH, json=body)
    assert response.status_code == 200
    assert response.json()["findings"] == []


def test_analysis_options_change_only_the_decision(client: TestClient) -> None:
    body = analysis_body(ORDERS / "baseline.yaml", ORDERS / "candidate-breaking.yaml",
                         failOn=None, failOnManualReview=False)  # fmt: skip
    result = client.post("/internal/v1/analyses", headers=AUTH, json=body).json()
    assert result["decision"] == {"result": "PASS", "reasons": [], "failOn": None,
                                  "failOnManualReview": False}  # fmt: skip
    assert result["summary"]["total"] == 17


def test_invalid_candidate_is_422_with_side_and_pointer(client: TestClient) -> None:
    broken = (
        "openapi: 3.1.0\ninfo: {title: x, version: '1'}\npaths:\n  /a:\n    get:\n"
        "      responses:\n        '200': {$ref: 'https://evil.example.com/x.yaml'}\n"
    )
    body = {"baseline": spec(ORDERS / "baseline.yaml"), "candidate": {"content": broken}}
    problem = assert_problem(client.post("/internal/v1/analyses", headers=AUTH, json=body), 422,
                             "SPEC_INVALID")  # fmt: skip
    assert problem["side"] == "candidate"
    assert problem["errors"][0]["pointer"] == "/paths/~1a/get/responses/200/$ref"


def test_swagger_2_is_rejected_as_unsupported(client: TestClient) -> None:
    body = {"baseline": {"content": '{"swagger": "2.0", "info": {}, "paths": {}}'},
            "candidate": spec(ORDERS / "baseline.yaml")}  # fmt: skip
    problem = assert_problem(client.post("/internal/v1/analyses", headers=AUTH, json=body), 422,
                             "UNSUPPORTED_OPENAPI_VERSION")  # fmt: skip
    assert problem["side"] == "baseline"


# -------------------------------------------------------- request validation
def test_malformed_request_is_400_without_echoing_input(client: TestClient) -> None:
    secret_marker = "openapi: SENSITIVE-SPEC-CONTENT"
    response = client.post("/internal/v1/analyses", headers=AUTH,
                           json={"baseline": {"content": secret_marker}, "unexpected": 1})  # fmt: skip
    problem = assert_problem(response, 400, "VALIDATION_FAILED")
    pointers = {e["pointer"] for e in problem["errors"]}
    assert pointers == {"/candidate", "/unexpected"}
    assert "SENSITIVE-SPEC-CONTENT" not in response.text


@pytest.mark.parametrize(
    "body",
    [
        {"spec": {"content": ""}},
        {"spec": {"content": "x", "filename": "../../etc/passwd"}},
        {"spec": {"content": "x"}, "options": {"failOn": "SEVERE"}},
    ],
)
def test_field_constraints_are_enforced(client: TestClient, body: dict[str, Any]) -> None:
    assert_problem(client.post("/internal/v1/security-scans", headers=AUTH, json=body), 400,
                   "VALIDATION_FAILED")  # fmt: skip


def test_non_json_content_type_is_415(client: TestClient) -> None:
    response = client.post("/internal/v1/specs/validate", headers={**AUTH,
                           "Content-Type": "application/x-yaml"}, content=b"openapi: 3.1.0")  # fmt: skip
    assert_problem(response, 415, "UNSUPPORTED_MEDIA_TYPE")


def test_unknown_route_and_wrong_method_are_problems(client: TestClient) -> None:
    assert_problem(client.get("/internal/v1/nope", headers=AUTH), 404, "NOT_FOUND")
    assert_problem(client.get("/internal/v1/analyses", headers=AUTH), 405, "METHOD_NOT_ALLOWED")


# ------------------------------------------------------------------ limits
def test_oversized_spec_is_413() -> None:
    with make_client(max_spec_mb=0.001) as small:
        body = analysis_body(ORDERS / "baseline.yaml", ORDERS / "candidate-breaking.yaml")
        problem = assert_problem(small.post("/internal/v1/analyses", headers=AUTH, json=body), 413,
                                 "SPEC_TOO_LARGE")  # fmt: skip
        assert problem["side"] == "baseline"


def test_oversized_request_body_is_rejected_before_parsing() -> None:
    with make_client(max_spec_mb=0.01) as small:  # request limit = 4 * 10 KiB + 256 KiB
        payload = json.dumps({"spec": {"content": "a" * 400_000}})
        response = small.post("/internal/v1/specs/validate", headers={**AUTH,
                              "Content-Type": "application/json"}, content=payload)  # fmt: skip
        assert_problem(response, 413, "PAYLOAD_TOO_LARGE")


def test_streamed_body_without_content_length_is_limited() -> None:
    reached_app = False

    async def app(scope: Any, receive: Any, send: Any) -> None:
        nonlocal reached_app
        while (await receive()).get("more_body"):
            pass
        reached_app = True

    sent: list[dict[str, Any]] = []
    chunks = [{"type": "http.request", "body": b"x" * 600, "more_body": True}] * 3

    async def receive() -> dict[str, Any]:
        return chunks.pop(0)

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    scope = {"type": "http", "method": "POST", "path": "/x", "headers": []}
    asyncio.run(RequestContextMiddleware(app, max_body_bytes=1000)(scope, receive, send))
    assert not reached_app
    assert sent[0]["status"] == 413


# ---------------------------------------------------------------- validate
def test_validate_reports_valid_and_invalid_specs_with_200(client: TestClient) -> None:
    ok = client.post("/internal/v1/specs/validate", headers=AUTH,
                     json={"spec": spec(ORDERS / "baseline.yaml")}).json()  # fmt: skip
    assert ok["valid"] is True
    assert ok["spec"]["operationCount"] == 4 and ok["error"] is None
    bad = client.post("/internal/v1/specs/validate", headers=AUTH,
                      json={"spec": {"content": "openapi: 3.2.0\ninfo: {}\n"}}).json()  # fmt: skip
    assert bad["valid"] is False
    assert bad["error"]["code"] == "UNSUPPORTED_OPENAPI_VERSION"


# ---------------------------------------------------------- security scans
def test_security_scan_on_real_spec(client: TestClient) -> None:
    body = {"spec": spec(REAL / "swagger-petstore-latest.yaml")}
    result = client.post("/internal/v1/security-scans", headers=AUTH, json=body).json()
    assert {f["category"] for f in result["findings"]} == {"SPEC_HYGIENE"}
    assert {f["ruleId"] for f in result["findings"]} == {"SEC-H002", "SEC-H011", "SEC-H013"}
    assert "not a penetration test" in result["disclaimer"]
    body["options"] = {"failOn": "MEDIUM"}
    assert client.post("/internal/v1/security-scans", headers=AUTH,
                       json=body).json()["decision"]["result"] == "FAIL"  # fmt: skip


# ---------------------------------------------------------- contract tests
def test_contract_tests_endpoint_returns_runnable_files(client: TestClient, tmp_path: Path) -> None:
    body = {"spec": spec(INVENTORY), "options": {"includeUnsafeMethods": True}}
    result = client.post("/internal/v1/contract-tests", headers=AUTH, json=body).json()
    assert result["summary"] == {"total": 7, "ready": 6, "skipped": 1, "schemaValidated": 5}
    assert {f["path"] for f in result["files"]} == {
        "_apisentinel_runtime.py", "conftest.py", "operations.json", "pytest.ini",
        "requirements.txt", "test_contract.py",
    }  # fmt: skip
    skipped = [o for o in result["operations"] if o["status"] == "skipped"]
    assert skipped[0]["id"] == "GET /search" and "no example" in skipped[0]["skipReason"]
    for file in result["files"]:
        (tmp_path / file["path"]).write_text(file["content"])
    env = {**os.environ, "APISENTINEL_AUTH_TOKEN": VALID_TOKEN}
    with running_server("correct") as url:
        proc = subprocess.run([sys.executable, "-m", "pytest", str(tmp_path), "-q", "-p",
                               "no:cacheprovider", "--base-url", url], capture_output=True,
                              text=True, env=env, cwd=tmp_path, check=False, timeout=120)  # fmt: skip
    assert proc.returncode == 0, proc.stdout
    assert "6 passed, 1 skipped" in proc.stdout


def test_contract_tests_base_url_must_be_http(client: TestClient) -> None:
    body = {"spec": spec(INVENTORY), "options": {"baseUrl": "ftp://example.com"}}
    assert_problem(client.post("/internal/v1/contract-tests", headers=AUTH, json=body), 400,
                   "VALIDATION_FAILED")  # fmt: skip


# --------------------------------------------------------- observability
def test_request_id_is_propagated_or_generated(client: TestClient) -> None:
    echoed = client.get("/health/live", headers={"X-Request-Id": "trace-abc.123"})
    assert echoed.headers["x-request-id"] == "trace-abc.123"
    replaced = client.get("/health/live", headers={"X-Request-Id": "bad id\nwith newline"})
    assert len(replaced.headers["x-request-id"]) == 32


def test_logs_are_metadata_only(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="apisentinel")
    body = analysis_body(ORDERS / "baseline.yaml", ORDERS / "candidate-breaking.yaml")
    client.post("/internal/v1/analyses", headers=AUTH, json=body)
    access = [r for r in caplog.records if r.getMessage() == "request"]
    assert access and access[-1].fields["status"] == 200  # type: ignore[attr-defined]
    text = "\n".join(str(r.__dict__) for r in caplog.records)
    assert TOKEN not in text
    assert "customerEmail" not in text  # no spec content in logs


def test_unexpected_errors_are_generic_500s(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("internal detail that must not leak")

    monkeypatch.setattr("apisentinel.api.routes.analyze", boom)
    body = analysis_body(ORDERS / "baseline.yaml", ORDERS / "baseline.yaml")
    response = client.post("/internal/v1/analyses", headers=AUTH, json=body)
    assert_problem(response, 500, "INTERNAL_ERROR")
    assert "must not leak" not in response.text
    assert any("must not leak" in (r.exc_text or "") for r in caplog.records)


# ------------------------------------------------------- docs and settings
def test_docs_are_disabled_by_default(client: TestClient) -> None:
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    with make_client(enable_docs=True) as docs:
        assert docs.get("/openapi.json").status_code == 200


def test_missing_or_short_token_refuses_to_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APISENTINEL_INTERNAL_TOKEN", raising=False)
    with pytest.raises(ConfigurationError, match="APISENTINEL_INTERNAL_TOKEN"):
        load_settings()
    monkeypatch.setenv("APISENTINEL_INTERNAL_TOKEN", "short-secret-value")
    with pytest.raises(ConfigurationError) as info:
        load_settings()
    assert "short-secret-value" not in str(info.value)


def test_committed_contract_matches_the_service() -> None:
    committed = json.loads((ROOT / "contracts" / "analyzer-api.openapi.json").read_text())
    assert committed == build_contract(), (
        "contracts/analyzer-api.openapi.json is stale; regenerate it with "
        "'uv run python -m apisentinel.api.contract > ../contracts/analyzer-api.openapi.json'"
    )
