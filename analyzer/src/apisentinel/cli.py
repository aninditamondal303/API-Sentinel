"""Command-line interface.

Exit codes (stable, for CI):
    0  analysis passed / spec valid
    1  analysis failed the configured threshold
    2  invalid input: missing file, unparsable or invalid spec, bad arguments
    3  unexpected internal error
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO

from apisentinel import RULESET_VERSION, __version__
from apisentinel.engine import FailurePolicy, InputError, SpecInput, analyze, load_spec
from apisentinel.errors import ApiSentinelError
from apisentinel.hygiene import scan
from apisentinel.loading import DEFAULT_MAX_BYTES
from apisentinel.rules import RULES, Severity
from apisentinel.testgen import GenerationOptions, generate_contract_tests, write_suite

EXIT_PASS, EXIT_FAIL, EXIT_INPUT, EXIT_INTERNAL = 0, 1, 2, 3

_COLORS = {
    "CRITICAL": "\033[1;31m",
    "HIGH": "\033[31m",
    "MEDIUM": "\033[33m",
    "LOW": "\033[36m",
    "INFO": "\033[2m",
    "PASS": "\033[1;32m",
    "FAIL": "\033[1;31m",
    "BOLD": "\033[1m",
    "DIM": "\033[2m",
}
_RESET = "\033[0m"


class _Painter:
    def __init__(self, stream: TextIO, mode: str) -> None:
        if mode == "always":
            self.enabled = True
        elif mode == "never" or os.environ.get("NO_COLOR"):
            self.enabled = False
        else:
            self.enabled = stream.isatty()

    def __call__(self, text: str, style: str) -> str:
        return f"{_COLORS[style]}{text}{_RESET}" if self.enabled and style in _COLORS else text


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        raise _UsageError(message)


def _read(path: str, max_bytes: int) -> SpecInput:
    file = Path(path)
    try:
        if file.stat().st_size > max_bytes:
            raise ApiSentinelError(
                code="SPEC_TOO_LARGE",
                message=f"{path} is larger than the {max_bytes}-byte limit (use --max-size-mb).",
            )
        return SpecInput(file.read_bytes(), file.name)
    except FileNotFoundError:
        raise ApiSentinelError(code="FILE_NOT_FOUND", message=f"File not found: {path}") from None
    except IsADirectoryError:
        raise ApiSentinelError(code="FILE_NOT_FOUND", message=f"Not a file: {path}") from None
    except PermissionError:
        raise ApiSentinelError(code="FILE_NOT_READABLE", message=f"Cannot read: {path}") from None


def _print_error(err: ApiSentinelError, out: TextIO, as_json: bool, paint: _Painter) -> None:
    if as_json:
        payload = {
            "error": {
                "code": err.code,
                "message": err.message,
                "issues": [i.to_dict() for i in err.issues],
            }
        }
        out.write(json.dumps(payload, indent=2) + "\n")
        return
    out.write(f"{paint('error', 'FAIL')}: {err.message} [{err.code}]\n")
    for issue in err.issues[:20]:
        where = f"{issue.pointer}: " if issue.pointer is not None else ""
        out.write(f"  - {where}{issue.message}\n")
    if len(err.issues) > 20:
        out.write(f"  ... and {len(err.issues) - 20} more\n")


def _render_text(result: dict[str, Any], out: TextIO, paint: _Painter, show_info: bool) -> None:
    base, cand = result["baseline"], result["candidate"]
    summary, decision = result["summary"], result["decision"]
    out.write(
        paint("API Sentinel", "BOLD") + f" {result['analyzer']['version']}"
        f" (ruleset {result['analyzer']['rulesetVersion']})\n"
    )
    out.write(
        f"Baseline : {base['title']} {base['apiVersion']} (OpenAPI {base['openapiVersion']},"
        f" {base['operationCount']} operations)\n"
    )
    out.write(
        f"Candidate: {cand['title']} {cand['apiVersion']} (OpenAPI {cand['openapiVersion']},"
        f" {cand['operationCount']} operations)\n\n"
    )

    findings = result["findings"]
    shown = [f for f in findings if show_info or f["severity"] != "INFO"]
    if not findings:
        out.write("No differences that affect compatibility or security were found.\n")
    groups: dict[str, list[dict[str, Any]]] = {}
    for finding in shown:
        endpoint = f"{finding['method']} {finding['path']}" if finding["path"] else "Document-level"
        groups.setdefault(endpoint, []).append(finding)
    for endpoint, items in groups.items():
        out.write(paint(endpoint, "BOLD") + "\n")
        for f in items:
            badge = paint(f"{f['severity']:<8}", f["severity"])
            review = paint(" [manual review]", "MEDIUM") if f["requiresManualReview"] else ""
            out.write(f"  {badge} {f['ruleId']:<13} {f['message']}{review}\n")
            out.write(
                paint(f"           at {f['location']} ({f['locationDocument']})", "DIM") + "\n"
            )
            if f["severity"] in {"CRITICAL", "HIGH"} or f["requiresManualReview"]:
                out.write(f"           impact: {f['impact']}\n")
                out.write(f"           fix:    {f['remediation']}\n")
        out.write("\n")
    hidden = len(findings) - len(shown)
    if hidden:
        out.write(paint(f"({hidden} INFO finding(s) hidden; use --show-info)", "DIM") + "\n\n")

    counts = ", ".join(f"{n} {s}" for s, n in summary["bySeverity"].items() if n)
    out.write(
        f"Summary: {summary['total']} finding(s)"
        + (f" ({counts})" if counts else "")
        + f"; {summary['breakingChanges']} breaking; {summary['manualReview']} need manual"
        f" review; {summary['endpointsAffected']} endpoint(s) affected.\n"
    )
    threshold = decision["failOn"] or "disabled"
    verdict = paint(decision["result"], decision["result"])
    reasons = f": {'; '.join(decision['reasons'])}" if decision["reasons"] else ""
    out.write(
        f"Result : {verdict} (fail-on {threshold}"
        f"{', manual review fails' if decision['failOnManualReview'] else ''}){reasons}\n"
    )


def _cmd_diff(args: argparse.Namespace, out: TextIO, paint: _Painter) -> int:
    max_bytes = int(args.max_size_mb * 1024 * 1024)
    fail_on = None if args.fail_on == "none" else Severity.parse(args.fail_on)
    policy = FailurePolicy(fail_on=fail_on, fail_on_manual_review=not args.allow_manual_review)
    try:
        baseline = _read(args.baseline, max_bytes)
        candidate = _read(args.candidate, max_bytes)
        result = analyze(baseline, candidate, policy, max_bytes=max_bytes)
    except (InputError, ApiSentinelError) as err:
        _print_error(err, out, args.format == "json", paint)
        return EXIT_INPUT
    if args.format == "json":
        out.write(json.dumps(result, indent=2) + "\n")
    else:
        _render_text(result, out, paint, args.show_info)
    return EXIT_PASS if result["decision"]["result"] == "PASS" else EXIT_FAIL


def _cmd_validate(args: argparse.Namespace, out: TextIO, paint: _Painter) -> int:
    max_bytes = int(args.max_size_mb * 1024 * 1024)
    try:
        loaded = load_spec(_read(args.spec, max_bytes), max_bytes)
    except ApiSentinelError as err:
        _print_error(err, out, args.format == "json", paint)
        return EXIT_INPUT
    facts = loaded.to_dict()
    if args.format == "json":
        out.write(json.dumps({"valid": True, **facts}, indent=2) + "\n")
    else:
        out.write(
            f"{paint('valid', 'PASS')}: {facts['title']} {facts['apiVersion']} "
            f"(OpenAPI {facts['openapiVersion']}, {facts['operationCount']} operations)\n"
        )
    return EXIT_PASS


def _cmd_rules(args: argparse.Namespace, out: TextIO, paint: _Painter) -> int:
    rules = sorted(RULES.values(), key=lambda r: r.id)
    if args.format == "json":
        payload = {"rulesetVersion": RULESET_VERSION, "rules": [r.to_dict() for r in rules]}
        out.write(json.dumps(payload, indent=2) + "\n")
        return EXIT_PASS
    for rule in rules:
        review = " (manual review)" if rule.manual_review else ""
        out.write(
            f"{rule.id:<14} {paint(f'{rule.severity.name:<8}', rule.severity.name)} "
            f"{rule.title}{review}\n"
        )
    return EXIT_PASS


def _cmd_scan(args: argparse.Namespace, out: TextIO, paint: _Painter) -> int:
    max_bytes = int(args.max_size_mb * 1024 * 1024)
    fail_on = None if args.fail_on == "none" else Severity.parse(args.fail_on)
    try:
        result = scan(load_spec(_read(args.spec, max_bytes), max_bytes), fail_on)
    except ApiSentinelError as err:
        _print_error(err, out, args.format == "json", paint)
        return EXIT_INPUT
    if args.format == "json":
        out.write(json.dumps(result, indent=2) + "\n")
    else:
        spec = result["spec"]
        out.write(
            paint("API Sentinel security scan", "BOLD") + f": {spec['title']} "
            f"{spec['apiVersion']} (OpenAPI {spec['openapiVersion']})\n"
        )
        out.write(paint(result["disclaimer"], "DIM") + "\n\n")
        if not result["findings"]:
            out.write("No specification-level security issues found.\n")
        for f in result["findings"]:
            where = f"{f['method']} {f['path']}" if f["path"] else "document"
            badge = paint(f"{f['severity']:<8}", f["severity"])
            out.write(f"  {badge} {f['ruleId']:<9} {f['message']}\n")
            out.write(paint(f"           at {f['location']} ({where})", "DIM") + "\n")
            out.write(f"           fix: {f['remediation']}\n")
        decision = result["decision"]
        counts = ", ".join(f"{n} {s}" for s, n in result["summary"]["bySeverity"].items() if n)
        reasons = f": {'; '.join(decision['reasons'])}" if decision["reasons"] else ""
        out.write(
            f"\nSummary: {result['summary']['total']} finding(s)"
            + (f" ({counts})" if counts else "")
            + "\n"
        )
        out.write(
            f"Result : {paint(decision['result'], decision['result'])} "
            f"(fail-on {decision['failOn'] or 'disabled'}){reasons}\n"
        )
    return EXIT_PASS if result["decision"]["result"] == "PASS" else EXIT_FAIL


def _cmd_generate_tests(args: argparse.Namespace, out: TextIO, paint: _Painter) -> int:
    max_bytes = int(args.max_size_mb * 1024 * 1024)
    try:
        loaded = load_spec(_read(args.spec, max_bytes), max_bytes)
    except ApiSentinelError as err:
        _print_error(err, out, args.format == "json", paint)
        return EXIT_INPUT
    options = GenerationOptions(
        include_unsafe_methods=args.include_unsafe_methods, default_base_url=args.base_url
    )
    suite = generate_contract_tests(loaded, options)
    target = Path(args.output)
    try:
        written = write_suite(suite, target, overwrite=args.overwrite)
    except FileExistsError as exc:
        _print_error(
            ApiSentinelError(code="OUTPUT_EXISTS", message=str(exc)),
            out,
            args.format == "json",
            paint,
        )
        return EXIT_INPUT
    except OSError as exc:
        _print_error(
            ApiSentinelError(code="OUTPUT_NOT_WRITABLE", message=str(exc)),
            out,
            args.format == "json",
            paint,
        )
        return EXIT_INPUT
    summary = suite.summary()
    if args.format == "json":
        payload = {
            "output": str(target),
            "files": [w.name for w in written],
            "summary": summary,
            "operations": suite.operations,
        }
        out.write(json.dumps(payload, indent=2) + "\n")
        return EXIT_PASS
    out.write(f"Wrote {len(written)} files to {target}\n\n")
    for record in suite.operations:
        status = (
            paint("ready  ", "PASS") if record["status"] == "ready" else paint("skipped", "MEDIUM")
        )
        detail = record["skipReason"] or "; ".join(record["notes"]) or ""
        out.write(f"  {status} {record['id']:<40} {detail}\n")
    out.write(
        f"\n{summary['ready']} of {summary['total']} operation(s) ready "
        f"({summary['schemaValidated']} with response-schema validation), "
        f"{summary['skipped']} skipped with a reason.\n"
    )
    out.write(f"Run: pytest {target} --base-url http://localhost:8080\n")
    return EXIT_PASS


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="apisentinel",
        description="Detect breaking changes between two OpenAPI 3.0/3.1 specifications.",
    )
    parser.add_argument("--version", action="version", version=f"apisentinel {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--format", choices=["text", "json"], default="text")
        p.add_argument("--color", choices=["auto", "always", "never"], default="auto")

    def size(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--max-size-mb",
            type=float,
            default=DEFAULT_MAX_BYTES / 1024 / 1024,
            help="Maximum spec size in MiB (default: 5).",
        )

    diff = sub.add_parser("diff", help="Compare a baseline spec with a candidate spec.")
    diff.add_argument("baseline", help="Path to the baseline (current) specification.")
    diff.add_argument("candidate", help="Path to the candidate (proposed) specification.")
    diff.add_argument(
        "--fail-on",
        default="high",
        choices=[s.name.lower() for s in Severity] + ["none"],
        help="Fail when any finding has this severity or higher (default: high).",
    )
    diff.add_argument(
        "--allow-manual-review",
        action="store_true",
        help="Do not fail on findings that require manual review.",
    )
    diff.add_argument("--show-info", action="store_true", help="Show INFO findings in text output.")
    common(diff)
    size(diff)

    validate = sub.add_parser("validate", help="Validate a single specification.")
    validate.add_argument("spec")
    common(validate)
    size(validate)

    scan_cmd = sub.add_parser("scan", help="Security hygiene checks on a single specification.")
    scan_cmd.add_argument("spec")
    scan_cmd.add_argument(
        "--fail-on", default="high", choices=[s.name.lower() for s in Severity] + ["none"]
    )
    common(scan_cmd)
    size(scan_cmd)

    gen = sub.add_parser("generate-tests", help="Generate pytest contract tests from a spec.")
    gen.add_argument("spec")
    gen.add_argument("-o", "--output", required=True, help="Directory to write the tests into.")
    gen.add_argument(
        "--include-unsafe-methods",
        action="store_true",
        help="Also test POST/PUT/PATCH/DELETE (they may change server data).",
    )
    gen.add_argument("--base-url", default=None, help="Default base URL stored in the suite.")
    gen.add_argument("--overwrite", action="store_true", help="Replace previously generated files.")
    common(gen)
    size(gen)

    rules = sub.add_parser("rules", help="List all rules.")
    common(rules)
    return parser


def main(argv: Sequence[str] | None = None, out: TextIO | None = None) -> int:
    stream = out or sys.stdout
    if stream is sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # e.g. legacy Windows code pages
    try:
        args = build_parser().parse_args(argv)
    except _UsageError as err:
        sys.stderr.write(f"apisentinel: error: {err}\nRun 'apisentinel --help' for usage.\n")
        return EXIT_INPUT
    except SystemExit as exc:  # --help / --version
        return int(exc.code or 0)
    paint = _Painter(stream, args.color)
    handlers = {
        "diff": _cmd_diff,
        "validate": _cmd_validate,
        "scan": _cmd_scan,
        "generate-tests": _cmd_generate_tests,
        "rules": _cmd_rules,
    }
    try:
        return handlers[args.command](args, stream, paint)
    except Exception as exc:  # last line of defence: never a raw traceback in CI
        sys.stderr.write(
            f"apisentinel: internal error ({type(exc).__name__}: {exc}). "
            "This is a bug; please report it with the specs that triggered it.\n"
        )
        return EXIT_INTERNAL


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
