#!/bin/sh
# Entry point of the Render image: starts the analyzer on 127.0.0.1:8081 (private to the
# container) and the backend on $PORT. If either process exits, the container exits so Render
# restarts it. No secret is ever printed.
set -eu

# DATABASE_URL is the PostgreSQL connection string from the database provider, e.g.
#   postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require
# The backend expects a JDBC URL plus separate user and password, so split it here.
if [ -n "${DATABASE_URL:-}" ]; then
  rest=${DATABASE_URL#*://}
  creds=${rest%%@*}
  hostpart=${rest#*@}
  # libpq spells it channel_binding; the PostgreSQL JDBC driver calls it channelBinding.
  hostpart=$(printf '%s' "$hostpart" | sed 's/channel_binding=/channelBinding=/')
  export APISENTINEL_DB_URL="jdbc:postgresql://${hostpart}"
  export APISENTINEL_DB_USER="${creds%%:*}"
  export APISENTINEL_DB_PASSWORD="${creds#*:}"
fi

uvicorn apisentinel.api.app:create_app --factory --host 127.0.0.1 --port 8081 --no-access-log &
analyzer=$!

# 512 MB instance: keep the JVM well inside it, leaving room for the analyzer.
java -Xms64m -Xmx224m -Xss512k -XX:MaxMetaspaceSize=160m -XX:ReservedCodeCacheSize=48m \
     -XX:MaxDirectMemorySize=32m -XX:+UseSerialGC -XX:TieredStopAtLevel=1 \
     -Djava.io.tmpdir=/tmp -jar /app/app.jar &
backend=$!

# Exit as soon as either process stops.
while kill -0 "$analyzer" 2>/dev/null && kill -0 "$backend" 2>/dev/null; do
  sleep 5
done
echo "A process exited; stopping the container so Render restarts it." >&2
kill "$analyzer" "$backend" 2>/dev/null || true
exit 1
