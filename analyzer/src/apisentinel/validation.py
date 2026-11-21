"""Structural validation of an OpenAPI document.

Order matters: our own ``$ref`` checks run *before* openapi-spec-validator,
because that library follows references itself. Rejecting external references
first guarantees no file or URL is ever fetched (no SSRF, no local file reads),
and checking local references first turns its crash on a dangling reference
into a clear error.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from openapi_spec_validator import OpenAPIV30SpecValidator, OpenAPIV31SpecValidator

from apisentinel import pointer
from apisentinel.errors import Issue, SpecValidationError
from apisentinel.loading import JsonObject

MAX_REPORTED_ISSUES = 50
HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
_VERSION_RE = re.compile(r"^3\.(0|1)\.\d+$")


@dataclass(frozen=True, slots=True)
class SpecInfo:
    """Facts about a validated document, safe to show to users."""

    openapi_version: str  # e.g. "3.1.0"
    version_family: str  # "3.0" or "3.1"
    title: str | None
    api_version: str | None
    operation_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "openapiVersion": self.openapi_version,
            "title": self.title,
            "apiVersion": self.api_version,
            "operationCount": self.operation_count,
        }


def detect_version(document: JsonObject) -> tuple[str, str]:
    """Return (full version, family) or raise for unsupported documents."""
    if "swagger" in document:
        raise SpecValidationError(
            code="UNSUPPORTED_OPENAPI_VERSION",
            message="Swagger 2.0 documents are not supported; convert to OpenAPI 3.x first.",
        )
    version = document.get("openapi")
    if not isinstance(version, str):
        raise SpecValidationError(
            code="SPEC_INVALID",
            message="Missing or non-string 'openapi' version field.",
            issues=[
                Issue(message="'openapi' must be a string such as '3.1.0'.", pointer="/openapi")
            ],
        )
    match = _VERSION_RE.match(version)
    if not match:
        raise SpecValidationError(
            code="UNSUPPORTED_OPENAPI_VERSION",
            message=f"OpenAPI version '{version}' is not supported; use 3.0.x or 3.1.x.",
        )
    return version, f"3.{match.group(1)}"


def _iter_refs(node: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    stack: list[tuple[Any, str]] = [(node, path)]
    while stack:
        current, where = stack.pop()
        if isinstance(current, dict):
            for key, value in current.items():
                child = pointer.join(where, key)
                if key == "$ref":
                    yield child, value
                else:
                    stack.append((value, child))
        elif isinstance(current, list):
            for index, value in enumerate(current):
                stack.append((value, pointer.join(where, index)))


def check_references(document: JsonObject) -> list[Issue]:
    """Reject external references and report local references that do not resolve."""
    issues: list[Issue] = []
    for where, ref in _iter_refs(document):
        if not isinstance(ref, str):
            issues.append(Issue(message="$ref must be a string.", pointer=where))
        elif not ref.startswith("#"):
            issues.append(
                Issue(
                    message=(
                        f"External reference '{ref[:200]}' is not allowed; bundle the "
                        "specification into a single file first."
                    ),
                    pointer=where,
                )
            )
        else:
            try:
                pointer.resolve(document, ref[1:])
            except KeyError:
                issues.append(
                    Issue(message=f"Reference '{ref[:200]}' does not resolve.", pointer=where)
                )
    return sorted(issues, key=lambda i: i.pointer or "")


def _schema_issues(document: JsonObject, family: str) -> list[Issue]:
    validator_cls = OpenAPIV31SpecValidator if family == "3.1" else OpenAPIV30SpecValidator
    issues: list[Issue] = []
    top_level_keys = set(document)
    try:
        for error in validator_cls(document).iter_errors():
            path = [str(p) for p in getattr(error, "absolute_path", [])]
            # The library reports some paths relative to a nested schema; only
            # keep pointers that are anchored at the document root.
            where = pointer.join("", *path) if path and path[0] in top_level_keys else None
            message = str(getattr(error, "message", error))
            issues.append(Issue(message=message[:300], pointer=where))
            if len(issues) >= MAX_REPORTED_ISSUES:
                break
    except Exception as exc:  # the library raises on some malformed input
        issues.append(
            Issue(message=f"Specification could not be validated ({type(exc).__name__}).")
        )
    return issues


def count_operations(document: JsonObject) -> int:
    paths = document.get("paths")
    if not isinstance(paths, dict):
        return 0
    return sum(
        1
        for item in paths.values()
        if isinstance(item, dict)
        for method in HTTP_METHODS
        if isinstance(item.get(method), dict)
    )


def validate_document(document: JsonObject) -> SpecInfo:
    """Validate a loaded document and return its facts.

    Raises:
        SpecValidationError: with every issue found (capped), if invalid or unsupported.
    """
    version, family = detect_version(document)

    ref_issues = check_references(document)
    if ref_issues:
        raise SpecValidationError(
            code="SPEC_INVALID",
            message="Specification contains invalid or external references.",
            issues=ref_issues[:MAX_REPORTED_ISSUES],
        )

    schema_issues = _schema_issues(document, family)
    if schema_issues:
        raise SpecValidationError(
            code="SPEC_INVALID",
            message=f"Specification is not a valid OpenAPI {family} document.",
            issues=schema_issues,
        )

    info = document.get("info") if isinstance(document.get("info"), dict) else {}
    assert isinstance(info, dict)
    title = info.get("title")
    api_version = info.get("version")
    return SpecInfo(
        openapi_version=version,
        version_family=family,
        title=title if isinstance(title, str) else None,
        api_version=str(api_version) if api_version is not None else None,
        operation_count=count_operations(document),
    )
