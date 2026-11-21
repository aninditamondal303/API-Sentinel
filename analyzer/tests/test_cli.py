"""CLI behaviour, exit codes and output formats.

Runs the same ``main()`` that the installed ``apisentinel`` script calls, plus
one real subprocess run of the installed entry point.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from apisentinel.cli import EXIT_FAIL, EXIT_INPUT, EXIT_INTERNAL, EXIT_PASS, main
from apisentinel.rules import RULES

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "orders-api"
BASE = str(EXAMPLES / "baseline.yaml")
BREAKING = str(EXAMPLES / "candidate-breaking.yaml")
SAFE = str(EXAMPLES / "candidate-safe.yaml")


def cli(*args: str) -> tuple[int, str]:
    out = io.StringIO()
    code = main(list(args), out=out)
    return code, out.getvalue()


def test_breaking_candidate_fails_with_exit_1_and_expected_rules() -> None:
    code, output = cli("diff", BASE, BREAKING, "--format", "json")
    assert code == EXIT_FAIL
    result = json.loads(output)
    found = {(f["ruleId"], f["method"], f["path"]) for f in result["findings"]}
    assert ("OP-002", "DELETE", "/orders/{id}") in found
    assert ("OP-005", "GET", "/orders/{orderId}") in found  # {id} renamed to {orderId}
    assert ("OP-006", "POST", "/orders/{orderId}/cancel") in found
    assert ("REQ-PARAM-002", "GET", "/orders") in found  # new required tenantId
    assert ("REQ-PARAM-006", "GET", "/orders") in found  # limit maximum 100 -> 50
    assert ("REQ-BODY-003", "POST", "/orders") in found  # new required currency
    assert ("SEC-R001", "GET", "/orders/{orderId}") in found  # security: []
    assert ("RES-009", "GET", "/orders") in found  # OrderStatus gained ON_HOLD
    assert ("RES-005", "GET", "/orders/{orderId}") in found  # customerEmail removed
    assert ("RES-007", "POST", "/orders") in found  # total number -> string
    # Adding an enum value to a *request* parameter widens it: must not be flagged.
    assert ("REQ-PARAM-005", "GET", "/orders") not in found
    assert result["decision"]["result"] == "FAIL"


def test_additive_candidate_passes_with_exit_0() -> None:
    code, output = cli("diff", BASE, SAFE, "--format", "json")
    result = json.loads(output)
    assert code == EXIT_PASS, result["findings"]
    assert {f["severity"] for f in result["findings"]} == {"INFO"}


@pytest.mark.parametrize(
    ("threshold", "expected"),
    [("critical", EXIT_FAIL), ("high", EXIT_FAIL), ("none", EXIT_PASS)],
)
def test_fail_on_threshold(threshold: str, expected: int) -> None:
    # The breaking candidate has CRITICAL findings and no manual-review findings.
    code, _ = cli("diff", BASE, BREAKING, "--fail-on", threshold)
    assert code == expected


def test_manual_review_fails_by_default_and_can_be_allowed(tmp_path: Path) -> None:
    def write(name: str, pattern: str) -> str:
        path = tmp_path / name
        path.write_text(
            "openapi: 3.1.0\ninfo: {title: t, version: '1'}\npaths:\n  /a:\n    get:\n"
            "      parameters:\n        - {name: code, in: query, schema: "
            f"{{type: string, pattern: '{pattern}'}}}}\n"
            "      responses: {'200': {description: ok}}\n"
        )
        return str(path)

    old, new = write("old.yaml", "^[A-Z]+$"), write("new.yaml", "^[A-Z]{3}$")
    assert cli("diff", old, new)[0] == EXIT_FAIL  # REQ-PARAM-009 is MEDIUM + manual review
    assert cli("diff", old, new, "--allow-manual-review")[0] == EXIT_PASS


def test_text_output_is_readable() -> None:
    code, output = cli("diff", BASE, BREAKING, "--color", "never")
    assert code == EXIT_FAIL
    assert "DELETE /orders/{id}" in output
    assert "Result : FAIL" in output
    assert "\033[" not in output
    assert "INFO finding(s) hidden" in output


def test_color_always_emits_ansi() -> None:
    _, output = cli("diff", BASE, BREAKING, "--color", "always")
    assert "\033[" in output


def test_missing_file_is_input_error() -> None:
    code, output = cli("diff", BASE, "does-not-exist.yaml")
    assert code == EXIT_INPUT
    assert "File not found" in output


def test_invalid_spec_reports_side_and_issues_as_json(tmp_path: Path) -> None:
    broken = tmp_path / "broken.yaml"
    broken.write_text(
        "openapi: 3.1.0\ninfo: {title: x, version: '1'}\npaths:\n  /a:\n"
        "    get:\n      responses:\n        '200': {$ref: '#/nope'}\n"
    )
    code, output = cli("diff", BASE, str(broken), "--format", "json")
    assert code == EXIT_INPUT
    error = json.loads(output)["error"]
    assert error["code"] == "SPEC_INVALID"
    assert error["message"].startswith("candidate:")
    assert error["issues"][0]["pointer"] == "/paths/~1a/get/responses/200/$ref"


def test_oversized_file_is_rejected_before_reading(tmp_path: Path) -> None:
    big = tmp_path / "big.yaml"
    big.write_bytes(b"a: 1\n" * 300_000)
    code, output = cli("diff", BASE, str(big), "--max-size-mb", "1")
    assert code == EXIT_INPUT
    assert "SPEC_TOO_LARGE" in output


def test_bad_arguments_are_input_errors(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli("diff", BASE)[0] == EXIT_INPUT
    assert cli("diff", BASE, SAFE, "--fail-on", "severe")[0] == EXIT_INPUT
    assert "apisentinel --help" in capsys.readouterr().err


def test_validate_command() -> None:
    code, output = cli("validate", BASE, "--format", "json")
    assert code == EXIT_PASS
    assert json.loads(output)["operationCount"] == 4
    code, _ = cli("validate", "nope.yaml")
    assert code == EXIT_INPUT


def test_rules_command_lists_whole_catalog() -> None:
    code, output = cli("rules", "--format", "json")
    assert code == EXIT_PASS
    assert {r["id"] for r in json.loads(output)["rules"]} == set(RULES)


def test_unexpected_errors_return_exit_3(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated bug")

    monkeypatch.setattr("apisentinel.cli.analyze", boom)
    assert cli("diff", BASE, SAFE)[0] == EXIT_INTERNAL


def test_installed_entry_point_runs_as_a_real_process() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "apisentinel", "diff", BASE, BREAKING, "--fail-on", "critical"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == EXIT_FAIL
    assert "Result : FAIL" in proc.stdout


REAL = Path(__file__).resolve().parent / "fixtures" / "real"
INVENTORY = str(EXAMPLES.parent / "inventory-api" / "openapi.yaml")


def test_scan_command_reports_hygiene_and_threshold() -> None:
    code, output = cli("scan", str(REAL / "petstore.yaml"), "--format", "json")
    assert code == EXIT_PASS  # 4 MEDIUM findings, default threshold HIGH
    result = json.loads(output)
    assert {f["ruleId"] for f in result["findings"]} == {"SEC-H001", "SEC-H002"}
    assert "not a penetration test" in result["disclaimer"]
    assert cli("scan", str(REAL / "petstore.yaml"), "--fail-on", "medium")[0] == EXIT_FAIL


def test_scan_text_output_shows_disclaimer() -> None:
    code, output = cli("scan", str(REAL / "petstore.yaml"), "--color", "never")
    assert code == EXIT_PASS
    assert "not a penetration test" in output
    assert "SEC-H001" in output


def test_generate_tests_command_writes_suite_and_protects_files(tmp_path: Path) -> None:
    target = tmp_path / "contract-tests"
    code, output = cli("generate-tests", INVENTORY, "-o", str(target), "--format", "json")
    assert code == EXIT_PASS
    payload = json.loads(output)
    assert payload["summary"] == {"total": 7, "ready": 5, "skipped": 2, "schemaValidated": 4}
    assert (target / "operations.json").exists()
    code, output = cli("generate-tests", INVENTORY, "-o", str(target))
    assert code == EXIT_INPUT
    assert "OUTPUT_EXISTS" in output
    assert cli("generate-tests", INVENTORY, "-o", str(target), "--overwrite")[0] == EXIT_PASS
