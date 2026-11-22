#!/usr/bin/env bash
# Write a compressed pg_dump of the API Sentinel database to ~/apisentinel-backups (mode 600).
# Read-only for the database. Keeps the newest 14 dumps. Run from the repository root:
#
#   bash scripts/deploy/backup-db.sh
#
# Optional daily cron (crontab -e):
#   15 3 * * * cd $HOME/API-Sentinel && bash scripts/deploy/backup-db.sh >/dev/null 2>&1
set -euo pipefail

cd "$(dirname "$0")/../.."
if docker info >/dev/null 2>&1; then DOCKER=(docker); else DOCKER=(sudo docker); fi
COMPOSE=("${DOCKER[@]}" compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose.prod.yml --env-file .env)

dir="$HOME/apisentinel-backups"
umask 077
mkdir -p "$dir"
file="$dir/apisentinel-$(date -u +%Y%m%dT%H%M%SZ).sql.gz"

# Credentials are read inside the container from its own environment; nothing is printed.
"${COMPOSE[@]}" exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner' | gzip >"$file"
chmod 600 "$file"
ls -1t "$dir"/apisentinel-*.sql.gz | tail -n +15 | xargs -r rm -f
echo "Backup written: $file ($(du -h "$file" | cut -f1))"
