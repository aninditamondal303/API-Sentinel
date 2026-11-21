"""Direction-aware comparison of two JSON Schemas inside OpenAPI documents.

The key idea: whether a change breaks clients depends on who *writes* the data.

* REQUEST  (client writes, server validates): accepting FEWER values breaks.
* RESPONSE (server writes, client parses):    producing MORE/DIFFERENT values breaks.

The comparator emits abstract change *kinds* (``TYPE_NARROWED``,
``PROPERTY_REMOVED`` ...). A per-context ``kind -> rule id`` map turns them into
catalog rules, so the same walk serves parameters, request bodies and
responses. Anything the engine cannot reason about soundly is emitted as a
manual-review kind instead of being silently treated as safe.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from apisentinel import pointer
from apisentinel.document import Document, RefCycleError

MAX_DEPTH = 64
REQUEST = "request"
RESPONSE = "response"

# Keywords whose semantics the engine does not model. A change to any of them
# becomes a manual-review finding rather than a silent pass.
UNSUPPORTED_KEYWORDS = (
    "not",
    "if",
    "then",
    "else",
    "patternProperties",
    "unevaluatedProperties",
    "unevaluatedItems",
    "dependentSchemas",
    "dependentRequired",
    "prefixItems",
    "contains",
    "propertyNames",
    "$dynamicRef",
)
_ALLOF_MERGEABLE_KEYS = {
    "type", "properties", "required", "description", "title", "example", "examples",
    "readOnly", "writeOnly", "deprecated", "nullable", "externalDocs", "xml",
}  # fmt: skip

# Shared manual-review kinds map to the same rules in every context.
MANUAL_REVIEW_KINDS = {
    "COMPOSITION_CHANGED": "MR-001",
    "UNSUPPORTED_KEYWORD": "MR-002",
    "DISCRIMINATOR_CHANGED": "MR-003",
    "NOT_COMPARED": "MR-004",
}

PARAMETER_RULES = {
    "TYPE_NARROWED": "REQ-PARAM-004",
    "ENUM_NARROWED": "REQ-PARAM-005",
    "CONSTRAINT_TIGHTENED": "REQ-PARAM-006",
    "DEFAULT_CHANGED": "REQ-PARAM-008",
    "PATTERN_CHANGED": "REQ-PARAM-009",
    "FORMAT_CHANGED": "REQ-PARAM-011",
    "PROPERTY_REQUIRED_ADDED": "REQ-PARAM-012",
    "PROPERTY_BECAME_REQUIRED": "REQ-PARAM-012",
    "PROPERTY_REMOVED_STRICT": "REQ-PARAM-012",
    "PROPERTY_REMOVED": "REQ-PARAM-012",
    "ADDITIONAL_PROPERTIES_RESTRICTED": "REQ-PARAM-012",
    **MANUAL_REVIEW_KINDS,
}
REQUEST_BODY_RULES = {
    "TYPE_NARROWED": "REQ-BODY-007",
    "FORMAT_CHANGED": "REQ-BODY-008",
    "ENUM_NARROWED": "REQ-BODY-009",
    "CONSTRAINT_TIGHTENED": "REQ-BODY-010",
    "PATTERN_CHANGED": "REQ-BODY-013",
    "DEFAULT_CHANGED": "REQ-BODY-014",
    "PROPERTY_REQUIRED_ADDED": "REQ-BODY-003",
    "PROPERTY_BECAME_REQUIRED": "REQ-BODY-004",
    "PROPERTY_REMOVED_STRICT": "REQ-BODY-005",
    "PROPERTY_REMOVED": "REQ-BODY-006",
    "ADDITIONAL_PROPERTIES_RESTRICTED": "REQ-BODY-011",
    "PROPERTY_ADDED_OPTIONAL": "REQ-BODY-012",
    **MANUAL_REVIEW_KINDS,
}
RESPONSE_RULES = {
    "TYPE_CHANGED": "RES-007",
    "NULLABLE_ADDED": "RES-008",
    "SHAPE_CHANGED": "RES-011",
    "ENUM_WIDENED": "RES-009",
    "ENUM_VALUES_REMOVED": "RES-010",
    "FORMAT_CHANGED": "RES-012",
    "PROPERTY_REMOVED": "RES-005",
    "PROPERTY_BECAME_OPTIONAL": "RES-006",
    "PROPERTY_ADDED": "RES-013",
    "CONSTRAINT_RELAXED": "RES-014",
    "PATTERN_CHANGED": "RES-015",
    **MANUAL_REVIEW_KINDS,
}

PROPERTY_KIND_TEXT = {
    "PROPERTY_REQUIRED_ADDED": "a new required property was added",
    "PROPERTY_BECAME_REQUIRED": "a property became required",
    "PROPERTY_REMOVED_STRICT": "a property was removed and extra properties are rejected",
    "PROPERTY_REMOVED": "a property was removed",
    "PROPERTY_ADDED_OPTIONAL": "an optional property was added",
    "PROPERTY_BECAME_OPTIONAL": "a property became optional",
    "PROPERTY_ADDED": "a property was added",
}

# Kinds whose most useful location is in the baseline (the thing that disappeared).
BASELINE_LOCATED_KINDS = {"PROPERTY_REMOVED", "PROPERTY_REMOVED_STRICT", "ENUM_VALUES_REMOVED"}

Emit = Callable[..., None]


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


@dataclass(slots=True)
class SchemaView:
    """A schema with allOf flattened and the real pointer of each property."""

    node: dict[str, Any]
    pointer: str
    property_pointers: dict[str, str] = field(default_factory=dict)

    @property
    def properties(self) -> dict[str, Any]:
        props = self.node.get("properties")
        return props if isinstance(props, dict) else {}

    @property
    def required(self) -> set[str]:
        req = self.node.get("required")
        return {r for r in req if isinstance(r, str)} if isinstance(req, list) else set()


@dataclass(slots=True)
class WalkState:
    old_doc: Document
    new_doc: Document
    direction: str
    rules: dict[str, str]
    emit: Emit
    visited: set[tuple[str, str]] = field(default_factory=set)


# ---------------------------------------------------------------- helpers
def schema_types(node: dict[str, Any], family: str) -> frozenset[str] | None:
    """Set of JSON types a schema admits, or None for "any type"."""
    raw = node.get("type")
    if isinstance(raw, str):
        types = {raw}
    elif isinstance(raw, list):
        types = {t for t in raw if isinstance(t, str)}
    elif "properties" in node or "additionalProperties" in node:
        types = {"object"}
    elif "items" in node:
        types = {"array"}
    else:
        return None
    if family == "3.0" and node.get("nullable") is True:
        types.add("null")
    return frozenset(types)


def covers(wide: frozenset[str] | None, narrow: frozenset[str] | None) -> bool:
    """True if every value of type set ``narrow`` is allowed by ``wide``."""
    if wide is None:
        return True
    if narrow is None:
        return False
    return all(t in wide or (t == "integer" and "number" in wide) for t in narrow)


def _type_label(types: frozenset[str] | None) -> str:
    return "any" if types is None else "|".join(sorted(types))


def enum_values(node: dict[str, Any]) -> dict[str, Any] | None:
    if "const" in node:
        return {canonical(node["const"]): node["const"]}
    values = node.get("enum")
    if isinstance(values, list):
        return {canonical(v): v for v in values}
    return None


def _num(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _bound(node: dict[str, Any], family: str, lower: bool) -> tuple[Decimal, bool] | None:
    """Effective (value, exclusive) bound, unifying 3.0 boolean and 3.1 numeric forms."""
    incl_key, excl_key = (
        ("minimum", "exclusiveMinimum") if lower else ("maximum", "exclusiveMaximum")
    )
    inclusive = _num(node.get(incl_key))
    excl_raw = node.get(excl_key)
    candidates: list[tuple[Decimal, bool]] = []
    if family == "3.0":
        if inclusive is not None:
            candidates.append((inclusive, excl_raw is True))
    else:
        if inclusive is not None:
            candidates.append((inclusive, False))
        exclusive = _num(excl_raw)
        if exclusive is not None:
            candidates.append((exclusive, True))
    if not candidates:
        return None

    def strictness(c: tuple[Decimal, bool]) -> tuple[Decimal, bool]:
        return (c[0], c[1]) if lower else (-c[0], c[1])

    return max(candidates, key=strictness)


def _tighter_bound(
    old: tuple[Decimal, bool] | None, new: tuple[Decimal, bool] | None, lower: bool
) -> bool:
    if new is None:
        return False
    if old is None:
        return True
    if new[0] != old[0]:
        return new[0] > old[0] if lower else new[0] < old[0]
    return new[1] and not old[1]


def _fmt_bound(bound: tuple[Decimal, bool] | None, lower: bool) -> str | None:
    if bound is None:
        return None
    op = (">" if bound[1] else ">=") if lower else ("<" if bound[1] else "<=")
    return f"{op} {bound[0]}"


def constraint_changes(
    old: dict[str, Any], new: dict[str, Any], old_family: str, new_family: str
) -> tuple[list[str], list[str]]:
    """Return (tightened, relaxed) human descriptions."""
    tightened: list[str] = []
    relaxed: list[str] = []

    for lower in (True, False):
        o, n = _bound(old, old_family, lower), _bound(new, new_family, lower)
        label = "minimum" if lower else "maximum"
        if _tighter_bound(o, n, lower):
            tightened.append(f"{label} {_fmt_bound(o, lower) or 'none'} -> {_fmt_bound(n, lower)}")
        elif _tighter_bound(n, o, lower):
            relaxed.append(f"{label} {_fmt_bound(o, lower)} -> {_fmt_bound(n, lower) or 'none'}")

    for key, is_min in (
        ("minLength", True), ("maxLength", False), ("minItems", True), ("maxItems", False),
        ("minProperties", True), ("maxProperties", False),
    ):  # fmt: skip
        o_val, n_val = _num(old.get(key)), _num(new.get(key))
        if o_val == n_val:
            continue
        if is_min:
            o_eff, n_eff = o_val or Decimal(0), n_val or Decimal(0)
            if n_eff > o_eff:
                tightened.append(f"{key} {o_val} -> {n_val}")
            elif n_eff < o_eff:
                relaxed.append(f"{key} {o_val} -> {n_val}")
        elif n_val is not None and (o_val is None or n_val < o_val):
            tightened.append(f"{key} {o_val} -> {n_val}")
        else:
            relaxed.append(f"{key} {o_val} -> {n_val}")

    if old.get("uniqueItems") is not True and new.get("uniqueItems") is True:
        tightened.append("uniqueItems false -> true")
    elif old.get("uniqueItems") is True and new.get("uniqueItems") is not True:
        relaxed.append("uniqueItems true -> false")

    o_mult, n_mult = _num(old.get("multipleOf")), _num(new.get("multipleOf"))
    if o_mult != n_mult:
        desc = f"multipleOf {o_mult} -> {n_mult}"
        # New multiples-of-N are a subset of old multiples-of-M exactly when N is a multiple of M.
        new_is_subset = n_mult is not None and (o_mult is None or n_mult % o_mult == 0)
        old_is_subset = o_mult is not None and (n_mult is None or o_mult % n_mult == 0)
        if not old_is_subset:
            tightened.append(desc)
        if not new_is_subset:
            relaxed.append(desc)
    return tightened, relaxed


# ------------------------------------------------------------- allOf merge
def flatten(doc: Document, node: Any, where: str, depth: int = 0) -> SchemaView | None:
    """Resolve refs and merge simple object-only allOf. None if not safely mergeable."""
    node, where = doc.deref(node, where)
    if not isinstance(node, dict):
        return None
    props_ptrs = {
        name: pointer.join(where, "properties", name)
        for name in (node.get("properties") or {})
        if isinstance(node.get("properties"), dict)
    }
    if "allOf" not in node:
        return SchemaView(node=node, pointer=where, property_pointers=props_ptrs)
    if depth > 8 or not isinstance(node["allOf"], list):
        return None

    merged: dict[str, Any] = {k: v for k, v in node.items() if k != "allOf"}
    properties: dict[str, Any] = dict(merged.get("properties") or {})
    required: set[str] = set(merged.get("required") or [])
    for index, sub in enumerate(node["allOf"]):
        view = flatten(doc, sub, pointer.join(where, "allOf", index), depth + 1)
        if view is None or not set(view.node) <= _ALLOF_MERGEABLE_KEYS:
            return None
        sub_types = schema_types(view.node, doc.version_family)
        if sub_types is not None and sub_types != frozenset({"object"}):
            return None
        for name, prop in view.properties.items():
            if name in properties and canonical(properties[name]) != canonical(prop):
                return None
            properties[name] = prop
            props_ptrs[name] = view.property_pointers[name]
        required |= view.required
    merged["type"] = merged.get("type", "object")
    merged["properties"] = properties
    if required:
        merged["required"] = sorted(required)
    return SchemaView(node=merged, pointer=where, property_pointers=props_ptrs)


# ------------------------------------------------------------------ walker
def compare_schema(
    state: WalkState,
    old: Any,
    old_ptr: str,
    new: Any,
    new_ptr: str,
    field_name: str,
    *,
    depth: int = 0,
    is_root: bool = False,
) -> None:
    """Compare two schemas, emitting change kinds through ``state.emit``."""

    def emit(kind: str, **kwargs: Any) -> None:
        rule_id = state.rules.get(kind)
        if rule_id is None:
            return
        baseline = kind in BASELINE_LOCATED_KINDS
        state.emit(
            rule_id,
            location=kwargs.pop("location", old_ptr if baseline else new_ptr),
            baseline_location=baseline,
            field=field_name,
            **kwargs,
        )

    if old is None and new is None:
        return
    if depth > MAX_DEPTH:
        # Only flag it if something below this point could actually differ.
        unchanged = canonical(old) == canonical(new) and canonical(
            state.old_doc.raw.get("components")
        ) == canonical(state.new_doc.raw.get("components"))
        if not unchanged:
            emit("NOT_COMPARED", detail=f"schema nesting deeper than {MAX_DEPTH} levels")
        return
    try:
        old_view = flatten(state.old_doc, old, old_ptr) if old is not None else None
        new_view = flatten(state.new_doc, new, new_ptr) if new is not None else None
    except RefCycleError:
        emit("NOT_COMPARED", detail="a $ref chain refers to itself")
        return

    if old_view is None or new_view is None:
        _compare_unflattenable(state, old, old_ptr, new, new_ptr, emit)
        return

    old_ptr, new_ptr = old_view.pointer, new_view.pointer
    visit_key = (old_ptr, new_ptr)
    if visit_key in state.visited:  # recursive schema already being compared
        return
    state.visited.add(visit_key)

    o, n = old_view.node, new_view.node
    old_family, new_family = state.old_doc.version_family, state.new_doc.version_family

    # Composition and unsupported keywords: never assume safe.
    for keyword in ("oneOf", "anyOf"):
        _compare_variants(state, o, old_ptr, n, new_ptr, keyword, field_name, depth, emit)
    for keyword in UNSUPPORTED_KEYWORDS:
        if canonical(o.get(keyword)) != canonical(n.get(keyword)):
            emit("UNSUPPORTED_KEYWORD", keyword=keyword, old=o.get(keyword), new=n.get(keyword))
    if canonical(o.get("discriminator")) != canonical(n.get("discriminator")):
        emit("DISCRIMINATOR_CHANGED", old=o.get("discriminator"), new=n.get("discriminator"))

    # Types.
    old_types, new_types = schema_types(o, old_family), schema_types(n, new_family)
    type_kind: str | None = None
    if state.direction == REQUEST:
        if not covers(new_types, old_types):
            type_kind = "TYPE_NARROWED"
    elif not covers(old_types, new_types):
        added = (new_types or frozenset()) - (old_types or frozenset())
        if old_types is not None and new_types is not None and added == {"null"}:
            type_kind = "NULLABLE_ADDED"
        else:
            type_kind = "SHAPE_CHANGED" if is_root else "TYPE_CHANGED"
    if type_kind:
        emit(type_kind, old=_type_label(old_types), new=_type_label(new_types))
        shared = (old_types or frozenset()) & (new_types or frozenset())
        if old_types is not None and new_types is not None and not shared:
            return  # unrelated types: deeper differences would only be noise

    _compare_scalars(state, o, n, old_family, new_family, emit)
    _compare_object(state, old_view, new_view, field_name, depth, emit)

    o_items, n_items = o.get("items"), n.get("items")
    if isinstance(o_items, dict) and isinstance(n_items, dict):
        compare_schema(
            state,
            o_items,
            pointer.join(old_ptr, "items"),
            n_items,
            pointer.join(new_ptr, "items"),
            f"{field_name}[]",
            depth=depth + 1,
        )


def _compare_unflattenable(
    state: WalkState, old: Any, old_ptr: str, new: Any, new_ptr: str, emit: Emit
) -> None:
    if old is None or new is None:
        return
    try:
        o, _ = state.old_doc.deref(old, old_ptr)
        n, _ = state.new_doc.deref(new, new_ptr)
    except RefCycleError:
        emit("NOT_COMPARED", detail="a $ref chain refers to itself")
        return
    if isinstance(o, bool) or isinstance(n, bool):
        if o != n:
            emit("UNSUPPORTED_KEYWORD", keyword="boolean schema", old=o, new=n)
        return
    if canonical(o) != canonical(n):
        emit("COMPOSITION_CHANGED", detail="allOf changed in a way that cannot be merged safely")


def _compare_variants(
    state: WalkState,
    o: dict[str, Any],
    old_ptr: str,
    n: dict[str, Any],
    new_ptr: str,
    keyword: str,
    field_name: str,
    depth: int,
    emit: Emit,
) -> None:
    old_list, new_list = o.get(keyword), n.get(keyword)
    if old_list is None and new_list is None:
        return
    if not isinstance(old_list, list) or not isinstance(new_list, list):
        action = "added" if old_list is None else "removed"
        emit("COMPOSITION_CHANGED", detail=f"{keyword} was {action}")
        return

    def recurse(i: int, j: int) -> None:
        compare_schema(
            state,
            old_list[i],
            pointer.join(old_ptr, keyword, i),
            new_list[j],
            pointer.join(new_ptr, keyword, j),
            f"{field_name}<{keyword}#{j + 1}>",
            depth=depth + 1,
        )

    if canonical(old_list) == canonical(new_list):
        for i in range(len(old_list)):
            recurse(i, i)  # same variants; referenced schemas may still differ
        return

    old_refs = [r for r in (Document.ref_name(v) for v in old_list) if r is not None]
    new_refs = [r for r in (Document.ref_name(v) for v in new_list) if r is not None]
    if len(old_refs) == len(old_list) and len(new_refs) == len(new_list):
        removed = sorted(set(old_refs) - set(new_refs))
        added = sorted(set(new_refs) - set(old_refs))
        risky = removed if state.direction == REQUEST else added
        if risky:
            verb = "no longer accepts" if state.direction == REQUEST else "may now return"
            names = ", ".join(r.rsplit("/", 1)[-1] for r in risky)
            emit("COMPOSITION_CHANGED", detail=f"{keyword} {verb} variant(s) {names}")
        for ref in sorted(set(old_refs) & set(new_refs)):
            recurse(old_refs.index(ref), new_refs.index(ref))
        return

    emit("COMPOSITION_CHANGED", detail=f"{keyword} variants changed and could not be matched")


def _compare_scalars(
    state: WalkState,
    o: dict[str, Any],
    n: dict[str, Any],
    old_family: str,
    new_family: str,
    emit: Emit,
) -> None:
    request = state.direction == REQUEST

    old_fmt, new_fmt = o.get("format"), n.get("format")
    # Request: adding/changing a format restricts input. Response: removing/changing it
    # means clients may receive values in a form they do not parse.
    if old_fmt != new_fmt and (
        (request and new_fmt is not None) or (not request and old_fmt is not None)
    ):
        emit("FORMAT_CHANGED", old=old_fmt, new=new_fmt)

    old_enum, new_enum = enum_values(o), enum_values(n)
    if request:
        if new_enum is not None and (old_enum is None or set(old_enum) - set(new_enum)):
            removed = (
                [old_enum[k] for k in sorted(set(old_enum) - set(new_enum))]
                if old_enum is not None
                else None
            )
            detail = (
                f"removed {', '.join(map(str, removed))}"
                if removed
                else f"now limited to {', '.join(map(str, new_enum.values()))}"
            )
            emit(
                "ENUM_NARROWED",
                old=list(old_enum.values()) if old_enum else None,
                new=list(new_enum.values()),
                detail=detail,
            )
    else:
        if old_enum is not None and (new_enum is None or set(new_enum) - set(old_enum)):
            added = (
                [new_enum[k] for k in sorted(set(new_enum) - set(old_enum))]
                if new_enum is not None
                else None
            )
            emit(
                "ENUM_WIDENED",
                old=list(old_enum.values()),
                new=list(new_enum.values()) if new_enum else None,
                detail=", ".join(map(str, added)) if added else "any value (enum removed)",
            )
        if old_enum is not None and new_enum is not None and set(old_enum) - set(new_enum):
            gone = [old_enum[k] for k in sorted(set(old_enum) - set(new_enum))]
            emit(
                "ENUM_VALUES_REMOVED",
                old=list(old_enum.values()),
                new=list(new_enum.values()),
                detail=", ".join(map(str, gone)),
            )

    tightened, relaxed = constraint_changes(o, n, old_family, new_family)
    if request and tightened:
        emit("CONSTRAINT_TIGHTENED", detail="; ".join(tightened))
    if not request and relaxed:
        emit("CONSTRAINT_RELAXED", detail="; ".join(relaxed))

    old_pat, new_pat = o.get("pattern"), n.get("pattern")
    if old_pat != new_pat and (
        (request and new_pat is not None) or (not request and old_pat is not None)
    ):
        emit("PATTERN_CHANGED", old=old_pat, new=new_pat)

    if request and "default" in o and canonical(o.get("default")) != canonical(n.get("default")):
        emit("DEFAULT_CHANGED", old=o.get("default"), new=n.get("default"))


def _visible_properties(
    doc: Document, view: SchemaView, direction: str
) -> tuple[dict[str, Any], set[str]]:
    """Properties that exist on the wire in this direction (readOnly/writeOnly aware)."""
    hidden_flag = "readOnly" if direction == REQUEST else "writeOnly"
    visible: dict[str, Any] = {}
    for name, prop in view.properties.items():
        try:
            resolved, _ = doc.deref(prop, view.property_pointers[name])
        except RefCycleError:
            resolved = prop
        if isinstance(resolved, dict) and resolved.get(hidden_flag) is True:
            continue
        visible[name] = prop
    required = {r for r in view.required if r in visible or r not in view.properties}
    return visible, required


def _compare_object(
    state: WalkState,
    old_view: SchemaView,
    new_view: SchemaView,
    field_name: str,
    depth: int,
    emit: Emit,
) -> None:
    old_props, old_req = _visible_properties(state.old_doc, old_view, state.direction)
    new_props, new_req = _visible_properties(state.new_doc, new_view, state.direction)
    if not (
        old_props or new_props or old_req or new_req or "additionalProperties" in new_view.node
    ):
        return

    def child(name: str) -> str:
        return f"{field_name}.{name}" if field_name else name

    def emit_prop(kind: str, name: str, *, baseline: bool, **kw: Any) -> None:
        ptrs = old_view.property_pointers if baseline else new_view.property_pointers
        location = ptrs.get(name, old_view.pointer if baseline else new_view.pointer)
        rule_id = state.rules.get(kind)
        if rule_id is not None:
            state.emit(
                rule_id,
                location=location,
                baseline_location=baseline,
                field=child(name),
                detail=PROPERTY_KIND_TEXT[kind],
                **kw,
            )

    if state.direction == REQUEST:
        strict = new_view.node.get("additionalProperties") is False
        for name in sorted(set(old_props) - set(new_props)):
            emit_prop(
                "PROPERTY_REMOVED_STRICT" if strict else "PROPERTY_REMOVED", name, baseline=True
            )
        for name in sorted(new_req - old_req):
            kind = "PROPERTY_BECAME_REQUIRED" if name in old_props else "PROPERTY_REQUIRED_ADDED"
            emit_prop(
                kind,
                name,
                baseline=False,
                old="optional" if name in old_props else None,
                new="required",
            )
        for name in sorted(set(new_props) - set(old_props) - new_req):
            emit_prop("PROPERTY_ADDED_OPTIONAL", name, baseline=False)
        if old_view.node.get("additionalProperties") is not False and strict:
            emit(
                "ADDITIONAL_PROPERTIES_RESTRICTED",
                old=old_view.node.get("additionalProperties", True),
                new=False,
                detail="additional properties are no longer allowed",
            )
    else:
        for name in sorted(set(old_props) - set(new_props)):
            emit_prop("PROPERTY_REMOVED", name, baseline=True)
        for name in sorted((old_req - new_req) & set(new_props)):
            emit_prop(
                "PROPERTY_BECAME_OPTIONAL", name, baseline=False, old="required", new="optional"
            )
        for name in sorted(set(new_props) - set(old_props)):
            emit_prop("PROPERTY_ADDED", name, baseline=False)

    for name in sorted(set(old_props) & set(new_props)):
        compare_schema(
            state,
            old_props[name],
            old_view.property_pointers[name],
            new_props[name],
            new_view.property_pointers[name],
            child(name),
            depth=depth + 1,
        )

    old_ap, new_ap = (
        old_view.node.get("additionalProperties"),
        new_view.node.get("additionalProperties"),
    )
    if isinstance(old_ap, dict) and isinstance(new_ap, dict):
        compare_schema(
            state,
            old_ap,
            pointer.join(old_view.pointer, "additionalProperties"),
            new_ap,
            pointer.join(new_view.pointer, "additionalProperties"),
            f"{field_name}.*",
            depth=depth + 1,
        )
