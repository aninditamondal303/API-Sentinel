"""Security hygiene scanner: every SEC-H rule has a positive case and a near-miss."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from builders import op, param, spec

from apisentinel.engine import SpecInput, load_spec
from apisentinel.hygiene import DISCLAIMER, scan
from apisentinel.rules import RULES, Category, Severity

Json = dict[str, Any]
REAL = Path(__file__).parent / "fixtures" / "real"

BEARER = {"bearer": {"type": "http", "scheme": "bearer"}}
BASIC = {"basic": {"type": "http", "scheme": "basic"}}


def oauth(flow: str = "clientCredentials", url: str = "https://auth.example.com/token") -> Json:
    body: Json = {"scopes": {"read": "Read"}}
    if flow in {"clientCredentials", "password"}:
        body["tokenUrl"] = url
    elif flow == "implicit":
        body["authorizationUrl"] = url
    else:
        body.update(authorizationUrl=url, tokenUrl=url)
    return {"oauth": {"type": "oauth2", "flows": {flow: body}}}


def api(
    paths: Json | None = None,
    *,
    schemes: Json | None = None,
    security: list[Json] | None = None,
    servers: list[str] | None = None,
) -> Json:
    return spec(
        paths if paths is not None else {"/items": {"get": op()}},
        components={"securitySchemes": schemes} if schemes is not None else None,
        security=security,
        servers=[{"url": u} for u in servers] if servers is not None else None,
    )


def scan_doc(doc: Json) -> Json:
    return scan(load_spec(SpecInput(json.dumps(doc).encode(), "spec.json")))


def ids(result: Json) -> set[str]:
    return {f["ruleId"] for f in result["findings"]}


@dataclass(frozen=True)
class Case:
    rule: str
    positive: Json
    negative: Json


secured = {"schemes": BEARER, "security": [{"bearer": []}]}

CASES: list[Case] = [
    Case("SEC-H001", api(servers=["http://api.example.com"], **secured),
         api(servers=["https://api.example.com"], **secured)),
    Case("SEC-H002", api(), api(**secured)),
    Case("SEC-H003", api({"/items": {"get": op(security=[])}}, **secured), api(**secured)),
    Case("SEC-H004", api(schemes=BEARER, security=[{"bearerAuth": []}]), api(**secured)),
    Case("SEC-H005", api(schemes={**BEARER, **BASIC}, security=[{"bearer": []}]), api(**secured)),
    Case("SEC-H006", api(schemes=oauth(), security=[{"oauth": ["admin"]}]),
         api(schemes=oauth(), security=[{"oauth": ["read"]}])),
    Case("SEC-H007",
         api(schemes={"key": {"type": "apiKey", "in": "query", "name": "api_key"}},
             security=[{"key": []}]),
         api(schemes={"key": {"type": "apiKey", "in": "header", "name": "X-API-Key"}},
             security=[{"key": []}])),
    Case("SEC-H008", api(servers=["http://api.example.com"], schemes=BASIC, security=[{"basic": []}]),
         api(servers=["https://api.example.com"], schemes=BASIC, security=[{"basic": []}])),
    Case("SEC-H009",
         api({"/items": {"get": op(), "post": op(security=[])}}, **secured),
         api({"/items": {"get": op(security=[]), "post": op()}}, **secured)),
    Case("SEC-H010", api(servers=["http://localhost:8080"], **secured),
         api(servers=["https://localhost:8443"], **secured)),
    Case("SEC-H011", api(schemes=oauth("implicit"), security=[{"oauth": ["read"]}]),
         api(schemes=oauth("authorizationCode"), security=[{"oauth": ["read"]}])),
    Case("SEC-H012",
         api(schemes=oauth(url="http://auth.example.com/token"), security=[{"oauth": ["read"]}]),
         api(schemes=oauth(url="https://auth.example.com/token"), security=[{"oauth": ["read"]}])),
    Case("SEC-H013", api({"/login": {"get": op(parameters=[param("password")])}}, **secured),
         api({"/login": {"get": op(parameters=[param("username")])}}, **secured)),
    Case("SEC-H014", api({"/items": {"post": op(security=[{"bearer": []}, {}])}}, **secured),
         api({"/items": {"get": op(security=[{"bearer": []}, {}])}}, **secured)),
]  # fmt: skip


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.rule)
def test_rule_fires_on_positive_case(case: Case) -> None:
    assert case.rule in ids(scan_doc(case.positive))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.rule)
def test_rule_silent_on_negative_case(case: Case) -> None:
    assert case.rule not in ids(scan_doc(case.negative))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.rule)
def test_finding_is_complete_and_separate_from_compatibility(case: Case) -> None:
    finding = next(f for f in scan_doc(case.positive)["findings"] if f["ruleId"] == case.rule)
    assert finding["category"] == "SPEC_HYGIENE"
    assert finding["locationDocument"] == "spec"
    assert finding["location"].startswith("/")
    for text in ("message", "impact", "remediation"):
        assert finding[text] and "'?'" not in finding[text], finding[text]


def test_every_hygiene_rule_has_cases() -> None:
    hygiene = {r.id for r in RULES.values() if r.category is Category.SPEC_HYGIENE}
    covered = [c.rule for c in CASES]
    assert len(covered) == len(set(covered))
    assert set(covered) == hygiene


def test_server_variables_are_resolved() -> None:
    doc = api(**secured)
    doc["servers"] = [
        {"url": "{scheme}://api.example.com", "variables": {"scheme": {"default": "http"}}}
    ]
    assert "SEC-H001" in ids(scan_doc(doc))


def test_operation_level_servers_are_checked() -> None:
    doc = api({"/items": {"get": op(servers=[{"url": "http://legacy.example.com"}])}}, **secured)
    finding = next(f for f in scan_doc(doc)["findings"] if f["ruleId"] == "SEC-H001")
    assert finding["location"] == "/paths/~1items/get/servers/0/url"


def test_clean_spec_passes_with_disclaimer() -> None:
    result = scan_doc(api(servers=["https://api.example.com"], **secured))
    assert result["findings"] == []
    assert result["decision"]["result"] == "PASS"
    assert result["disclaimer"] == DISCLAIMER
    assert "not a penetration test" in DISCLAIMER


def test_threshold_controls_decision() -> None:
    doc = api(schemes=BEARER, security=[{"missing": []}])  # SEC-H004 is HIGH
    loaded = load_spec(SpecInput(json.dumps(doc).encode(), "spec.json"))
    assert scan(loaded)["decision"]["result"] == "FAIL"
    assert scan(loaded, fail_on=Severity.CRITICAL)["decision"]["result"] == "PASS"
    assert scan(loaded, fail_on=None)["decision"]["result"] == "PASS"


def test_real_swagger_petstore_findings() -> None:
    """Exact results on the unmodified upstream spec (tests/fixtures/real/SOURCES.md)."""
    data = (REAL / "swagger-petstore-latest.yaml").read_bytes()
    result = scan(load_spec(SpecInput(data, "petstore.yaml")))
    counts = {r: sum(1 for f in result["findings"] if f["ruleId"] == r) for r in ids(result)}
    assert counts == {"SEC-H002": 10, "SEC-H011": 1, "SEC-H013": 1}
    login = next(f for f in result["findings"] if f["ruleId"] == "SEC-H013")
    assert (login["method"], login["path"], login["field"]) == (
        "GET",
        "/user/login",
        "query.password",
    )


@pytest.mark.parametrize("name", sorted(p.name for p in REAL.glob("*.yaml")))
def test_scanner_runs_on_every_real_spec(name: str) -> None:
    result = scan(load_spec(SpecInput((REAL / name).read_bytes(), name)))
    assert result["summary"]["total"] == len(result["findings"])
