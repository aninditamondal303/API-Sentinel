"""Request IDs, structured JSON logs and request-size limiting (pure ASGI).

Logs contain request metadata only: never request bodies, spec content or
credentials. Specs are identified by their SHA-256 in results instead.
"""

from __future__ import annotations

import contextvars
import json
import logging
import re
import time
import uuid
from http import HTTPStatus
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "x-request-id"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
logger = logging.getLogger("apisentinel.api")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "requestId": request_id_var.get(),
        }
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            entry.update(extra)
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(level: str) -> None:
    root = logging.getLogger("apisentinel")
    root.setLevel(level)
    if not any(getattr(h, "_apisentinel", False) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        handler._apisentinel = True  # type: ignore[attr-defined]
        root.addHandler(handler)


class _BodyTooLargeError(Exception):
    pass


class RequestContextMiddleware:
    """Assigns a request ID, enforces the body-size limit and writes an access log line."""

    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        incoming = headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming if _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_holder = {"status": 500, "started": False}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                status_holder["started"] = True
                message.setdefault("headers", [])
                message["headers"].append((b"x-request-id", request_id.encode()))
            await send(message)

        received = 0

        async def receive_wrapper() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body_bytes:
                    raise _BodyTooLargeError
            return message

        try:
            declared = headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > self.max_body_bytes:
                await self._too_large(scope, send_wrapper, request_id)
            else:
                try:
                    await self.app(scope, receive_wrapper, send_wrapper)
                except _BodyTooLargeError:
                    if status_holder["started"]:
                        raise
                    await self._too_large(scope, send_wrapper, request_id)
                except Exception:
                    # Error boundary: log with the request ID, answer with a generic problem.
                    logger.exception(
                        "unhandled error", extra={"fields": {"path": scope.get("path")}}
                    )
                    if status_holder["started"]:
                        raise
                    await self._problem(scope, send_wrapper, request_id, 500, "INTERNAL_ERROR",
                                        "Unexpected analyzer error. Quote the requestId when "
                                        "reporting it.")  # fmt: skip
        finally:
            logger.info(
                "request",
                extra={
                    "fields": {
                        "method": scope.get("method"),
                        "path": scope.get("path"),
                        "status": status_holder["status"],
                        "durationMs": round((time.perf_counter() - started) * 1000, 1),
                    }
                },
            )
            request_id_var.reset(token)

    async def _too_large(self, scope: Scope, send: Send, request_id: str) -> None:
        detail = f"Request body exceeds {self.max_body_bytes} bytes."
        await self._problem(scope, send, request_id, 413, "PAYLOAD_TOO_LARGE", detail)

    @staticmethod
    async def _problem(
        scope: Scope, send: Send, request_id: str, status: int, code: str, detail: str
    ) -> None:
        body = json.dumps(
            {
                "type": "about:blank",
                "title": HTTPStatus(status).phrase,
                "status": status,
                "detail": detail,
                "instance": scope.get("path"),
                "errorCode": code,
                "requestId": request_id,
            }
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/problem+json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
