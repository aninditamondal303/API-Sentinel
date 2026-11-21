"""Read-only view over a validated OpenAPI document.

Normalizes the parts the comparators need (operations, parameters, security)
and resolves local ``$ref`` chains while tracking the real JSON Pointer of the
resolved node, so findings can point at the exact place to edit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from apisentinel import pointer
from apisentinel.loading import JsonObject
from apisentinel.validation import HTTP_METHODS

_PATH_PARAM = re.compile(r"\{([^}/]+)\}")
MAX_REF_HOPS = 32
IGNORED_HEADERS = {"accept", "content-type", "authorization"}
DEFAULT_STYLE = {"path": "simple", "query": "form", "header": "simple", "cookie": "form"}


class RefCycleError(Exception):
    """A $ref chain points back to itself without reaching a schema."""


def normalize_path(template: str) -> str:
    """'/users/{userId}/posts' -> '/users/{}/posts' so renamed path params still match."""
    return _PATH_PARAM.sub("{}", template)


def path_param_names(template: str) -> list[str]:
    return _PATH_PARAM.findall(template)


@dataclass(frozen=True, slots=True)
class Parameter:
    key: tuple[str, str]
    name: str
    location: str  # path | query | header | cookie
    required: bool
    pointer: str
    schema: Any
    schema_pointer: str
    style: str
    explode: bool
    raw: JsonObject


@dataclass(slots=True)
class Operation:
    method: str  # upper-case
    path: str  # template as written in this document
    normalized_path: str
    pointer: str
    raw: JsonObject
    path_item: JsonObject
    path_item_pointer: str
    deprecated: bool = False
    operation_id: str | None = None
    parameters: dict[tuple[str, str], Parameter] = field(default_factory=dict)


class Document:
    def __init__(self, raw: JsonObject, version_family: str) -> None:
        self.raw = raw
        self.version_family = version_family
        self.operations: dict[tuple[str, str], Operation] = self._collect_operations()

    # ------------------------------------------------------------------ refs
    def deref(self, node: Any, where: str) -> tuple[Any, str]:
        """Follow a local $ref chain. Returns (resolved node, its pointer)."""
        seen: set[str] = set()
        hops = 0
        while isinstance(node, dict) and isinstance(node.get("$ref"), str):
            ref: str = node["$ref"]
            if ref in seen or hops >= MAX_REF_HOPS:
                raise RefCycleError(ref)
            seen.add(ref)
            hops += 1
            target = ref[1:]
            node = pointer.resolve(self.raw, target)  # validated earlier: always resolves
            where = target
        return node, where

    @staticmethod
    def ref_name(node: Any) -> str | None:
        if isinstance(node, dict) and isinstance(node.get("$ref"), str):
            return str(node["$ref"])
        return None

    # ------------------------------------------------------------ operations
    def _collect_operations(self) -> dict[tuple[str, str], Operation]:
        operations: dict[tuple[str, str], Operation] = {}
        paths = self.raw.get("paths")
        if not isinstance(paths, dict):
            return operations
        for template in sorted(paths):
            item_ptr = pointer.join("/paths", template)
            item, item_ptr = self.deref(paths[template], item_ptr)
            if not isinstance(item, dict):
                continue
            normalized = normalize_path(template)
            for method in HTTP_METHODS:
                op = item.get(method)
                if not isinstance(op, dict):
                    continue
                key = (method.upper(), normalized)
                if key in operations:  # duplicate template after normalization
                    continue
                operation = Operation(
                    method=method.upper(),
                    path=template,
                    normalized_path=normalized,
                    pointer=pointer.join(item_ptr, method),
                    raw=op,
                    path_item=item,
                    path_item_pointer=item_ptr,
                    deprecated=op.get("deprecated") is True,
                    operation_id=op.get("operationId")
                    if isinstance(op.get("operationId"), str)
                    else None,
                )
                operation.parameters = self._collect_parameters(operation)
                operations[key] = operation
        return operations

    def _collect_parameters(self, op: Operation) -> dict[tuple[str, str], Parameter]:
        result: dict[tuple[str, str], Parameter] = {}
        names = path_param_names(op.path)
        sources = [
            (op.path_item.get("parameters"), pointer.join(op.path_item_pointer, "parameters")),
            (op.raw.get("parameters"), pointer.join(op.pointer, "parameters")),
        ]
        for params, base in sources:  # operation-level entries override path-level ones
            if not isinstance(params, list):
                continue
            for index, entry in enumerate(params):
                raw, where = self.deref(entry, pointer.join(base, index))
                if not isinstance(raw, dict):
                    continue
                name, location = raw.get("name"), raw.get("in")
                if not isinstance(name, str) or location not in DEFAULT_STYLE:
                    continue
                if location == "header" and name.lower() in IGNORED_HEADERS:
                    continue
                if location == "path":
                    # Identify path params by position so a rename is not "removed + added".
                    if name not in names:
                        continue
                    key = ("path", str(names.index(name)))
                elif location == "header":
                    key = ("header", name.lower())
                else:
                    key = (location, name)
                schema, schema_ptr = self._parameter_schema(raw, where)
                style = raw.get("style") if isinstance(raw.get("style"), str) else None
                style = style or DEFAULT_STYLE[location]
                explode = raw.get("explode")
                result[key] = Parameter(
                    key=key,
                    name=name,
                    location=location,
                    required=location == "path" or raw.get("required") is True,
                    pointer=where,
                    schema=schema,
                    schema_pointer=schema_ptr,
                    style=style,
                    explode=explode if isinstance(explode, bool) else style == "form",
                    raw=raw,
                )
        return result

    @staticmethod
    def _parameter_schema(raw: JsonObject, where: str) -> tuple[Any, str]:
        if "schema" in raw:
            return raw["schema"], pointer.join(where, "schema")
        content = raw.get("content")
        if isinstance(content, dict) and content:
            media = sorted(content)[0]
            media_obj = content[media]
            if isinstance(media_obj, dict) and "schema" in media_obj:
                return media_obj["schema"], pointer.join(where, "content", media, "schema")
        return None, where

    # -------------------------------------------------------------- security
    def security_schemes(self) -> dict[str, Any]:
        components = self.raw.get("components")
        if not isinstance(components, dict):
            return {}
        schemes = components.get("securitySchemes")
        if not isinstance(schemes, dict):
            return {}
        resolved: dict[str, Any] = {}
        base = "/components/securitySchemes"
        for name, scheme in schemes.items():
            resolved[name], _ = self.deref(scheme, pointer.join(base, name))
        return resolved

    def effective_security(self, op: Operation) -> tuple[Any, str]:
        """Returns (requirement list or None, pointer of where it is declared)."""
        if "security" in op.raw:
            return op.raw["security"], pointer.join(op.pointer, "security")
        return self.raw.get("security"), "/security"
