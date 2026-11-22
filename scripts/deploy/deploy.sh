#!/usr/bin/env bash
# Build and start (or update) the production stack on the server. Run from the repository root:
#
#   bash scripts/deploy/deploy.sh <public-domain> <email-for-lets-encrypt>
#   e.g. bash scripts/deploy/deploy.sh apisentinel.duckdns.org you@example.com
#
# On the first run it creates .env with freshly generated random secrets (mode 600, git-ignored).
# On later runs it keeps every existing value, so the database password and JWT secret stay the
# same and the PostgreSQL volume keeps working. Secret values are never printed.
#
# Safe to re-run for redeployments: images are rebuilt, containers recreated, volumes kept.
# It never runs "docker compose down -v" and never removes volumes.
set -euo pipefail

cd "$(dirname "$0")/../.."
ROOT=$(pwd)
ENV_FILE="$ROOT/.env"

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <public-domain> <email-for-lets-encrypt>" >&2
  exit 2
fi
DOMAIN=$1
EMAIL=$2
if ! [[ $DOMAIN =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ && $DOMAIN == *.* ]]; then
  echo "Not a valid host name: $DOMAIN" >&2
  exit 2
fi
if ! [[ $EMAIL =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ ]]; then
  echo "Not a valid e-mail address: $EMAIL" >&2
  exit 2
fi

if docker info >/dev/null 2>&1; then DOCKER=(docker); else DOCKER=(sudo docker); fi

# ---------------------------------------------------------------- .env (secrets)
umask 077
touch "$ENV_FILE"
chmod 600 "$ENV_FILE"

has_key() { grep -q "^$1=" "$ENV_FILE"; }
set_if_missing() {
  local key=$1 value=$2
  if ! has_key "$key"; then
    printf '%s=%s\n' "$key" "$value" >>"$ENV_FILE"
    echo "  created $key"
  fi
}
set_or_update() {
  local key=$1 value=$2
  if has_key "$key"; then
    local tmp
    tmp=$(mktemp)
    grep -v "^$key=" "$ENV_FILE" >"$tmp"
    printf '%s=%s\n' "$key" "$value" >>"$tmp"
    cat "$tmp" >"$ENV_FILE"
    rm -f "$tmp"
  else
    printf '%s=%s\n' "$key" "$value" >>"$ENV_FILE"
  fi
}

echo "== Checking .env (values are not shown)"
set_if_missing POSTGRES_DB apisentinel
set_if_missing POSTGRES_USER apisentinel
set_if_missing POSTGRES_PASSWORD "$(openssl rand -hex 32)"
set_if_missing APISENTINEL_JWT_SECRET "$(openssl rand -base64 48 | tr -d '\n')"
set_if_missing APISENTINEL_INTERNAL_TOKEN "$(openssl rand -hex 32)"
set_or_update APISENTINEL_DOMAIN "$DOMAIN"
set_or_update ACME_EMAIL "$EMAIL"

# ---------------------------------------------------------------- DNS sanity check
public_ip=$(curl -fsS --max-time 10 https://api.ipify.org || true)
dns_ip=$(getent ahostsv4 "$DOMAIN" | awk 'NR==1{print $1}' || true)
echo "== DNS: $DOMAIN -> ${dns_ip:-unresolved}; this server's public IP: ${public_ip:-unknown}"
if [[ -n $public_ip && $dns_ip != "$public_ip" ]]; then
  echo "WARNING: $DOMAIN does not resolve to this server yet. Caddy cannot get a certificate until it does." >&2
fi

# ---------------------------------------------------------------- build and start
COMPOSE=("${DOCKER[@]}" compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose.prod.yml --env-file "$ENV_FILE")

echo "== Validating compose configuration"
"${COMPOSE[@]}" config --quiet

echo "== Building images (first build on a small VM can take 10-20 minutes)"
"${COMPOSE[@]}" build

echo "== Starting the stack and waiting for health checks"
"${COMPOSE[@]}" up -d --remove-orphans --wait --wait-timeout 600

"${COMPOSE[@]}" ps
echo
echo "Stack is up. Next: bash scripts/deploy/verify.sh"
