"""Operation-level comparison: paths, parameters, bodies, responses, security."""

from __future__ import annotations

import json
from typing import Any

from apisentinel import pointer
from apisentinel.document import Document, Operation, path_param_names
from apisentinel.findings import Collector
from apisentinel.schema_diff import (
    PARAMETER_RULES,
    REQUEST,
    REQUEST_BODY_RULES,
    RESPONSE,
    RESPONSE_RULES,
    WalkState,
    compare_schema,
)

Requirement = frozenset[tuple[str, frozenset[str]]]


class Comparator:
    def __init__(self, old: Document, new: Document, collector: Collector) -> None:
        self.old = old
        self.new = new
        self.out = collector
        self._old_schemes = old.security_schemes()
        self._new_schemes = new.security_schemes()

    # ------------------------------------------------------------------ entry
    def run(self) -> None:
        old_ops, new_ops = self.old.operations, self.new.operations
        new_paths = {key[1] for key in new_ops}

        for key in sorted(old_ops.keys() - new_ops.keys()):
            op = old_ops[key]
            if op.deprecated:
                rule = "OP-003"
            else:
                rule = "OP-001" if key[1] not in new_paths else "OP-002"
            self.out.add(
                rule, method=op.method, path=op.path, location=op.pointer, baseline_location=True
            )

        for key in sorted(new_ops.keys() - old_ops.keys()):
            op = new_ops[key]
            self.out.add("OP-006", method=op.method, path=op.path, location=op.pointer)

        for key in sorted(old_ops.keys() & new_ops.keys()):
            self._compare_operation(old_ops[key], new_ops[key])

        self._compare_servers()

    # ------------------------------------------------------------- operation
    def _compare_operation(self, old: Operation, new: Operation) -> None:
        method, path = new.method, new.path
        if not old.deprecated and new.deprecated:
            self.out.add(
                "OP-004", method=method, path=path, location=pointer.join(new.pointer, "deprecated")
            )
        old_names, new_names = path_param_names(old.path), path_param_names(new.path)
        for old_name, new_name in zip(old_names, new_names, strict=True):
            if old_name != new_name:
                self.out.add(
                    "OP-005",
                    method=method,
                    path=path,
                    location=new.path_item_pointer,
                    old=old_name,
                    new=new_name,
                )
        self._compare_parameters(old, new)
        self._compare_request_body(old, new)
        self._compare_responses(old, new)
        self._compare_security(old, new)

    def _walk(self, rules: dict[str, str], direction: str, op: Operation) -> WalkState:
        def emit(rule_id: str, **kwargs: Any) -> None:
            self.out.add(rule_id, method=op.method, path=op.path, **kwargs)

        return WalkState(self.old, self.new, direction, rules, emit)

    # ------------------------------------------------------------ parameters
    def _compare_parameters(self, old: Operation, new: Operation) -> None:
        add = self.out.add
        method, path = new.method, new.path
        for key in sorted(old.parameters.keys() - new.parameters.keys()):
            param = old.parameters[key]
            add(
                "REQ-PARAM-001",
                method=method,
                path=path,
                location=param.pointer,
                baseline_location=True,
                field=f"{param.location}.{param.name}",
                name=param.name,
                location_kind=param.location,
            )
        for key in sorted(new.parameters.keys() - old.parameters.keys()):
            param = new.parameters[key]
            rule = "REQ-PARAM-002" if param.required else "REQ-PARAM-010"
            add(
                rule,
                method=method,
                path=path,
                location=param.pointer,
                field=f"{param.location}.{param.name}",
                name=param.name,
                location_kind=param.location,
            )
        for key in sorted(old.parameters.keys() & new.parameters.keys()):
            o, n = old.parameters[key], new.parameters[key]
            label = f"{n.location}.{n.name}"
            if n.required and not o.required:
                add(
                    "REQ-PARAM-003",
                    method=method,
                    path=path,
                    location=n.pointer,
                    field=label,
                    name=n.name,
                    location_kind=n.location,
                    old="optional",
                    new="required",
                )
            if (o.style, o.explode) != (n.style, n.explode):
                add(
                    "REQ-PARAM-007",
                    method=method,
                    path=path,
                    location=n.pointer,
                    field=label,
                    old=f"style={o.style}, explode={str(o.explode).lower()}",
                    new=f"style={n.style}, explode={str(n.explode).lower()}",
                )
            compare_schema(
                self._walk(PARAMETER_RULES, REQUEST, new),
                o.schema,
                o.schema_pointer,
                n.schema,
                n.schema_pointer,
                label,
            )

    # ---------------------------------------------------------- request body
    def _request_body(self, doc: Document, op: Operation) -> tuple[dict[str, Any] | None, str]:
        if "requestBody" not in op.raw:
            return None, op.pointer
        body, where = doc.deref(op.raw["requestBody"], pointer.join(op.pointer, "requestBody"))
        return (body if isinstance(body, dict) else None), where

    def _compare_request_body(self, old: Operation, new: Operation) -> None:
        old_body, old_ptr = self._request_body(self.old, old)
        new_body, new_ptr = self._request_body(self.new, new)
        method, path = new.method, new.path
        if old_body is None and new_body is None:
            return
        if new_body is None:
            self.out.add(
                "REQ-BODY-015",
                method=method,
                path=path,
                location=old_ptr,
                baseline_location=True,
                field="body",
            )
            return
        if new_body.get("required") is True and (
            old_body is None or old_body.get("required") is not True
        ):
            self.out.add(
                "REQ-BODY-001",
                method=method,
                path=path,
                location=pointer.join(new_ptr, "required"),
                field="body",
                old="optional" if old_body else "absent",
                new="required",
            )
        if old_body is None:
            return
        old_content, new_content = _content(old_body), _content(new_body)
        for media in sorted(old_content):
            match = _match_media(media, new_content)
            if match is None:
                self.out.add(
                    "REQ-BODY-002",
                    method=method,
                    path=path,
                    location=pointer.join(old_ptr, "content", media),
                    baseline_location=True,
                    field="body",
                    media=media,
                )
                continue
            o_media, n_media = old_content[media], new_content[match]
            compare_schema(
                self._walk(REQUEST_BODY_RULES, REQUEST, new),
                o_media.get("schema"),
                pointer.join(old_ptr, "content", media, "schema"),
                n_media.get("schema"),
                pointer.join(new_ptr, "content", match, "schema"),
                "body",
                is_root=True,
            )

    # -------------------------------------------------------------- responses
    def _responses(self, doc: Document, op: Operation) -> dict[str, tuple[dict[str, Any], str]]:
        raw = op.raw.get("responses")
        result: dict[str, tuple[dict[str, Any], str]] = {}
        if not isinstance(raw, dict):
            return result
        for status, entry in raw.items():
            resolved, where = doc.deref(entry, pointer.join(op.pointer, "responses", status))
            if isinstance(resolved, dict):
                result[str(status).upper()] = (resolved, where)
        return result

    def _compare_responses(self, old: Operation, new: Operation) -> None:
        old_res, new_res = self._responses(self.old, old), self._responses(self.new, new)
        method, path = new.method, new.path
        new_success = {s for s in new_res if _is_success(s)}
        for status in sorted(old_res):
            target = status if status in new_res else _covering_range(status, new_res)
            if target is None:
                rule = "RES-001" if _is_success(status) else "RES-002"
                self.out.add(
                    rule,
                    method=method,
                    path=path,
                    location=old_res[status][1],
                    baseline_location=True,
                    field=f"response[{status}]",
                    status=status,
                )
                continue
            self._compare_response(method, path, new, status, old_res[status], new_res[target])
        for status in sorted(new_success - set(old_res)):
            if _covering_range(status, old_res) is None:
                self.out.add(
                    "RES-003",
                    method=method,
                    path=path,
                    location=new_res[status][1],
                    field=f"response[{status}]",
                    status=status,
                )

    def _compare_response(
        self,
        method: str,
        path: str,
        new_op: Operation,
        status: str,
        old: tuple[dict[str, Any], str],
        new: tuple[dict[str, Any], str],
    ) -> None:
        (old_res, old_ptr), (new_res, new_ptr) = old, new
        old_content, new_content = _content(old_res), _content(new_res)
        label = f"response[{status}]"
        for media in sorted(old_content):
            match = _match_media(media, new_content)
            if match is None:
                self.out.add(
                    "RES-004",
                    method=method,
                    path=path,
                    location=pointer.join(old_ptr, "content", media),
                    baseline_location=True,
                    field=label,
                    status=status,
                    media=media,
                )
                continue
            o_schema = old_content[media].get("schema")
            n_schema = new_content[match].get("schema")
            n_schema_ptr = pointer.join(new_ptr, "content", match, "schema")
            if o_schema is not None and n_schema is None:
                self.out.add(
                    "RES-011",
                    method=method,
                    path=path,
                    location=pointer.join(new_ptr, "content", match),
                    field=label,
                    old="schema",
                    new="no schema",
                )
                continue
            compare_schema(
                self._walk(RESPONSE_RULES, RESPONSE, new_op),
                o_schema,
                pointer.join(old_ptr, "content", media, "schema"),
                n_schema,
                n_schema_ptr,
                label,
                is_root=True,
            )

    # --------------------------------------------------------------- security
    def _requirements(self, raw: Any) -> list[Requirement]:
        """Normalize a security list. Public (no requirement) == [empty set]."""
        if not isinstance(raw, list) or not raw:
            return [frozenset()]
        alternatives: list[Requirement] = []
        for alt in raw:
            if not isinstance(alt, dict):
                continue
            alternatives.append(
                frozenset(
                    (name, frozenset(s for s in scopes if isinstance(s, str)))
                    for name, scopes in alt.items()
                    if isinstance(scopes, list)
                )
            )
        return alternatives or [frozenset()]

    @staticmethod
    def _signature(scheme: Any) -> str:
        if not isinstance(scheme, dict):
            return "undefined"
        location = scheme.get("in")
        name = scheme.get("name")
        if location == "header" and isinstance(name, str):
            name = name.lower()
        raw_flows = scheme.get("flows")
        flows: dict[str, Any] = raw_flows if isinstance(raw_flows, dict) else {}
        return json.dumps(
            {
                "type": scheme.get("type"),
                "scheme": str(scheme.get("scheme", "")).lower(),
                "in": location,
                "name": name,
                "openIdConnectUrl": scheme.get("openIdConnectUrl"),
                "flows": {
                    flow: {k: v.get(k) for k in ("tokenUrl", "authorizationUrl")}
                    for flow, v in sorted(flows.items())
                    if isinstance(v, dict)
                },
            },
            sort_keys=True,
        )

    def _satisfies(self, offered: Requirement, demanded: Requirement, *, check_sig: bool) -> bool:
        """True if credentials matching old alternative ``offered`` satisfy new ``demanded``."""
        have = dict(offered)
        for name, scopes in demanded:
            if name not in have or not scopes <= have[name]:
                return False
            if check_sig and self._signature(self._old_schemes.get(name)) != self._signature(
                self._new_schemes.get(name)
            ):
                return False
        return True

    @staticmethod
    def _describe(alternatives: list[Requirement]) -> str:
        parts = []
        for alt in alternatives:
            if not alt:
                parts.append("anonymous")
                continue
            parts.append(
                " + ".join(
                    f"{name}[{', '.join(sorted(scopes))}]" if scopes else name
                    for name, scopes in sorted(alt)
                )
            )
        return " OR ".join(parts)

    def _compare_security(self, old: Operation, new: Operation) -> None:
        old_raw, _ = self.old.effective_security(old)
        new_raw, new_ptr = self.new.effective_security(new)
        old_alts, new_alts = self._requirements(old_raw), self._requirements(new_raw)
        method, path = new.method, new.path
        old_desc, new_desc = self._describe(old_alts), self._describe(new_alts)

        # Compatibility: can a client using any old alternative still get in?
        for alt in old_alts:
            if any(self._satisfies(alt, cand, check_sig=True) for cand in new_alts):
                continue
            if not alt:
                rule = "AUTH-001"
                extra: dict[str, Any] = {}
            else:
                same_schemes = [
                    c for c in new_alts
                    if {n for n, _ in c} == {n for n, _ in alt}
                    and self._satisfies(alt, frozenset((n, frozenset()) for n, _ in c),
                                        check_sig=True)
                ]  # fmt: skip
                if same_schemes:
                    rule = "AUTH-003"
                    have = dict(alt)
                    added = sorted(
                        f"{n}:{s}" for n, scopes in same_schemes[0] for s in scopes - have[n]
                    )
                    extra = {"detail": ", ".join(added)}
                else:
                    rule = "AUTH-002"
                    extra = {}
            self.out.add(
                rule,
                method=method,
                path=path,
                location=new_ptr,
                field="security",
                old=old_desc,
                new=new_desc,
                **extra,
            )

        # Security regression: does the new spec accept something the old one rejected?
        old_public = any(not alt for alt in old_alts)
        new_public_only = all(not alt for alt in new_alts)
        if not old_public and new_public_only:
            self.out.add(
                "SEC-R001",
                method=method,
                path=path,
                location=new_ptr,
                field="security",
                old=old_desc,
                new=new_desc,
            )
            return
        for cand in new_alts:
            if any(self._satisfies(cand, alt, check_sig=False) for alt in old_alts):
                continue  # at least as strict as some old alternative
            reduced = [
                alt for alt in old_alts
                if alt and {n for n, _ in alt} == {n for n, _ in cand}
            ]  # fmt: skip
            if cand and reduced:
                cand_scopes = dict(cand)
                dropped = sorted(
                    f"{n}:{s}" for n, scopes in reduced[0] for s in scopes - cand_scopes[n]
                )
                self.out.add(
                    "SEC-R003",
                    method=method,
                    path=path,
                    location=new_ptr,
                    field="security",
                    old=old_desc,
                    new=new_desc,
                    detail=", ".join(dropped),
                )
            else:
                self.out.add(
                    "SEC-R002",
                    method=method,
                    path=path,
                    location=new_ptr,
                    field="security",
                    old=old_desc,
                    new=self._describe([cand]),
                )

    # ---------------------------------------------------------------- servers
    def _compare_servers(self) -> None:
        def urls(doc: Document) -> list[str]:
            servers = doc.raw.get("servers")
            if not isinstance(servers, list):
                return []
            return [
                s["url"] for s in servers if isinstance(s, dict) and isinstance(s.get("url"), str)
            ]

        new_urls = urls(self.new)
        for url in urls(self.old):
            if not url.lower().startswith("https://"):
                continue
            downgraded = "http://" + url[len("https://") :]
            for index, candidate in enumerate(new_urls):
                if candidate.lower() == downgraded.lower():
                    self.out.add(
                        "SEC-R004",
                        method=None,
                        path=None,
                        location=pointer.join("/servers", index, "url"),
                        field="servers",
                        old=url,
                        new=candidate,
                    )


# ------------------------------------------------------------------ helpers
def _content(container: dict[str, Any]) -> dict[str, dict[str, Any]]:
    content = container.get("content")
    if not isinstance(content, dict):
        return {}
    return {str(media): value for media, value in content.items() if isinstance(value, dict)}


def _media_key(media: str) -> str:
    return media.split(";", 1)[0].strip().lower()


def _match_media(media: str, candidates: dict[str, Any]) -> str | None:
    """Find the candidate media type that still covers ``media`` (exact, then wildcards)."""
    wanted = _media_key(media)
    by_key = {_media_key(c): c for c in candidates}
    if wanted in by_key:
        return by_key[wanted]
    major = wanted.split("/", 1)[0]
    for pattern in (f"{major}/*", "*/*"):
        if pattern in by_key:
            return by_key[pattern]
    return None


def _is_success(status: str) -> bool:
    return status.startswith("2")


def _covering_range(status: str, responses: dict[str, Any]) -> str | None:
    """'201' is still documented if the other side has '2XX'."""
    if len(status) == 3 and status[0].isdigit() and status[1:].isdigit():
        candidate = f"{status[0]}XX"
        if candidate in responses:
            return candidate
    return None
