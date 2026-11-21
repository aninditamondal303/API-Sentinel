# syntax=docker/dockerfile:1
# Build context: the frontend/ directory.

FROM node:24-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# `docker build --target test` runs type checking and the unit/component tests.
FROM deps AS test
COPY . .
RUN npm run typecheck && npm test

FROM deps AS build
COPY . .
# The CSP allows fonts and images only from 'self': fail the build if any asset was inlined as a data: URI.
RUN npm run build && ! grep -rlE "url\(\"?data:" dist

# Static files served by unprivileged nginx (non-root user, listens on 8080).
FROM nginxinc/nginx-unprivileged:stable-alpine AS runtime
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
  CMD wget -qO- http://127.0.0.1:8080/healthz >/dev/null || exit 1
