# syntax=docker/dockerfile:1
# Render.com free-tier image: the Spring Boot backend and the Python analyzer in ONE container.
#
# Why one container: Render free web services cannot receive private-network traffic, so a
# separate analyzer service would have to be public. Here the analyzer listens only on
# 127.0.0.1:8081 inside the container and is never reachable from outside; only the backend
# port ($PORT) is exposed. Application code is unchanged; the build steps mirror
# backend/Dockerfile and analyzer/Dockerfile. Build context: the repository root.
# The local Docker Compose stack does not use this file.

# ---- backend build (same as backend/Dockerfile) --------------------------------
FROM eclipse-temurin:25-jdk AS backend-build
RUN apt-get update \
 && apt-get install -y --no-install-recommends unzip curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY backend/.mvn .mvn
COPY backend/mvnw backend/pom.xml ./
RUN sh ./mvnw -B -ntp dependency:go-offline
COPY backend/src src
RUN sh ./mvnw -B -ntp package -DskipTests && cp target/apisentinel-backend-*.jar /build/app.jar

# ---- analyzer build (same as analyzer/Dockerfile) -------------------------------
FROM python:3.14-slim AS analyzer-build
COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app/analyzer
COPY analyzer/pyproject.toml analyzer/uv.lock analyzer/README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY analyzer/src ./src
RUN uv sync --locked --no-dev --no-editable

# ---- runtime: Python 3.14 base + Java 21 JRE copied from the official Temurin image ----
FROM python:3.14-slim AS runtime
COPY --from=eclipse-temurin:21-jre /opt/java/openjdk /opt/java/openjdk
COPY --from=analyzer-build /opt/venv /opt/venv
COPY --from=backend-build /build/app.jar /app/app.jar
COPY deploy/render/start.sh /app/start.sh
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app \
 && chmod 0555 /app/start.sh
ENV JAVA_HOME=/opt/java/openjdk \
    PATH="/opt/venv/bin:/opt/java/openjdk/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APISENTINEL_ANALYZER_URL=http://127.0.0.1:8081
USER 10001
WORKDIR /app
EXPOSE 10000
CMD ["/app/start.sh"]
