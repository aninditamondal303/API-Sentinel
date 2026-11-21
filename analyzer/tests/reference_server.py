"""A small real HTTP server implementing examples/inventory-api/openapi.yaml.

Used to prove that generated contract tests execute: in ``correct`` mode every
response follows the spec; in ``broken`` mode some responses deliberately
violate it (wrong types, missing fields, wrong status) so the generated tests
must fail.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

VALID_TOKEN = "test-token-123"
PRODUCT = {
    "sku": "BK-001",
    "name": "The Pragmatic Programmer",
    "price": 42.0,
    "category": "books",
    "tags": ["software"],
    "createdAt": "2024-05-01T10:00:00Z",
    "discontinuedAt": None,
}


def make_handler(mode: str) -> type[BaseHTTPRequestHandler]:
    broken = mode == "broken"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send(self, status: int, body: Any, content_type: str = "application/json") -> None:
            raw = body.encode() if isinstance(body, str) else json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _authorized(self) -> bool:
            return self.headers.get("Authorization") == f"Bearer {VALID_TOKEN}"

        def do_GET(self) -> None:
            url = urlsplit(self.path)
            query = parse_qs(url.query)
            path = url.path
            if path == "/health":
                if broken:
                    self._send(503, {"status": "down"})
                else:
                    self._send(200, {"status": "ok"})
            elif path == "/products":
                if query.get("category") != ["books"]:
                    self._send(400, {"error": "category is required"})
                    return
                item = {**PRODUCT, "price": "42.00"} if broken else PRODUCT
                self._send(200, {"items": [item], "total": 1})
            elif path == "/products/BK-001":
                item = {k: v for k, v in PRODUCT.items() if k != "name"} if broken else PRODUCT
                self._send(200, item)
            elif path == "/warehouses/WH-PUNE-1/stock":
                if not self._authorized():
                    self._send(401, {"error": "unauthorized"})
                    return
                self._send(200, [{"sku": "BK-001", "quantity": -5 if broken else 12}])
            elif path == "/reports/stock.csv":
                self._send(200, "sku,quantity\nBK-001,12\n", "text/csv")
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            if urlsplit(self.path).path == "/products" and self._authorized():
                self._send(201, {**payload, "createdAt": "2026-11-21T07:00:00Z"})
            else:
                self._send(401, {"error": "unauthorized"})

    return Handler


@contextmanager
def running_server(mode: str = "correct") -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(mode))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
