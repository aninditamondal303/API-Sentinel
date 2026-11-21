"""Request and response contracts of the analyzer service.

These models *describe and validate* what the engine returns; they contain no
analysis logic. The generated OpenAPI document of this service is committed as
``contracts/analyzer-api.openapi.json`` and checked for drift in tests.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from pydantic.alias_generators import to_camel

SeverityName = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
CategoryName = Literal["COMPATIBILITY", "SECURITY_REGRESSION", "SPEC_HYGIENE"]


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class StrictRequest(ApiModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


# ------------------------------------------------------------------ requests
class SpecPayload(StrictRequest):
    content: str = Field(min_length=1, description="The OpenAPI document as JSON or YAML text.")
    filename: str | None = Field(
        default=None,
        max_length=255,
        pattern=r"^[\w.\- ]+$",
        description="Original file name; only its extension is used, to pick JSON or YAML.",
        examples=["orders-v2.yaml"],
    )


class AnalysisOptions(StrictRequest):
    fail_on: SeverityName | None = Field(
        default="HIGH",
        description="Fail when a finding has this severity or higher; null to disable.",
    )
    fail_on_manual_review: bool = True


class AnalysisRequest(StrictRequest):
    baseline: SpecPayload
    candidate: SpecPayload
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)


class SpecRequest(StrictRequest):
    spec: SpecPayload


class ScanOptions(StrictRequest):
    fail_on: SeverityName | None = "HIGH"


class SecurityScanRequest(StrictRequest):
    spec: SpecPayload
    options: ScanOptions = Field(default_factory=ScanOptions)


class ContractTestOptions(StrictRequest):
    include_unsafe_methods: bool = Field(
        default=False, description="Also generate tests for POST/PUT/PATCH/DELETE."
    )
    base_url: HttpUrl | None = Field(
        default=None, description="Default base URL stored in the suite (overridable at run time)."
    )


class ContractTestRequest(StrictRequest):
    spec: SpecPayload
    options: ContractTestOptions = Field(default_factory=ContractTestOptions)


# ----------------------------------------------------------------- responses
class AnalyzerInfo(ApiModel):
    version: str
    ruleset_version: str


class SpecSummary(ApiModel):
    openapi_version: str
    title: str | None
    api_version: str | None
    operation_count: int
    sha256: str


class Finding(ApiModel):
    rule_id: str
    title: str
    category: CategoryName
    severity: SeverityName
    requires_manual_review: bool
    method: str | None
    path: str | None
    location: str = Field(description="JSON Pointer into the document named by locationDocument.")
    location_document: Literal["baseline", "candidate", "spec"]
    field: str | None
    old_value: Any
    new_value: Any
    message: str
    impact: str
    remediation: str
    fingerprint: str


class AnalysisDecision(ApiModel):
    result: Literal["PASS", "FAIL"]
    reasons: list[str]
    fail_on: SeverityName | None
    fail_on_manual_review: bool


class AnalysisSummary(ApiModel):
    total: int
    by_severity: dict[SeverityName, int]
    by_category: dict[CategoryName, int]
    breaking_changes: int
    manual_review: int
    endpoints_affected: int


class AnalysisResult(ApiModel):
    schema_version: str
    analyzer: AnalyzerInfo
    baseline: SpecSummary
    candidate: SpecSummary
    decision: AnalysisDecision
    summary: AnalysisSummary
    findings: list[Finding]


class ScanDecision(ApiModel):
    result: Literal["PASS", "FAIL"]
    reasons: list[str]
    fail_on: SeverityName | None


class ScanSummary(ApiModel):
    total: int
    by_severity: dict[SeverityName, int]
    endpoints_affected: int


class SecurityScanResult(ApiModel):
    schema_version: str
    analyzer: AnalyzerInfo
    spec: SpecSummary
    decision: ScanDecision
    summary: ScanSummary
    findings: list[Finding]
    disclaimer: str


class Issue(ApiModel):
    pointer: str | None
    message: str


class ErrorBody(ApiModel):
    code: str
    message: str
    issues: list[Issue]


class ValidationResult(ApiModel):
    valid: bool
    spec: SpecSummary | None = None
    error: ErrorBody | None = None


class GeneratedFile(ApiModel):
    path: str
    content: str


class GeneratedOperation(ApiModel):
    id: str
    method: str
    path: str
    operation_id: str | None
    status: Literal["ready", "skipped"]
    skip_reason: str | None
    expected_statuses: list[str]
    input_sources: dict[str, str]
    notes: list[str]
    requires_auth: bool


class ContractTestSummary(ApiModel):
    total: int
    ready: int
    skipped: int
    schema_validated: int


class ContractTestResult(ApiModel):
    spec: SpecSummary
    summary: ContractTestSummary
    operations: list[GeneratedOperation]
    files: list[GeneratedFile]
    run_command: str


class RuleInfo(ApiModel):
    id: str
    title: str
    category: CategoryName
    severity: SeverityName
    requires_manual_review: bool
    impact: str
    remediation: str


class RulesResponse(ApiModel):
    ruleset_version: str
    rules: list[RuleInfo]


class Health(ApiModel):
    status: Literal["ok", "ready"]
    analyzer_version: str
    ruleset_version: str


class Problem(ApiModel):
    """RFC 9457 problem details, used for every error response."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str | None = None
    error_code: str
    request_id: str | None = None
    side: Literal["baseline", "candidate"] | None = None
    errors: list[Issue] | None = None
