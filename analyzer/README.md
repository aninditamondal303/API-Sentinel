# API Sentinel analyzer

Deterministic breaking-change analysis, security hygiene checks and contract-test
generation for OpenAPI 3.0 and 3.1. One Python package with three entry points:
the engine (`apisentinel.engine`), the CLI (`apisentinel`) and the internal HTTP
service (`apisentinel.api`) that the backend calls.

## Setup (Windows 11, PowerShell)

```powershell
pip install uv                       # once
cd API-Sentinel\analyzer
uv sync --python 3.14                # creates .venv from uv.lock
uv run python -m pytest              # full test suite
uv run python -m ruff check src tests; uv run python -m mypy
```

## CLI

```powershell
uv run python -m apisentinel diff ..\examples\orders-api\baseline.yaml ..\examples\orders-api\candidate-breaking.yaml
uv run python -m apisentinel diff BASE CANDIDATE --format json --fail-on critical
uv run python -m apisentinel scan ..\analyzer\tests\fixtures\real\swagger-petstore-latest.yaml
uv run python -m apisentinel generate-tests ..\examples\inventory-api\openapi.yaml -o .\contract-tests
uv run python -m apisentinel validate SPEC
uv run python -m apisentinel rules
```

Exit codes: `0` pass, `1` failed the threshold, `2` invalid input, `3` internal error.

Run a generated suite (needs only `pytest` and `jsonschema`):

```powershell
$env:APISENTINEL_AUTH_TOKEN = "<token, only if operations need auth>"
uv run python -m pytest .\contract-tests --base-url http://localhost:8080
```

## HTTP service

```powershell
$env:APISENTINEL_INTERNAL_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(32))"
uv run python -m uvicorn apisentinel.api.app:create_app --factory --host 127.0.0.1 --port 8081
```

Endpoints: `GET /health/live`, `GET /health/ready`, and under `/internal/v1`
(header `X-Internal-Token` required): `POST /specs/validate`, `POST /analyses`,
`POST /security-scans`, `POST /contract-tests`, `GET /rules`. The full contract is
`contracts/analyzer-api.openapi.json`; regenerate it after API changes with
`uv run python -m apisentinel.api.contract > ..\contracts\analyzer-api.openapi.json`.

Security checks are specification-level only: they read what the spec declares and
are not a penetration test.

On Windows with Smart App Control enabled, always use `uv run python -m <tool>` (as above):
the unsigned launchers uv generates in `.venv\Scripts` (pytest.exe, uvicorn.exe, apisentinel.exe)
are blocked, while `python.exe` is allowed. Smart App Control can also block the unsigned native
extensions of some dependencies (for example pydantic-core and PyYAML). If imports fail with an
Application Control error, run the lint, type checks and tests in Docker instead:
`powershell -ExecutionPolicy Bypass -File ..\scripts\test-analyzer.ps1` (from this folder).
