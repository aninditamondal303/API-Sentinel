# syntax=docker/dockerfile:1
# API Sentinel analyzer. Build context: the repository root.
#   docker build -f analyzer/Dockerfile --target runtime -t apisentinel-analyzer .
#   docker build -f analyzer/Dockerfile --target test    -t apisentinel-analyzer-test .

ARG PYTHON_IMAGE=python:3.14-slim

# ---- dependencies + application (shared by test and runtime) -------------------
FROM ${PYTHON_IMAGE} AS build
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

# ---- test image: full dev dependencies and the test suite ----------------------
FROM build AS test
RUN uv sync --locked
COPY analyzer/tests ./tests
COPY examples /app/examples
COPY contracts /app/contracts
ENV PATH="/opt/venv/bin:${PATH}"
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]

# ---- runtime image: no build tools, no tests, non-root -------------------------
FROM ${PYTHON_IMAGE} AS runtime
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin analyzer
COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
USER analyzer
EXPOSE 8081
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8081/health/ready', timeout=2).status == 200 else 1)"]
CMD ["uvicorn", "apisentinel.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8081", "--no-access-log"]
