"""Finding model and the collector that turns rule hits into findings."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from apisentinel.rules import RULES, Rule, Severity, render

_MAX_VALUE_CHARS = 300


def short(value: Any) -> str:
    """Compact, bounded rendering of a value for messages."""
    if value is None:
        return "none"
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    return text if len(text) <= 80 else text[:77] + "..."


def _bounded(value: Any) -> Any:
    """Keep oldValue/newValue small: large schemas are summarized, not copied."""
    text = json.dumps(value, sort_keys=True, default=str)
    if len(text) <= _MAX_VALUE_CHARS:
        return value
    return {"summary": text[: _MAX_VALUE_CHARS - 3] + "..."}


@dataclass(frozen=True, slots=True)
class Finding:
    rule: Rule
    method: str | None
    path: str | None
    location: str
    location_document: str  # "baseline" | "candidate"
    field: str | None
    old_value: Any
    new_value: Any
    message: str
    impact: str
    remediation: str

    @property
    def severity(self) -> Severity:
        return self.rule.severity

    @property
    def fingerprint(self) -> str:
        key = "|".join(
            [self.rule.id, self.method or "", self.path or "", self.location, self.field or ""]
        )
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def sort_key(self) -> tuple[Any, ...]:
        return (
            -int(self.severity),
            self.path or "",
            self.method or "",
            self.rule.id,
            self.field or "",
            self.location,
        )

    def to_dict(self) -> dict[str, Any]:
        rule = self.rule
        return {
            "ruleId": rule.id,
            "title": rule.title,
            "category": rule.category.value,
            "severity": rule.severity.name,
            "requiresManualReview": rule.manual_review,
            "method": self.method,
            "path": self.path,
            "location": self.location,
            "locationDocument": self.location_document,
            "field": self.field,
            "oldValue": _bounded(self.old_value),
            "newValue": _bounded(self.new_value),
            "message": self.message,
            "impact": self.impact,
            "remediation": self.remediation,
            "fingerprint": self.fingerprint,
        }


class Collector:
    """Accumulates findings, de-duplicating identical hits."""

    def __init__(self) -> None:
        self._findings: dict[tuple[str, str | None, str | None, str, str | None], Finding] = {}

    def add(
        self,
        rule_id: str,
        *,
        method: str | None,
        path: str | None,
        location: str,
        baseline_location: bool = False,
        document: str | None = None,
        field: str | None = None,
        old: Any = None,
        new: Any = None,
        **details: Any,
    ) -> None:
        rule = RULES[rule_id]
        context = {
            "method": method,
            "path": path,
            "field": field or "",
            "old": short(old),
            "new": short(new),
            **details,
        }
        finding = Finding(
            rule=rule,
            method=method,
            path=path,
            location=location,
            location_document=document or ("baseline" if baseline_location else "candidate"),
            field=field,
            old_value=old,
            new_value=new,
            message=render(rule.message, context),
            impact=render(rule.impact, context),
            remediation=render(rule.remediation, context),
        )
        key = (rule_id, method, path, location, field)
        self._findings.setdefault(key, finding)

    def findings(self) -> list[Finding]:
        return sorted(self._findings.values(), key=Finding.sort_key)
