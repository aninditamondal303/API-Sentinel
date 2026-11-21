package dev.apisentinel.support;

import java.time.Duration;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.wait.strategy.Wait;
import org.testcontainers.postgresql.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;

/**
 * Real infrastructure shared by all integration tests: PostgreSQL 18 and the actual analyzer image
 * (built by scripts/test-backend.ps1 from analyzer/Dockerfile). Started once per JVM.
 */
public final class TestContainers {

    public static final String INTERNAL_TOKEN = "integration-test-internal-token-0123456789abcdef";
    public static final String ANALYZER_IMAGE = "apisentinel-analyzer:latest";

    public static final PostgreSQLContainer POSTGRES = new PostgreSQLContainer("postgres:18-alpine");

    private static GenericContainer<?> analyzer;

    static {
        POSTGRES.start();
    }

    private TestContainers() {
    }

    public static synchronized GenericContainer<?> analyzer() {
        if (analyzer == null) {
            analyzer = new GenericContainer<>(DockerImageName.parse(ANALYZER_IMAGE))
                    .withEnv("APISENTINEL_INTERNAL_TOKEN", INTERNAL_TOKEN)
                    .withExposedPorts(8081)
                    .waitingFor(Wait.forHttp("/health/ready").forPort(8081).forStatusCode(200)
                            .withStartupTimeout(Duration.ofSeconds(120)));
            analyzer.start();
        }
        return analyzer;
    }

    public static String analyzerUrl() {
        GenericContainer<?> container = analyzer();
        return "http://" + container.getHost() + ":" + container.getMappedPort(8081);
    }
}
