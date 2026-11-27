#!/usr/bin/env bash
# Backend: Maven verify with Testcontainers (real PostgreSQL 18 and the real analyzer image).
# Like scripts/test-backend.ps1, Maven runs inside the eclipse-temurin:21-jdk toolchain image, so
# no local Java is needed; the tests start their containers through the host's Docker socket.
# Usage (from anywhere): bash scripts/test-backend.sh     Log: logs/backend-tests.txt
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
log=logs/backend-tests.txt
repo=$(pwd)

docker info >/dev/null 2>&1 || { echo "Docker is not running." >&2; exit 1; }

echo "== analyzer runtime image $(date -u +%FT%TZ)" | tee "$log"
docker build -f analyzer/Dockerfile --target runtime -t apisentinel-analyzer:latest . >>"$log" 2>&1 \
  || { echo "Analyzer image build failed; see $log" >&2; exit 1; }

echo "== backend toolchain image" | tee -a "$log"
docker build -f backend/Dockerfile --target toolchain -t apisentinel-backend-toolchain backend >>"$log" 2>&1 \
  || { echo "Toolchain image build failed; see $log" >&2; exit 1; }

echo "== mvnw verify (the first run downloads Maven dependencies)" | tee -a "$log"
# host.docker.internal is predefined on Docker Desktop; --add-host provides it on Linux engines.
set +e
docker run --rm \
  -v "$repo:/workspace" \
  -v apisentinel-m2:/root/.m2 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  --add-host=host.docker.internal:host-gateway \
  -e TESTCONTAINERS_HOST_OVERRIDE=host.docker.internal \
  -w /workspace/backend \
  apisentinel-backend-toolchain \
  sh ./mvnw -B -ntp verify >>"$log" 2>&1
mvn=$?
set -e

grep -E "Tests run: [0-9]+, Failures|BUILD (SUCCESS|FAILURE)" "$log" | tail -n 2
[ "$mvn" -eq 0 ] || { echo "Backend tests failed; see $log and backend/target/surefire-reports/" >&2; exit 1; }
echo "Backend: all tests passed."
