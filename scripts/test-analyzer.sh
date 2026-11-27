#!/usr/bin/env bash
# Analyzer: builds the test image, then runs ruff, mypy and pytest inside it.
# Same commands as scripts/test-analyzer.ps1 and the "Analyzer" job in .github/workflows/ci.yml.
# Usage (from anywhere): bash scripts/test-analyzer.sh     Log: logs/analyzer-tests.txt
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
log=logs/analyzer-tests.txt

docker info >/dev/null 2>&1 || { echo "Docker is not running." >&2; exit 1; }

echo "== docker build (test image) $(date -u +%FT%TZ)" | tee "$log"
docker build -f analyzer/Dockerfile --target test -t apisentinel-analyzer-test . >>"$log" 2>&1 \
  || { echo "Image build failed; see $log" >&2; exit 1; }

status=0
echo "== ruff + mypy" | tee -a "$log"
docker run --rm apisentinel-analyzer-test sh -c \
  "python -m ruff check src tests && python -m ruff format --check src tests && python -m mypy" 2>&1 | tee -a "$log" \
  || status=1

echo "== pytest" | tee -a "$log"
docker run --rm apisentinel-analyzer-test 2>&1 | tee -a "$log" | tail -n 3 || status=1

[ "$status" -eq 0 ] && echo "Analyzer: all checks passed." || echo "Analyzer: failures; see $log" >&2
exit "$status"
