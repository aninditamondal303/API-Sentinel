#!/usr/bin/env bash
# Frontend: type check and Vitest (the Dockerfile's "test" target), then the production image.
# Same commands as scripts/test-frontend.ps1 and the "Frontend" job in .github/workflows/ci.yml.
# Usage (from anywhere): bash scripts/test-frontend.sh     Log: logs/frontend-tests.txt
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
log=logs/frontend-tests.txt

docker info >/dev/null 2>&1 || { echo "Docker is not running." >&2; exit 1; }

echo "== type check and tests $(date -u +%FT%TZ)" | tee "$log"
docker build --progress=plain --target test -t apisentinel-frontend-test frontend >>"$log" 2>&1 \
  || { grep -E "Tests |Test Files|error TS|FAIL" "$log" | tail -n 20 >&2; echo "Tests failed; see $log" >&2; exit 1; }
grep -E "Test Files|Tests " "$log" | tail -n 2

echo "== production image" | tee -a "$log"
docker build --target runtime -t apisentinel-frontend:latest frontend >>"$log" 2>&1 \
  || { echo "Production image build failed; see $log" >&2; exit 1; }

echo "Frontend: type check, tests and production build passed."
