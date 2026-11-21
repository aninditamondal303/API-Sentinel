"""Public entry point: ``analyze()`` turns two spec files into a structured result.

This module is the only API the CLI (and later the FastAPI service used by the
Java backend) calls, so every surface produces identical results.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from typing import Any

from apisentinel import RULESET_VERSION, __version__
from apisentinel.diff import Comparator
from apisentinel.document import Document
from apisentinel.errors import ApiSentinelError
from apisentinel.findings import Collector, Finding
from apisentinel.loading import DEFAULT_MAX_BYTES, load_document
from apisentinel.rules import Category, Severity
from apisentinel.validation import SpecInfo, validate_document

RESULT_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class SpecInput:
    data: bytes
    filename: str | None = None


@dataclass(frozen=True, slots=True)
class FailurePolicy:
    """When the analysis counts as failed. Thresholds only; no waivers in v1."""

    fail_on: Severity | None = Severity.HIGH  # None disables severity-based failure
    fail_on_manual_review: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "failOn": self.fail_on.name if self.fail_on is not None else None,
            "failOnManualReview": self.fail_on_manual_review,
        }


@dataclass(frozen=True, slots=True)
class LoadedSpec:
    info: SpecInfo
    document: Document
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {**self.info.to_dict(), "sha256": self.sha256}


class InputError(ApiSentinelError):
    """Wraps a load/validation error with which side (baseline/candidate) it came from."""

    def __init__(self, side: str, cause: ApiSentinelError) -> None:
        super().__init__(code=cause.code, message=f"{side}: {cause.message}", issues=cause.issues)
        self.side = side


def load_spec(spec: SpecInput, max_bytes: int = DEFAULT_MAX_BYTES) -> LoadedSpec:
    raw = load_document(spec.data, spec.filename, max_bytes=max_bytes)
    info = validate_document(raw)
    return LoadedSpec(
        info=info,
        document=Document(raw, info.version_family),
        sha256=hashlib.sha256(spec.data).hexdigest(),
    )


def _decision(findings: list[Finding], policy: FailurePolicy) -> dict[str, Any]:
    reasons: list[str] = []
    if policy.fail_on is not None:
        threshold = policy.fail_on
        at_or_above = [f for f in findings if f.severity >= threshold]
        if at_or_above:
            reasons.append(f"{len(at_or_above)} finding(s) at or above {threshold.name}")
    if policy.fail_on_manual_review:
        manual = [f for f in findings if f.rule.manual_review]
        if manual:
            reasons.append(f"{len(manual)} finding(s) require manual review")
    return {"result": "FAIL" if reasons else "PASS", "reasons": reasons, **policy.to_dict()}


def _summary(findings: list[Finding]) -> dict[str, Any]:
    by_severity = Counter(f.severity.name for f in findings)
    by_category = Counter(f.rule.category.value for f in findings)
    breaking = sum(
        1
        for f in findings
        if f.rule.category is Category.COMPATIBILITY and f.severity >= Severity.HIGH
    )
    return {
        "total": len(findings),
        "bySeverity": {s.name: by_severity.get(s.name, 0) for s in reversed(Severity)},
        "byCategory": {c.value: by_category.get(c.value, 0) for c in Category},
        "breakingChanges": breaking,
        "manualReview": sum(1 for f in findings if f.rule.manual_review),
        "endpointsAffected": len({(f.method, f.path) for f in findings if f.path}),
    }


def analyze(
    baseline: SpecInput,
    candidate: SpecInput,
    policy: FailurePolicy | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> dict[str, Any]:
    """Compare two specifications and return a JSON-serializable result.

    Raises:
        InputError: if either specification cannot be loaded or is invalid.
    """
    policy = policy or FailurePolicy()
    loaded: dict[str, LoadedSpec] = {}
    for side, spec in (("baseline", baseline), ("candidate", candidate)):
        try:
            loaded[side] = load_spec(spec, max_bytes)
        except ApiSentinelError as exc:
            raise InputError(side, exc) from None

    collector = Collector()
    Comparator(loaded["baseline"].document, loaded["candidate"].document, collector).run()
    findings = collector.findings()

    return {
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "analyzer": {"version": __version__, "rulesetVersion": RULESET_VERSION},
        "baseline": loaded["baseline"].to_dict(),
        "candidate": loaded["candidate"].to_dict(),
        "decision": _decision(findings, policy),
        "summary": _summary(findings),
        "findings": [f.to_dict() for f in findings],
    }
