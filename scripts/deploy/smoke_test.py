#!/usr/bin/env python3
"""End-to-end smoke test of a deployed API Sentinel over its public HTTPS URL.

    python3 scripts/deploy/smoke_test.py https://your.domain            # full flow, new account
    python3 scripts/deploy/smoke_test.py https://your.domain --persist  # re-check that account

The full flow registers a fresh throw-away account, logs in, creates a project, uploads the
Orders API example specs, runs a compatibility scan and a security scan, reads findings, the
report and the dashboard, and downloads the contract-test ZIP: the same journey a visitor makes
in the UI, through the same public origin (Caddy -> nginx -> backend -> analyzer/PostgreSQL).

It saves the test account and the ids it created to ~/.apisentinel-smoke.json (mode 600) so that
--persist can log in again after a restart or redeploy and confirm the data survived.
Passwords and tokens are never printed. Standard library only.
"""
from __future__ import annotations

import io
import json
import os
import secrets
import ssl
import sys
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples" / "orders-api"
STATE = Path.home() / ".apisentinel-smoke.json"
CTX = ssl.create_default_context()  # certificate must be valid: no verification bypass

passed = 0
failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}  {detail}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.token: str | None = None

    def call(self, method: str, path: str, body=None, form=None, raw: bool = False):
        headers = {"Accept": "application/json"}
        data = None
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        elif form is not None:
            boundary = uuid.uuid4().hex
            buf = io.BytesIO()
            for key, value in form.items():
                buf.write(f"--{boundary}\r\n".encode())
                if isinstance(value, Path):
                    buf.write(
                        f'Content-Disposition: form-data; name="{key}"; filename="{value.name}"\r\n'
                        "Content-Type: application/yaml\r\n\r\n".encode()
                    )
                    buf.write(value.read_bytes())
                else:
                    buf.write(f'Content-Disposition: form-data; name="{key}"\r\n\r\n{value}'.encode())
                buf.write(b"\r\n")
            buf.write(f"--{boundary}--\r\n".encode())
            data = buf.getvalue()
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, context=CTX, timeout=90) as resp:
                status, payload = resp.status, resp.read()
        except urllib.error.HTTPError as err:
            status, payload = err.code, err.read()
        if raw:
            return status, payload
        try:
            return status, json.loads(payload) if payload else None
        except ValueError:
            return status, None


def full(base: str) -> None:
    api = Api(base)
    email = f"smoke.{secrets.token_hex(4)}@example.com"
    password = "Smoke-" + secrets.token_hex(8) + "9"

    print("== Registration and login")
    s, j = api.call("POST", "/api/v1/auth/register", {"email": email, "password": password, "displayName": "Smoke Test"})
    check("Register", s == 201 and j and j.get("user", {}).get("email") == email, str(s))
    s, j = api.call("POST", "/api/v1/auth/login", {"email": email, "password": password})
    api.token = (j or {}).get("accessToken")
    check("Login", s == 200 and bool(api.token), str(s))
    s, j = api.call("GET", "/api/v1/auth/me")
    check("Current user", s == 200 and j and j.get("email") == email, str(s))

    print("== Project and specifications")
    s, j = api.call("POST", "/api/v1/projects", {"name": f"Orders API smoke {secrets.token_hex(2)}", "description": "Deployment smoke test"})
    project = (j or {}).get("id")
    check("Create project", s == 201 and bool(project), str(s))
    s, j = api.call("POST", f"/api/v1/projects/{project}/specifications",
                    form={"file": EXAMPLES / "baseline.yaml", "versionLabel": "v1.0.0"})
    baseline = (j or {}).get("id")
    check("Upload baseline spec", s == 201 and bool(baseline), f"{s} operations={(j or {}).get('operationCount')}")
    s, j = api.call("POST", f"/api/v1/projects/{project}/specifications",
                    form={"file": EXAMPLES / "candidate-breaking.yaml", "versionLabel": "v2.0.0"})
    candidate = (j or {}).get("id")
    check("Upload candidate spec", s == 201 and bool(candidate), str(s))

    print("== Scans")
    s, compat = api.call("POST", f"/api/v1/projects/{project}/scans/compatibility",
                         {"baselineSpecificationId": baseline, "candidateSpecificationId": candidate})
    compat = compat or {}
    check("Compatibility scan", s == 201 and compat.get("status") == "COMPLETED",
          f"{s} decision={compat.get('decision')} findings={compat.get('totalFindings')} breaking={compat.get('breakingChanges')}")
    s, j = api.call("GET", f"/api/v1/projects/{project}/scans/{compat.get('id')}/findings?size=200")
    check("Findings", s == 200 and j and j.get("totalItems") == compat.get("totalFindings"), f"{s} totalItems={(j or {}).get('totalItems')}")
    s, j = api.call("POST", f"/api/v1/projects/{project}/scans/security", {"specificationId": baseline})
    check("Security scan", s == 201 and j and j.get("status") == "COMPLETED", f"{s} decision={(j or {}).get('decision')} findings={(j or {}).get('totalFindings')}")
    s, j = api.call("GET", f"/api/v1/projects/{project}/scans/{compat.get('id')}/report")
    check("Scan report", s == 200 and j and len(j.get("findings", [])) == compat.get("totalFindings"), str(s))

    print("== Contract tests and dashboard")
    s, payload = api.call("GET", f"/api/v1/projects/{project}/specifications/{baseline}/contract-tests/download?baseUrl=http://localhost:9000", raw=True)
    entries = 0
    try:
        entries = len(zipfile.ZipFile(io.BytesIO(payload)).namelist())
    except zipfile.BadZipFile:
        pass
    check("Contract-test ZIP download", s == 200 and entries > 0, f"{s} entries={entries}")
    s, d = api.call("GET", "/api/v1/dashboard")
    d = d or {}
    check("Dashboard", s == 200 and d.get("projects") == 1 and d.get("specifications") == 2 and d.get("scans", {}).get("total") == 2,
          f"{s} projects={d.get('projects')} specs={d.get('specifications')} scans={d.get('scans', {}).get('total')}")

    print("== Isolation")
    other = Api(base)
    oemail = f"smoke.other.{secrets.token_hex(4)}@example.com"
    other.call("POST", "/api/v1/auth/register", {"email": oemail, "password": password, "displayName": "Other"})
    _, oj = other.call("POST", "/api/v1/auth/login", {"email": oemail, "password": password})
    other.token = (oj or {}).get("accessToken")
    s, _ = other.call("GET", f"/api/v1/projects/{project}")
    check("Other user cannot read the project", s == 404, str(s))

    old = os.umask(0o077)
    try:
        STATE.write_text(json.dumps({"base": base, "email": email, "password": password, "project": project,
                                     "scan": compat.get("id"), "findings": compat.get("totalFindings")}))
    finally:
        os.umask(old)
    STATE.chmod(0o600)
    print(f"  (test account saved to {STATE} for --persist)")


def persist(base: str) -> None:
    state = json.loads(STATE.read_text())
    api = Api(base)
    print("== Persistence after restart/redeploy")
    s, j = api.call("POST", "/api/v1/auth/login", {"email": state["email"], "password": state["password"]})
    api.token = (j or {}).get("accessToken")
    check("Earlier account can still log in", s == 200 and bool(api.token), str(s))
    s, j = api.call("GET", f"/api/v1/projects/{state['project']}")
    check("Earlier project still exists", s == 200, str(s))
    s, j = api.call("GET", f"/api/v1/projects/{state['project']}/scans/{state['scan']}/findings?size=200")
    check("Earlier findings still stored", s == 200 and j and j.get("totalItems") == state["findings"], f"{s} totalItems={(j or {}).get('totalItems')}")


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].startswith("https://"):
        print(__doc__)
        return 2
    base = sys.argv[1]
    if "--persist" in sys.argv[2:]:
        persist(base)
    else:
        full(base)
    print(f"\nResult: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
