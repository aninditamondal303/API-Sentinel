"""RFC 6901 JSON Pointer helpers."""

from __future__ import annotations

from typing import Any


def escape(token: str | int) -> str:
    return str(token).replace("~", "~0").replace("/", "~1")


def unescape(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def join(base: str, *tokens: str | int) -> str:
    return base + "".join("/" + escape(t) for t in tokens)


def resolve(document: Any, pointer: str) -> Any:
    """Resolve ``pointer`` ("" or "/a/b") inside ``document``.

    Raises:
        KeyError: if any segment does not exist.
    """
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise KeyError(pointer)
    current = document
    for raw in pointer[1:].split("/"):
        token = unescape(raw)
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            raise KeyError(pointer)
    return current
