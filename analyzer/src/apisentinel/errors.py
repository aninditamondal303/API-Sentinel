"""Typed errors raised by the analyzer.

Every error carries a stable machine-readable ``code`` so callers (the CLI today,
the Java backend later) can map it to an exit code or HTTP status without parsing
human text.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Issue:
    """One problem found in a specification document."""

    message: str
    pointer: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {"pointer": self.pointer, "message": self.message}


@dataclass
class ApiSentinelError(Exception):
    """Base class for all expected (user-input) errors."""

    code: str
    message: str
    issues: list[Issue] = field(default_factory=list)

    def __str__(self) -> str:
        return self.message


class SpecLoadError(ApiSentinelError):
    """The file could not be read or parsed as JSON/YAML."""


class SpecValidationError(ApiSentinelError):
    """The document parsed but is not a valid, supported OpenAPI document."""
