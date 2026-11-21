"""Generate executable pytest contract tests from an OpenAPI specification.

Design:
* The generated ``.py`` files are fixed templates shipped with this package.
  Everything taken from the specification goes into ``operations.json`` as
  data, so a hostile spec cannot inject code into the test suite.
* Inputs come only from what the spec provides (examples, defaults, enums).
  An operation whose required inputs cannot be filled is emitted as an
  explicit, visible ``pytest.skip`` with the reason; nothing is invented.
* Only safe methods (GET, HEAD, OPTIONS) are exercised unless the caller opts
  in, because a smoke test aimed at the wrong base URL must not change data.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from apisentinel import __version__, pointer
from apisentinel.document import Document, Operation, Parameter
from apisentinel.engine import LoadedSpec

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
TEMPLATE_FILES = ("conftest.py", "test_contract.py", "_apisentinel_runtime.py")
REQUIREMENTS = "pytest==9.2.0\njsonschema==4.26.0\n"
PYTEST_INI = "[pytest]\naddopts = -ra\n"
_JSON_MEDIA = re.compile(r"^application/(.+\+)?json$")
_SCHEMA_REF = "#/components/schemas/"


@dataclass(frozen=True, slots=True)
class GenerationOptions:
    include_unsafe_methods: bool = False
    default_base_url: str | None = None


@dataclass(slots=True)
class GeneratedSuite:
    files: dict[str, str]
    operations: list[dict[str, Any]]

    def summary(self) -> dict[str, int]:
        ready = sum(1 for o in self.operations if o["status"] == "ready")
        return {
            "total": len(self.operations),
            "ready": ready,
            "skipped": len(self.operations) - ready,
            "schemaValidated": sum(
                1 for o in self.operations if o["status"] == "ready" and o["responseSchemas"]
            ),
        }


class _SkipError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(slots=True)
class _Value:
    value: Any
    source: str


@dataclass(slots=True)
class _OperationBuilder:
    doc: Document
    op: Operation
    notes: list[str] = field(default_factory=list)
    sources: dict[str, str] = field(default_factory=dict)


# ------------------------------------------------------------ example lookup
def _example(doc: Document, container: dict[str, Any], schema: Any, where: str) -> _Value | None:
    """First usable value from: example, examples, schema example(s), default, const, enum."""
    if "example" in container:
        return _Value(container["example"], "example")
    examples = container.get("examples")
    if isinstance(examples, dict):
        for name in sorted(examples):
            resolved, _ = doc.deref(examples[name], pointer.join(where, "examples", name))
            if isinstance(resolved, dict) and "value" in resolved:
                return _Value(resolved["value"], f"example '{name}'")
    if schema is None:
        return None
    resolved_schema, _ = doc.deref(schema, where)
    if not isinstance(resolved_schema, dict):
        return None
    if "example" in resolved_schema:
        return _Value(resolved_schema["example"], "schema example")
    schema_examples = resolved_schema.get("examples")
    if isinstance(schema_examples, list) and schema_examples:
        return _Value(schema_examples[0], "schema examples[0]")
    if "default" in resolved_schema:
        return _Value(resolved_schema["default"], "schema default")
    if "const" in resolved_schema:
        return _Value(resolved_schema["const"], "schema const")
    enum = resolved_schema.get("enum")
    if isinstance(enum, list) and enum:
        return _Value(enum[0], "first enum value")
    return None


# ---------------------------------------------------- schema -> JSON Schema
def _convert_schema(node: Any, family: str, *, strip_write_only: bool) -> Any:
    """Convert an OpenAPI schema to JSON Schema 2020-12 (3.0 nullable/exclusive* aware)."""
    if isinstance(node, list):
        return [_convert_schema(n, family, strip_write_only=strip_write_only) for n in node]
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in {"properties", "patternProperties", "$defs", "definitions"} and isinstance(
            value, dict
        ):
            out[key] = {
                k: _convert_schema(v, family, strip_write_only=strip_write_only)
                for k, v in value.items()
            }
        elif key in {"discriminator", "xml", "externalDocs", "example"}:
            continue
        else:
            out[key] = _convert_schema(value, family, strip_write_only=strip_write_only)
    if family == "3.0":
        if out.pop("nullable", False) is True:
            if isinstance(out.get("type"), str):
                out["type"] = [out["type"], "null"]
            if isinstance(out.get("enum"), list) and None not in out["enum"]:
                out["enum"] = [*out["enum"], None]
        for bound, flag in (("minimum", "exclusiveMinimum"), ("maximum", "exclusiveMaximum")):
            if out.get(flag) is True and bound in out:
                out[flag] = out.pop(bound)
            elif isinstance(out.get(flag), bool):
                out.pop(flag)
    if strip_write_only and isinstance(out.get("properties"), dict):
        # A server never returns writeOnly properties, so they cannot be required in a response.
        hidden = {
            name
            for name, prop in out["properties"].items()
            if isinstance(prop, dict) and prop.get("writeOnly") is True
        }
        if hidden and isinstance(out.get("required"), list):
            out["required"] = [r for r in out["required"] if r not in hidden]
    return out


def _refs(node: Any) -> set[str]:
    found: set[str] = set()
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            ref = current.get("$ref")
            if isinstance(ref, str):
                found.add(ref)
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return found


# ------------------------------------------------------------ the generator
class ContractTestGenerator:
    def __init__(self, loaded: LoadedSpec, options: GenerationOptions | None = None) -> None:
        self.loaded = loaded
        self.doc = loaded.document
        self.options = options or GenerationOptions()
        self.family = self.doc.version_family
        components = self.doc.raw.get("components")
        raw_schemas = components.get("schemas") if isinstance(components, dict) else None
        self.components = {
            "schemas": {
                name: _convert_schema(schema, self.family, strip_write_only=True)
                for name, schema in (raw_schemas or {}).items()
            }
            if isinstance(raw_schemas, dict)
            else {}
        }
        self.schemes = self.doc.security_schemes()

    # ----------------------------------------------------------------- params
    def _parameter(self, b: _OperationBuilder, param: Parameter) -> dict[str, Any] | None:
        label = f"{param.location}.{param.name}"
        found = _example(self.doc, param.raw, param.schema, param.schema_pointer)
        if found is None:
            if param.required:
                raise _SkipError(
                    f"required {param.location} parameter '{param.name}' has no example, "
                    "default or enum value in the specification"
                )
            return None
        if not param.required:
            return None  # optional parameters are omitted: fewer assumptions about the server
        value = found.value
        if isinstance(value, dict):
            raise _SkipError(
                f"object-valued {param.location} parameter '{param.name}' is not supported"
            )
        if param.location in {"header", "cookie"} and any(c in str(value) for c in "\r\n;"):
            raise _SkipError(f"{param.location} parameter '{param.name}' example contains control "
                        "characters")  # fmt: skip
        if param.location == "query" and param.style not in {
            "form",
            "spaceDelimited",
            "pipeDelimited",
        }:
            raise _SkipError(f"query parameter style '{param.style}' is not supported")
        b.sources[label] = found.source
        return {"value": value, "style": param.style, "explode": param.explode}

    # -------------------------------------------------------------------- body
    def _body(self, b: _OperationBuilder) -> dict[str, Any]:
        empty = {"hasBody": False, "body": None, "contentType": None}
        if "requestBody" not in b.op.raw:
            return empty
        body, where = self.doc.deref(b.op.raw["requestBody"],
                                     pointer.join(b.op.pointer, "requestBody"))  # fmt: skip
        if not isinstance(body, dict) or body.get("required") is not True:
            return empty
        content = body.get("content") if isinstance(body.get("content"), dict) else {}
        assert isinstance(content, dict)
        json_types = sorted(m for m in content if _JSON_MEDIA.match(m.split(";")[0].strip()))
        if not json_types:
            raise _SkipError("required request body has no JSON media type")
        media = json_types[0]
        media_obj = content[media] if isinstance(content[media], dict) else {}
        found = _example(self.doc, media_obj, media_obj.get("schema"),
                         pointer.join(where, "content", media, "schema"))  # fmt: skip
        if found is None or found.source == "first enum value":
            raise _SkipError("required request body has no example in the specification")
        b.sources["body"] = found.source
        return {"hasBody": True, "body": found.value, "contentType": media}

    # -------------------------------------------------------------------- auth
    def _requires_auth(self, op: Operation) -> bool:
        raw, _ = self.doc.effective_security(op)
        return isinstance(raw, list) and bool(raw) and not any(a == {} for a in raw)

    def _auth(self, op: Operation) -> dict[str, Any] | None:
        raw, _ = self.doc.effective_security(op)
        if not isinstance(raw, list) or not raw or any(a == {} for a in raw):
            return None
        reasons = []
        for alternative in raw:
            if not isinstance(alternative, dict) or len(alternative) != 1:
                reasons.append("requires several schemes at once")
                continue
            name = next(iter(alternative))
            scheme = self.schemes.get(name)
            if not isinstance(scheme, dict):
                reasons.append(f"scheme '{name}' is undefined")
                continue
            kind = scheme.get("type")
            http_scheme = str(scheme.get("scheme", "")).lower()
            if kind == "http" and http_scheme in {"bearer", "basic"}:
                return {"scheme": name, "kind": http_scheme}
            if kind in {"oauth2", "openIdConnect"}:
                return {"scheme": name, "kind": "bearer"}
            if kind == "apiKey" and scheme.get("in") in {"header", "query", "cookie"}:
                return {"scheme": name, "kind": "apiKey", "in": scheme["in"],
                        "name": scheme.get("name")}  # fmt: skip
            reasons.append(f"scheme '{name}' ({kind}) is not supported")
        raise _SkipError("authentication not supported: " + "; ".join(reasons))

    # --------------------------------------------------------------- responses
    def _responses(self, b: _OperationBuilder) -> tuple[list[str], dict[str, Any]]:
        raw = b.op.raw.get("responses") if isinstance(b.op.raw.get("responses"), dict) else {}
        assert isinstance(raw, dict)
        codes = (str(s).upper() for s in raw)
        expected = sorted(c for c in codes if c == "2XX" or (c.isdigit() and c.startswith("2")))
        if not expected:
            raise _SkipError("no documented 2xx response to assert against")
        schemas: dict[str, Any] = {}
        for status in expected:
            original = next(s for s in raw if str(s).upper() == status)
            where = pointer.join(b.op.pointer, "responses", original)
            resolved, _ = self.doc.deref(raw[original], where)
            content = resolved.get("content") if isinstance(resolved, dict) else None
            if not isinstance(content, dict) or not content:
                continue
            json_types = sorted(m for m in content if _JSON_MEDIA.match(m.split(";")[0].strip()))
            if not json_types:
                b.notes.append(f"response {status} body not validated (non-JSON media type)")
                continue
            media_obj = content[json_types[0]]
            schema = media_obj.get("schema") if isinstance(media_obj, dict) else None
            if schema is None:
                continue
            outside = {r for r in _refs(schema) if not r.startswith(_SCHEMA_REF)}
            if outside:
                b.notes.append(f"response {status} body not validated (unsupported $ref)")
                continue
            converted = _convert_schema(schema, self.family, strip_write_only=True)
            try:
                Draft202012Validator.check_schema({"allOf": [converted]})
            except SchemaError:
                b.notes.append(f"response {status} body not validated (schema not usable)")
                continue
            schemas[status] = {"allOf": [converted]}
        return expected, schemas

    # --------------------------------------------------------------- operation
    def _operation(self, op: Operation) -> dict[str, Any]:
        b = _OperationBuilder(self.doc, op)
        record: dict[str, Any] = {
            "id": f"{op.method} {op.path}",
            "method": op.method,
            "path": op.path,
            "operationId": op.operation_id,
            "status": "ready",
            "skipReason": None,
            "request": {"path": {}, "query": {}, "header": {}, "cookie": {},
                        "hasBody": False, "body": None, "contentType": None},
            "auth": None,
            "requiresAuth": self._requires_auth(op),
            "expectedStatuses": [],
            "responseSchemas": {},
            "inputSources": {},
            "notes": b.notes,
        }  # fmt: skip
        try:
            if op.method not in SAFE_METHODS and not self.options.include_unsafe_methods:
                raise _SkipError(
                    f"{op.method} changes server state; enable unsafe methods to test it"
                )
            for param in sorted(op.parameters.values(), key=lambda p: (p.location, p.name)):
                spec = self._parameter(b, param)
                if spec is not None:
                    record["request"][param.location][param.name] = spec
            record["request"].update(self._body(b))
            record["auth"] = self._auth(op)
            record["expectedStatuses"], record["responseSchemas"] = self._responses(b)
        except _SkipError as skip:
            record["status"] = "skipped"
            record["skipReason"] = skip.reason
        record["inputSources"] = b.sources
        return record

    def generate(self) -> GeneratedSuite:
        operations = [
            self._operation(op)
            for _, op in sorted(self.doc.operations.items(), key=lambda kv: (kv[0][1], kv[0][0]))
        ]
        info = self.loaded.info
        data = {
            "generator": f"apisentinel {__version__}",
            "api": {"title": info.title, "version": info.api_version,
                    "openapiVersion": info.openapi_version},
            "defaultBaseUrl": self.options.default_base_url,
            "components": self.components,
            "operations": operations,
        }  # fmt: skip
        package = resources.files("apisentinel") / "templates" / "contract_tests"
        files = {
            name: (package / f"{name}.template").read_text(encoding="utf-8")
            for name in TEMPLATE_FILES
        }
        files["operations.json"] = json.dumps(data, indent=2, sort_keys=False) + "\n"
        files["requirements.txt"] = REQUIREMENTS
        files["pytest.ini"] = PYTEST_INI
        return GeneratedSuite(files=files, operations=copy.deepcopy(operations))


def generate_contract_tests(
    loaded: LoadedSpec, options: GenerationOptions | None = None
) -> GeneratedSuite:
    return ContractTestGenerator(loaded, options).generate()


def write_suite(suite: GeneratedSuite, directory: Path, *, overwrite: bool = False) -> list[Path]:
    """Write the suite's files. Never touches other files in ``directory``.

    Raises:
        FileExistsError: if a generated file already exists and ``overwrite`` is False.
    """
    targets = [directory / name for name in sorted(suite.files)]
    existing = [t for t in targets if t.exists()]
    if existing and not overwrite:
        names = ", ".join(t.name for t in existing)
        raise FileExistsError(f"{directory} already contains {names}; use --overwrite to replace")
    directory.mkdir(parents=True, exist_ok=True)
    for target in targets:
        target.write_text(suite.files[target.name], encoding="utf-8", newline="\n")
    return targets
