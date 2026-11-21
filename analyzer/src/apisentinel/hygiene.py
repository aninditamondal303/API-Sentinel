"""Single-specification security hygiene checks.

These read what a specification *declares* about transport and authentication.
They are not a penetration test: they cannot tell whether the running server
enforces any of it, and they find no runtime vulnerabilities. Every result
carries that disclaimer.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any
from urllib.parse import urlsplit

from apisentinel import RULESET_VERSION, __version__, pointer
from apisentinel.document import Document, Operation
from apisentinel.engine import RESULT_SCHEMA_VERSION, FailurePolicy, LoadedSpec
from apisentinel.findings import Collector, Finding
from apisentinel.rules import Severity

DISCLAIMER = (
    "Static specification checks only. API Sentinel reads what the specification declares; "
    "it is not a penetration test and does not detect runtime vulnerabilities."
)
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
_CREDENTIAL_NAME = re.compile(
    r"^(password|passwd|pwd|secret|client[_-]?secret|token|access[_-]?token|refresh[_-]?token|"
    r"api[_-]?key|apikey|access[_-]?key|private[_-]?key|session[_-]?id)$",
    re.IGNORECASE,
)
_VARIABLE = re.compile(r"\{([^}]+)\}")


def _resolve_server_url(server: dict[str, Any]) -> str | None:
    url = server.get("url")
    if not isinstance(url, str):
        return None
    variables = server.get("variables") if isinstance(server.get("variables"), dict) else {}
    assert isinstance(variables, dict)

    def substitute(match: re.Match[str]) -> str:
        variable = variables.get(match.group(1))
        if isinstance(variable, dict) and isinstance(variable.get("default"), str):
            return str(variable["default"])
        return match.group(0)

    return _VARIABLE.sub(substitute, url)


def _is_local(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host in LOCAL_HOSTS or host.endswith(".localhost")


class HygieneScanner:
    def __init__(self, doc: Document, collector: Collector) -> None:
        self.doc = doc
        self.out = collector
        self.schemes = doc.security_schemes()

    def _add(self, rule_id: str, **kwargs: Any) -> None:
        kwargs.setdefault("method", None)
        kwargs.setdefault("path", None)
        self.out.add(rule_id, document="spec", **kwargs)

    # -------------------------------------------------------------- servers
    def _server_entries(self) -> list[tuple[str, str]]:
        """All server URLs (root, path and operation level) with their pointers."""
        found: list[tuple[str, str]] = []

        def collect(container: Any, where: str) -> None:
            servers = container.get("servers") if isinstance(container, dict) else None
            if not isinstance(servers, list):
                return
            for index, server in enumerate(servers):
                if isinstance(server, dict):
                    url = _resolve_server_url(server)
                    if url:
                        found.append((url, pointer.join(where, "servers", index, "url")))

        collect(self.doc.raw, "")
        seen_items: set[str] = set()
        for op in self.doc.operations.values():
            if op.path_item_pointer not in seen_items:
                seen_items.add(op.path_item_pointer)
                collect(op.path_item, op.path_item_pointer)
            collect(op.raw, op.pointer)
        return found

    def check_servers(self) -> list[str]:
        """Emit SEC-H001/H010 and return insecure non-local URLs."""
        insecure: list[str] = []
        for url, where in self._server_entries():
            if not url.lower().startswith("http://"):
                continue
            if _is_local(url):
                self._add("SEC-H010", location=where, field="servers", url=url)
            else:
                self._add("SEC-H001", location=where, field="servers", url=url)
                insecure.append(url)
        return insecure

    # -------------------------------------------------------------- schemes
    def check_schemes(self, insecure_urls: list[str], used: set[str]) -> None:
        base = "/components/securitySchemes"
        for name in sorted(self.schemes):
            scheme = self.schemes[name]
            where = pointer.join(base, name)
            if not isinstance(scheme, dict):
                continue
            kind = scheme.get("type")
            if name not in used:
                self._add("SEC-H005", location=where, field=f"securitySchemes.{name}", scheme=name)
            if kind == "apiKey" and scheme.get("in") == "query":
                self._add("SEC-H007", location=where, field=f"securitySchemes.{name}",
                          scheme=name, name=scheme.get("name"))  # fmt: skip
            if (
                kind == "http"
                and str(scheme.get("scheme", "")).lower() == "basic"
                and name in used
                and insecure_urls
            ):
                self._add("SEC-H008", location=where, field=f"securitySchemes.{name}",
                          scheme=name, url=insecure_urls[0])  # fmt: skip
            urls: list[tuple[str, str]] = []
            if kind == "openIdConnect" and isinstance(scheme.get("openIdConnectUrl"), str):
                urls.append((scheme["openIdConnectUrl"], pointer.join(where, "openIdConnectUrl")))
            flows = scheme.get("flows") if kind == "oauth2" else None
            if isinstance(flows, dict):
                for flow_name in sorted(flows):
                    flow = flows[flow_name]
                    if not isinstance(flow, dict):
                        continue
                    flow_ptr = pointer.join(where, "flows", flow_name)
                    if flow_name in {"implicit", "password"}:
                        self._add("SEC-H011", location=flow_ptr, field=f"securitySchemes.{name}",
                                  scheme=name, flow=flow_name)  # fmt: skip
                    for key in ("authorizationUrl", "tokenUrl", "refreshUrl"):
                        if isinstance(flow.get(key), str):
                            urls.append((flow[key], pointer.join(flow_ptr, key)))
            for url, url_ptr in urls:
                if url.lower().startswith("http://") and not _is_local(url):
                    self._add("SEC-H012", location=url_ptr, field=f"securitySchemes.{name}",
                              scheme=name, url=url)  # fmt: skip

    def _defined_scopes(self, scheme: Any) -> set[str] | None:
        """Scopes an OAuth2 scheme defines; None when scopes are free-form (other types)."""
        if not isinstance(scheme, dict) or scheme.get("type") != "oauth2":
            return None
        scopes: set[str] = set()
        flows = scheme.get("flows")
        if isinstance(flows, dict):
            for flow in flows.values():
                if isinstance(flow, dict) and isinstance(flow.get("scopes"), dict):
                    scopes |= set(flow["scopes"])
        return scopes

    # ----------------------------------------------------------- operations
    def check_requirement_list(self, raw: Any, where: str, op: Operation | None) -> set[str]:
        """Validate one security list; return the scheme names it references."""
        names: set[str] = set()
        if not isinstance(raw, list):
            return names
        method = op.method if op else None
        path = op.path if op else None
        for index, alternative in enumerate(raw):
            if not isinstance(alternative, dict):
                continue
            for name in sorted(alternative):
                scopes = alternative[name]
                names.add(name)
                entry_ptr = pointer.join(where, index, name)
                if name not in self.schemes:
                    self._add("SEC-H004", method=method, path=path, location=entry_ptr,
                              field="security", scheme=name)  # fmt: skip
                    continue
                defined = self._defined_scopes(self.schemes[name])
                if defined is None or not isinstance(scopes, list):
                    continue
                for scope in scopes:
                    if isinstance(scope, str) and scope not in defined:
                        self._add("SEC-H006", method=method, path=path, location=entry_ptr,
                                  field="security", scheme=name, scope=scope)  # fmt: skip
        return names

    def check_operations(self) -> set[str]:
        used = self.check_requirement_list(self.doc.raw.get("security"), "/security", None)
        root_declared = isinstance(self.doc.raw.get("security"), list) and bool(
            self.doc.raw["security"]
        )
        effective: dict[tuple[str, str], list[Any] | None] = {}
        for key, op in sorted(self.doc.operations.items()):
            if "security" in op.raw:
                used |= self.check_requirement_list(
                    op.raw["security"], pointer.join(op.pointer, "security"), op
                )
            raw, where = self.doc.effective_security(op)
            effective[key] = raw if isinstance(raw, list) else None
            if "security" in op.raw and raw == []:
                self._add("SEC-H003", method=op.method, path=op.path, location=where,
                          field="security")  # fmt: skip
            elif not root_declared and "security" not in op.raw:
                self._add("SEC-H002", method=op.method, path=op.path, location=op.pointer,
                          field="security")  # fmt: skip
            if (
                op.method in MUTATING
                and isinstance(raw, list)
                and any(isinstance(a, dict) and not a for a in raw)
                and any(isinstance(a, dict) and a for a in raw)
            ):
                self._add("SEC-H014", method=op.method, path=op.path, location=where,
                          field="security")  # fmt: skip
            for param in op.parameters.values():
                if param.location == "query" and _CREDENTIAL_NAME.match(param.name):
                    self._add("SEC-H013", method=op.method, path=op.path, location=param.pointer,
                              field=f"query.{param.name}", name=param.name)  # fmt: skip

        def is_public(requirement: list[Any] | None) -> bool:
            return not requirement or any(isinstance(a, dict) and not a for a in requirement)

        for (method, norm_path), op in sorted(self.doc.operations.items()):
            if method not in MUTATING or not is_public(effective[(method, norm_path)]):
                continue
            read = effective.get(("GET", norm_path))
            if ("GET", norm_path) in effective and not is_public(read):
                self._add("SEC-H009", method=op.method, path=op.path, location=op.pointer,
                          field="security")  # fmt: skip
        return used

    def run(self) -> None:
        insecure = self.check_servers()
        used = self.check_operations()
        self.check_schemes(insecure, used)


def scan(loaded: LoadedSpec, fail_on: Severity | None = Severity.HIGH) -> dict[str, Any]:
    """Run the hygiene checks on one validated specification."""
    collector = Collector()
    HygieneScanner(loaded.document, collector).run()
    findings: list[Finding] = collector.findings()
    policy = FailurePolicy(fail_on=fail_on, fail_on_manual_review=False)
    failing = [f for f in findings if fail_on is not None and f.severity >= fail_on]
    by_severity = Counter(f.severity.name for f in findings)
    return {
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "analyzer": {"version": __version__, "rulesetVersion": RULESET_VERSION},
        "spec": loaded.to_dict(),
        "decision": {
            "result": "FAIL" if failing else "PASS",
            "reasons": [f"{len(failing)} finding(s) at or above {fail_on.name}"]
            if failing and fail_on is not None
            else [],
            "failOn": policy.to_dict()["failOn"],
        },
        "summary": {
            "total": len(findings),
            "bySeverity": {s.name: by_severity.get(s.name, 0) for s in reversed(Severity)},
            "endpointsAffected": len({(f.method, f.path) for f in findings if f.path}),
        },
        "findings": [f.to_dict() for f in findings],
        "disclaimer": DISCLAIMER,
    }
