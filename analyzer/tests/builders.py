"""Small builders for valid OpenAPI documents used by the rule tests."""

from __future__ import annotations

import copy
import json
from typing import Any

from apisentinel.engine import FailurePolicy, SpecInput, analyze

Json = dict[str, Any]
OK = {"200": {"description": "ok"}}


def op(**fields: Any) -> Json:
    """An operation with a default 200 response."""
    result: Json = {"responses": copy.deepcopy(OK)}
    result.update(fields)
    return result


def param(name: str, location: str = "query", required: bool = False, **extra: Any) -> Json:
    data: Json = {"name": name, "in": location, "schema": {"type": "string"}}
    if required or location == "path":
        data["required"] = True
    data.update(extra)
    return data


def json_body(schema: Json, required: bool = True, media: str = "application/json") -> Json:
    return {"required": required, "content": {media: {"schema": schema}}}


def json_response(schema: Json, status: str = "200", media: str = "application/json") -> Json:
    return {status: {"description": "ok", "content": {media: {"schema": schema}}}}


def obj(properties: Json, required: list[str] | None = None, **extra: Any) -> Json:
    data: Json = {"type": "object", "properties": properties}
    if required:
        data["required"] = required
    data.update(extra)
    return data


def spec(
    paths: Json,
    *,
    components: Json | None = None,
    security: list[Json] | None = None,
    servers: list[Json] | None = None,
    version: str = "3.1.0",
) -> Json:
    doc: Json = {"openapi": version, "info": {"title": "Test API", "version": "1.0.0"}}
    if servers is not None:
        doc["servers"] = servers
    doc["paths"] = paths
    if components is not None:
        doc["components"] = components
    if security is not None:
        doc["security"] = security
    return doc


def get_spec(operation: Json, path: str = "/items", **kwargs: Any) -> Json:
    return spec({path: {"get": operation}}, **kwargs)


def post_spec(operation: Json, path: str = "/items", **kwargs: Any) -> Json:
    return spec({path: {"post": operation}}, **kwargs)


def run(baseline: Json, candidate: Json, policy: FailurePolicy | None = None) -> Json:
    return analyze(
        SpecInput(json.dumps(baseline).encode(), "baseline.json"),
        SpecInput(json.dumps(candidate).encode(), "candidate.json"),
        policy,
    )


def rule_ids(result: Json) -> set[str]:
    return {f["ruleId"] for f in result["findings"]}
