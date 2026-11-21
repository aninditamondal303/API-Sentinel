"""FastAPI application factory.

Run:  uvicorn apisentinel.api.app:create_app --factory --port 8081
"""

from __future__ import annotations

from fastapi import FastAPI

from apisentinel import __version__
from apisentinel.api.observability import RequestContextMiddleware, configure_logging
from apisentinel.api.problems import install_handlers
from apisentinel.api.routes import health, internal
from apisentinel.api.settings import Settings, load_settings

DESCRIPTION = (
    "Internal API of the API Sentinel analyzer. Called by the API Sentinel backend; "
    "not meant to be exposed publicly. All /internal/v1 endpoints require the "
    "X-Internal-Token header. Errors use RFC 9457 problem details."
)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="API Sentinel Analyzer",
        version=__version__,
        description=DESCRIPTION,
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.enable_docs else None,
    )
    app.state.settings = settings
    install_handlers(app)
    app.include_router(health)
    app.include_router(internal)
    app.add_middleware(RequestContextMiddleware, max_body_bytes=settings.max_request_bytes)
    return app
