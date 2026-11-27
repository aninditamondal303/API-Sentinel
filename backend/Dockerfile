# syntax=docker/dockerfile:1
# Build context: the backend/ directory.

# Toolchain used both for image builds and by scripts/test-backend.ps1.
# `unzip` is required: without it the Maven Wrapper silently switches to the .tar.gz distribution,
# whose SHA-256 differs from the pinned .zip checksum, and verification (correctly) fails.
FROM eclipse-temurin:25-jdk AS toolchain
RUN apt-get update \
 && apt-get install -y --no-install-recommends unzip curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

FROM toolchain AS build
WORKDIR /build
COPY .mvn .mvn
COPY mvnw pom.xml ./
RUN sh ./mvnw -B -ntp dependency:go-offline
COPY src src
# Tests need Docker (Testcontainers) and run separately via scripts/test-backend.ps1.
RUN sh ./mvnw -B -ntp package -DskipTests && cp target/apisentinel-backend-*.jar /build/app.jar

FROM eclipse-temurin:25-jre AS runtime
# curl is used only by the container HEALTHCHECK below.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --no-create-home app
WORKDIR /app
COPY --from=build /build/app.jar app.jar
USER 10001
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=40s --retries=5 \
  CMD curl -fsS http://localhost:8080/actuator/health/readiness >/dev/null || exit 1
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75", "-Djava.io.tmpdir=/tmp", "-jar", "/app/app.jar"]
