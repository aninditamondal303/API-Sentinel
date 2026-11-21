from __future__ import annotations

import pytest

from apisentinel.errors import SpecLoadError
from apisentinel.loading import MAX_DEPTH, load_document


def test_loads_json_and_yaml_to_identical_data() -> None:
    as_json = b'{"openapi": "3.1.0", "info": {"title": "T", "version": "1"}}'
    as_yaml = b"openapi: 3.1.0\ninfo:\n  title: T\n  version: '1'\n"
    assert load_document(as_json, "a.json") == load_document(as_yaml, "a.yaml")


def test_format_is_sniffed_when_filename_has_no_extension() -> None:
    assert load_document(b'{"a": 1}', None) == {"a": 1}
    assert load_document(b"a: 1\n", None) == {"a": 1}


def test_utf8_bom_is_accepted() -> None:
    assert load_document("﻿a: 1\n".encode(), "x.yaml") == {"a": 1}


def test_numeric_yaml_keys_become_strings() -> None:
    doc = load_document(b"responses:\n  200:\n    description: ok\n", "x.yaml")
    assert doc == {"responses": {"200": {"description": "ok"}}}


def test_yaml_timestamps_stay_strings() -> None:
    doc = load_document(b"example: 2024-01-31\n", "x.yaml")
    assert doc == {"example": "2024-01-31"}


def test_rejects_oversized_input_before_parsing() -> None:
    with pytest.raises(SpecLoadError) as info:
        load_document(b"a: 1\n" * 100, "x.yaml", max_bytes=50)
    assert info.value.code == "SPEC_TOO_LARGE"


def test_benign_yaml_anchors_are_accepted_and_expanded() -> None:
    doc = load_document(b"base: &b {type: string}\ncopy: *b\n", "x.yaml")
    assert doc == {"base": {"type": "string"}, "copy": {"type": "string"}}
    doc["copy"]["type"] = "integer"
    assert doc["base"]["type"] == "string"  # expanded into independent copies


def test_rejects_billion_laughs_alias_bomb() -> None:
    lines = ['l0: &l0 ["lol","lol","lol","lol","lol","lol","lol","lol","lol","lol"]']
    for level in range(1, 9):
        refs = ",".join([f"*l{level - 1}"] * 10)
        lines.append(f"l{level}: &l{level} [{refs}]")
    bomb = "\n".join(lines).encode()  # ~10^9 nodes once expanded, ~1 KB on disk
    with pytest.raises(SpecLoadError) as info:
        load_document(bomb, "bomb.yaml")
    assert "expands to more than" in info.value.message


@pytest.mark.parametrize(
    ("payload", "name"),
    [(b"a: 1\na: 2\n", "x.yaml"), (b'{"a": 1, "a": 2}', "x.json")],
)
def test_rejects_duplicate_keys(payload: bytes, name: str) -> None:
    with pytest.raises(SpecLoadError) as info:
        load_document(payload, name)
    assert "Duplicate key 'a'" in info.value.message


def test_rejects_excessive_nesting() -> None:
    deep = "[" * (MAX_DEPTH + 5) + "]" * (MAX_DEPTH + 5)
    with pytest.raises(SpecLoadError):
        load_document(('{"a": ' + deep + "}").encode(), "x.json")


@pytest.mark.parametrize(
    ("payload", "fragment"),
    [
        (b"", "empty"),
        (b"\xff\xfe\x00", "UTF-8"),
        (b'{"a": }', "Invalid JSON at line 1"),
        (b"a: [1, 2\n", "Invalid YAML"),
        (b"- 1\n- 2\n", "must be a mapping"),
    ],
)
def test_reports_readable_parse_errors(payload: bytes, fragment: str) -> None:
    with pytest.raises(SpecLoadError) as info:
        load_document(payload, "x.json" if payload.startswith(b"{") else "x.yaml")
    assert info.value.code == "SPEC_PARSE_ERROR"
    assert fragment in info.value.message


def test_python_object_tags_are_not_executed() -> None:
    with pytest.raises(SpecLoadError):
        load_document(b"a: !!python/object/apply:os.system ['echo hacked']\n", "x.yaml")
