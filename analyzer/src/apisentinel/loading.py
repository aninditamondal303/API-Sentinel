"""Safe loading of OpenAPI documents from untrusted bytes.

Threats handled here, because specs are user uploads:

* Oversized input (memory exhaustion)       -> hard byte limit before parsing.
* YAML alias expansion ("billion laughs")    -> aliases are allowed (real specs use
  anchors), but the alias count and the fully expanded node count are capped.
* Deeply nested documents (stack exhaustion) -> nesting depth limit.
* Duplicate mapping keys                     -> rejected; silently keeping the
  last value would make two tools disagree about what the spec says.
* YAML implicit types                        -> timestamps stay strings, and
  non-string keys (``200:``) become strings, so the result is plain JSON data.
"""

from __future__ import annotations

import json
import math
from collections.abc import Hashable
from pathlib import PurePath
from typing import Any

import yaml
from yaml.events import AliasEvent
from yaml.nodes import MappingNode, Node

from apisentinel.errors import Issue, SpecLoadError

DEFAULT_MAX_BYTES = 5 * 1024 * 1024
MAX_DEPTH = 100
MAX_ALIASES = 10_000
MAX_EXPANDED_NODES = 2_000_000

JsonObject = dict[str, Any]


class _SafeSpecLoader(yaml.SafeLoader):
    """SafeLoader with bounded aliases, no duplicate keys and no implicit timestamps."""

    _alias_count = 0

    def compose_node(self, parent: Node | None, index: int) -> Node | None:
        if self.check_event(AliasEvent):
            self._alias_count += 1
            if self._alias_count > MAX_ALIASES:
                raise SpecLoadError(
                    code="SPEC_PARSE_ERROR",
                    message=f"Document uses more than {MAX_ALIASES} YAML aliases.",
                )
        return super().compose_node(parent, index)

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[Hashable, Any]:
        seen: set[Any] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            marker = str(key)
            if marker in seen:
                raise SpecLoadError(
                    code="SPEC_PARSE_ERROR",
                    message=(f"Duplicate key '{marker}' at line {key_node.start_mark.line + 1}."),
                )
            seen.add(marker)
        return super().construct_mapping(node, deep=deep)


# Drop the timestamp resolver: `example: 2024-01-01` must stay the string "2024-01-01".
_SafeSpecLoader.yaml_implicit_resolvers = {
    first_char: [r for r in resolvers if r[0] != "tag:yaml.org,2002:timestamp"]
    for first_char, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            raise SpecLoadError(code="SPEC_PARSE_ERROR", message=f"Duplicate key '{key}'.")
        result[key] = value
    return result


def _detect_format(text: str, filename: str | None) -> str:
    if filename:
        suffix = PurePath(filename).suffix.lower()
        if suffix == ".json":
            return "json"
        if suffix in {".yaml", ".yml"}:
            return "yaml"
    return "json" if text.lstrip().startswith("{") else "yaml"


def _normalize(value: Any) -> Any:
    """Convert to plain JSON data (string keys) and enforce the depth limit.

    Iterative rather than recursive so a hostile document cannot exhaust the
    Python stack before the limit is checked.
    """
    root_holder: list[Any] = [None]
    stack: list[tuple[Any, Any, Any, int]] = [(value, root_holder, 0, 0)]
    visited = 0
    while stack:
        current, parent, key, depth = stack.pop()
        visited += 1
        if visited > MAX_EXPANDED_NODES:
            # Shared YAML anchors are copied here, so exponential alias bombs stop at this cap.
            raise SpecLoadError(
                code="SPEC_PARSE_ERROR",
                message=f"Document expands to more than {MAX_EXPANDED_NODES} nodes.",
            )
        if depth > MAX_DEPTH:
            raise SpecLoadError(
                code="SPEC_PARSE_ERROR",
                message=f"Document nesting is deeper than {MAX_DEPTH} levels.",
            )
        if isinstance(current, dict):
            container: dict[str, Any] = {}
            parent[key] = container
            for child_key, child in current.items():
                if child_key is None or isinstance(child_key, (dict, list)):
                    raise SpecLoadError(
                        code="SPEC_PARSE_ERROR",
                        message="Mapping keys must be scalar values.",
                    )
                normalized_key = (
                    str(child_key).lower() if isinstance(child_key, bool) else str(child_key)
                )
                container[normalized_key] = None
                stack.append((child, container, normalized_key, depth + 1))
        elif isinstance(current, list):
            items: list[Any] = [None] * len(current)
            parent[key] = items
            for index, child in enumerate(current):
                stack.append((child, items, index, depth + 1))
        elif isinstance(current, float) and math.isnan(current):
            raise SpecLoadError(code="SPEC_PARSE_ERROR", message="NaN is not valid JSON data.")
        else:
            parent[key] = current
    return root_holder[0]


def load_document(
    data: bytes,
    filename: str | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> JsonObject:
    """Parse untrusted bytes into a JSON-compatible mapping.

    Raises:
        SpecLoadError: on size, encoding or syntax problems, or if the document
            is not a mapping at the top level.
    """
    if len(data) > max_bytes:
        raise SpecLoadError(
            code="SPEC_TOO_LARGE",
            message=f"Specification is {len(data)} bytes; the limit is {max_bytes} bytes.",
        )
    if not data.strip():
        raise SpecLoadError(code="SPEC_PARSE_ERROR", message="Specification file is empty.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SpecLoadError(
            code="SPEC_PARSE_ERROR",
            message=f"Specification is not valid UTF-8 (byte offset {exc.start}).",
        ) from None

    fmt = _detect_format(text, filename)
    try:
        if fmt == "json":
            raw: Any = json.loads(text, object_pairs_hook=_reject_duplicate_json_keys)
        else:
            raw = yaml.load(text, Loader=_SafeSpecLoader)
    except SpecLoadError:
        raise
    except json.JSONDecodeError as exc:
        raise SpecLoadError(
            code="SPEC_PARSE_ERROR",
            message=f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}.",
        ) from None
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        problem = getattr(exc, "problem", None) or "syntax error"
        raise SpecLoadError(
            code="SPEC_PARSE_ERROR", message=f"Invalid YAML{where}: {problem}."
        ) from None
    except RecursionError:
        raise SpecLoadError(
            code="SPEC_PARSE_ERROR", message="Document nesting is too deep to parse."
        ) from None

    if not isinstance(raw, dict):
        raise SpecLoadError(
            code="SPEC_PARSE_ERROR",
            message="The top level of an OpenAPI document must be a mapping.",
            issues=[Issue(message="Expected an object at the document root.", pointer="")],
        )
    normalized: JsonObject = _normalize(raw)
    return normalized
