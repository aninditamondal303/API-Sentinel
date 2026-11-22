#!/usr/bin/env bash
# Verify a production deployment on the server. Run from the repository root after deploy.sh:
#
#   bash scripts/deploy/verify.sh               # infrastructure checks + full end-to-end smoke test
#   bash scripts/deploy/verify.sh --restart     # also restart every container, then re-check
#                                               # that the earlier test data survived
#
# Exits non-zero if any check fails. Prints no secret values.
set -uo pipefail

cd "$(dirname "$0")/../.." || exit 1
ENV_FILE=.env
DOMAIN=$(grep '^APISENTINEL_DOMAIN=' "$ENV_FILE" | cut -d= -f2-)
BASE="https://$DOMAIN"
if docker info >/dev/null 2>&1; then DOCKER=(docker); else DOCKER=(sudo docker); fi
COMPOSE=("${DOCKER[@]}" compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose.prod.yml --env-file "$ENV_FILE")

pass=0; fail=0
check() { if [[ $2 == 0 ]]; then pass=$((pass+1)); echo "  [PASS] $1 $3"; else fail=$((fail+1)); echo "  [FAIL] $1 $3"; fi; }

container_checks() {
  echo "== Containers"
  for svc in postgres analyzer backend frontend; do
    id=$("${COMPOSE[@]}" ps -q "$svc")
    h=$("${DOCKER[@]}" inspect -f '{{.State.Health.Status}}' "$id" 2>/dev/null || echo missing)
    [[ $h == healthy ]]; check "$svc healthy" $? "($h)"
  done
  id=$("${COMPOSE[@]}" ps -q caddy)
  s=$("${DOCKER[@]}" inspect -f '{{.State.Status}}' "$id" 2>/dev/null || echo missing)
  [[ $s == running ]]; check "caddy running" $? "($s)"
}

exposure_checks() {
  echo "== Exposure (only 80/443 published, nothing else)"
  published=$("${DOCKER[@]}" ps --format '{{.Names}} {{.Ports}}' | grep -E '0\.0\.0\.0|\[::\]|127\.0\.0\.1' || true)
  others=$(echo "$published" | grep -v '^apisentinel-caddy' | grep -E '\->' || true)
  [[ -z $others ]]; check "No host port published except caddy" $? "${others:+-> $others}"
  for port in 5432 8081 8080 3000; do
    ! ss -ltnH "( sport = :$port )" | grep -q .; check "Nothing listening on host port $port" $? ""
  done
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:8080/" || true)
  [[ $code == 000 ]]; check "Backend not reachable on host :8080" $? "($code)"
}

http_checks() {
  echo "== Public HTTPS ($BASE)"
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$BASE/")
  [[ $code == 200 ]]; check "GET / over HTTPS with a valid certificate" $? "($code)"
  redirect=$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' --max-time 20 "http://$DOMAIN/")
  [[ $redirect == 30[18]\ https://* ]]; check "HTTP redirects to HTTPS" $? "($redirect)"
  issuer=$(echo | openssl s_client -connect "$DOMAIN:443" -servername "$DOMAIN" 2>/dev/null | openssl x509 -noout -issuer -enddate 2>/dev/null | tr '\n' ' ')
  [[ -n $issuer ]]; check "Certificate details" $? "($issuer)"
  headers=$(curl -sI --max-time 20 "$BASE/")
  grep -qi '^strict-transport-security:' <<<"$headers"; check "HSTS header" $? ""
  grep -qi '^content-security-policy:' <<<"$headers"; check "CSP header (from nginx)" $? ""
  health=$(curl -s --max-time 20 "$BASE/actuator/health")
  grep -q '"status":"UP"' <<<"$health"; check "/actuator/health UP" $? ""
  for p in /actuator/env /actuator/beans /actuator; do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$BASE$p")
    [[ $code == 404 ]]; check "$p not exposed" $? "($code)"
  done
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$BASE/api/v1/projects")
  [[ $code == 401 ]]; check "API requires authentication" $? "($code)"
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$BASE/dashboard")
  [[ $code == 200 ]]; check "SPA deep link served" $? "($code)"
}

container_checks
exposure_checks
http_checks

echo "== End-to-end flow through $BASE"
python3 scripts/deploy/smoke_test.py "$BASE"; check "End-to-end smoke test" $? ""

if [[ ${1:-} == --restart ]]; then
  echo "== Restarting all containers (volumes untouched)"
  "${COMPOSE[@]}" restart
  "${COMPOSE[@]}" up -d --wait --wait-timeout 600 >/dev/null
  container_checks
  python3 scripts/deploy/smoke_test.py "$BASE" --persist; check "Data persisted across restart" $? ""
fi

echo
echo "Result: $pass passed, $fail failed"
[[ $fail == 0 ]]
