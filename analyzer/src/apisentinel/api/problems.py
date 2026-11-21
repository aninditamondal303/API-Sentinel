"""Mapping of every error to an RFC 9457 problem-details response.

Rules: never echo request input (it can be a whole spec), never expose stack
traces or configuration, always include the request ID for log correlation.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from apisentinel import pointer
from apisentinel.api.observability import request_id_var
from apisentinel.engine import InputError
from apisentinel.errors import ApiSentinelError

PROBLEM_JSON = "application/problem+json"

# Engine error codes -> HTTP status. Unknown engine codes are input problems (422).
ENGINE_STATUS = {
    "SPEC_TOO_LARGE": 413,
    "SPEC_PARSE_ERROR": 422,
    "SPEC_INVALID": 422,
    "UNSUPPORTED_OPENAPI_VERSION": 422,
}
HTTP_CODES = {
    401: "UNAUTHENTICATED",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
}


class ProblemError(Exception):
    def __init__(self, status: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail


def problem(
    request: Request,
    status: int,
    code: str,
    detail: str,
    *,
    errors: list[dict[str, Any]] | None = None,
    side: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": HTTPStatus(status).phrase,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "errorCode": code,
        "requestId": request_id_var.get(),
    }
    if side:
        body["side"] = side
    if errors is not None:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=headers)


def _loc_to_pointer(loc: tuple[Any, ...]) -> str:
    parts = [p for p in loc if p != "body"]
    return pointer.join("", *parts)


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"pointer": _loc_to_pointer(tuple(err.get("loc", ()))), "message": err.get("msg", "")}
            for err in exc.errors()
        ]  # 'input' is deliberately dropped: it may contain an entire specification
        return problem(request, 400, "VALIDATION_FAILED", "The request is not valid.",
                       errors=errors)  # fmt: skip

    @app.exception_handler(ApiSentinelError)
    async def _engine(request: Request, exc: ApiSentinelError) -> JSONResponse:
        status = ENGINE_STATUS.get(exc.code, 422)
        side = exc.side if isinstance(exc, InputError) else None
        return problem(request, status, exc.code, exc.message,
                       errors=[i.to_dict() for i in exc.issues], side=side)  # fmt: skip

    @app.exception_handler(ProblemError)
    async def _api_problem(request: Request, exc: ProblemError) -> JSONResponse:
        headers = {"WWW-Authenticate": "X-Internal-Token"} if exc.status == 401 else None
        return problem(request, exc.status, exc.code, exc.detail, headers=headers)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
        detail = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
        return problem(request, exc.status_code, code, detail)

    # Unexpected exceptions are handled by RequestContextMiddleware (the error boundary),
    # which still knows the request ID; Starlette's own handler runs outside it.
