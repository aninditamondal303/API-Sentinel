"""HTTP endpoints. Each handler only translates between HTTP and the engine:
no compatibility, security or generation logic lives here.
"""

from __future__ import annotations

import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request

from apisentinel import RULESET_VERSION, __version__
from apisentinel.api.problems import ProblemError
from apisentinel.api.schemas import (
    AnalysisRequest,
    AnalysisResult,
    ContractTestRequest,
    ContractTestResult,
    Health,
    Problem,
    RulesResponse,
    SecurityScanRequest,
    SecurityScanResult,
    SpecPayload,
    SpecRequest,
    ValidationResult,
)
from apisentinel.api.settings import Settings
from apisentinel.engine import FailurePolicy, LoadedSpec, SpecInput, analyze, load_spec
from apisentinel.errors import ApiSentinelError
from apisentinel.hygiene import scan
from apisentinel.rules import RULES, Severity
from apisentinel.testgen import GenerationOptions, generate_contract_tests

ERRORS: dict[int | str, dict[str, Any]] = {
    status: {"model": Problem, "description": description}
    for status, description in {
        400: "Malformed request",
        401: "Missing or invalid X-Internal-Token",
        413: "Request or specification too large",
        415: "Content-Type must be application/json",
        422: "Specification could not be parsed, is invalid or unsupported",
        500: "Unexpected analyzer error",
    }.items()
}


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def require_internal_token(
    request: Request,
    x_internal_token: Annotated[str | None, Header()] = None,
) -> None:
    expected = get_settings(request).internal_token.get_secret_value()
    supplied = x_internal_token or ""
    if not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise ProblemError(401, "UNAUTHENTICATED", "Missing or invalid X-Internal-Token header.")


def require_json(request: Request) -> None:
    if request.method == "POST":
        media = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if media != "application/json":
            raise ProblemError(
                415, "UNSUPPORTED_MEDIA_TYPE", "Send the request as application/json."
            )


health = APIRouter(tags=["health"])
internal = APIRouter(
    prefix="/internal/v1",
    dependencies=[Depends(require_internal_token), Depends(require_json)],
    responses=ERRORS,
)


def _input(payload: SpecPayload) -> SpecInput:
    return SpecInput(payload.content.encode("utf-8"), payload.filename)


def _severity(name: str | None) -> Severity | None:
    return Severity[name] if name is not None else None


def _load(payload: SpecPayload, settings: Settings) -> LoadedSpec:
    return load_spec(_input(payload), settings.max_spec_bytes)


@health.get("/health/live", response_model=Health)
def live() -> dict[str, str]:
    return {"status": "ok", "analyzerVersion": __version__, "rulesetVersion": RULESET_VERSION}


@health.get("/health/ready", response_model=Health)
def ready() -> dict[str, str]:
    # The engine has no external dependencies: if the process serves requests, it is ready.
    return {"status": "ready", "analyzerVersion": __version__, "rulesetVersion": RULESET_VERSION}


@internal.post("/specs/validate", response_model=ValidationResult, summary="Validate one spec")
def validate_spec(body: SpecRequest, request: Request) -> dict[str, Any]:
    """Always 200 for a well-formed request: ``valid`` says whether the spec is usable."""
    try:
        loaded = _load(body.spec, get_settings(request))
    except ApiSentinelError as err:
        issues = [i.to_dict() for i in err.issues]
        return {
            "valid": False,
            "error": {"code": err.code, "message": err.message, "issues": issues},
        }
    return {"valid": True, "spec": loaded.to_dict()}


@internal.post("/analyses", response_model=AnalysisResult, summary="Compare two specs")
def create_analysis(body: AnalysisRequest, request: Request) -> dict[str, Any]:
    policy = FailurePolicy(
        fail_on=_severity(body.options.fail_on),
        fail_on_manual_review=body.options.fail_on_manual_review,
    )
    return analyze(
        _input(body.baseline),
        _input(body.candidate),
        policy,
        max_bytes=get_settings(request).max_spec_bytes,
    )


@internal.post("/security-scans", response_model=SecurityScanResult, summary="Security hygiene")
def create_security_scan(body: SecurityScanRequest, request: Request) -> dict[str, Any]:
    return scan(_load(body.spec, get_settings(request)), _severity(body.options.fail_on))


@internal.post("/contract-tests", response_model=ContractTestResult, summary="Generate tests")
def create_contract_tests(body: ContractTestRequest, request: Request) -> dict[str, Any]:
    loaded = _load(body.spec, get_settings(request))
    base_url = str(body.options.base_url) if body.options.base_url else None
    suite = generate_contract_tests(
        loaded,
        GenerationOptions(
            include_unsafe_methods=body.options.include_unsafe_methods,
            default_base_url=base_url.rstrip("/") if base_url else None,
        ),
    )
    operations = [
        {
            "id": o["id"],
            "method": o["method"],
            "path": o["path"],
            "operationId": o["operationId"],
            "status": o["status"],
            "skipReason": o["skipReason"],
            "expectedStatuses": o["expectedStatuses"],
            "inputSources": o["inputSources"],
            "notes": o["notes"],
            "requiresAuth": o["requiresAuth"],
        }
        for o in suite.operations
    ]
    return {
        "spec": loaded.to_dict(),
        "summary": suite.summary(),
        "operations": operations,
        "files": [{"path": name, "content": text} for name, text in sorted(suite.files.items())],
        "runCommand": "pip install -r requirements.txt && pytest --base-url <URL>",
    }


@internal.get("/rules", response_model=RulesResponse, summary="Rule catalog")
def list_rules() -> dict[str, Any]:
    rules = [r.to_dict() for r in sorted(RULES.values(), key=lambda r: r.id)]
    return {"rulesetVersion": RULESET_VERSION, "rules": rules}
