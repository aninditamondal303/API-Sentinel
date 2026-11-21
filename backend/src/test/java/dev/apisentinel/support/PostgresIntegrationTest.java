package dev.apisentinel.support;

import java.util.Base64;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/** Boots the whole application on a random port against a real PostgreSQL container. */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
public abstract class PostgresIntegrationTest {

    /** Test-only signing key (48 bytes). Production keys come from APISENTINEL_JWT_SECRET. */
    public static final String JWT_SECRET = Base64.getEncoder()
            .encodeToString("test-only-jwt-signing-key-do-not-use-in-prod-48b".getBytes());

    @Value("${local.server.port}")
    protected int port;

    protected TestApi api;

    @DynamicPropertySource
    static void database(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", TestContainers.POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", TestContainers.POSTGRES::getUsername);
        registry.add("spring.datasource.password", TestContainers.POSTGRES::getPassword);
        registry.add("apisentinel.jwt.secret", () -> JWT_SECRET);
        registry.add("apisentinel.analyzer.token", () -> TestContainers.INTERNAL_TOKEN);
    }

    @BeforeEach
    void createApiClient() {
        api = new TestApi("http://localhost:" + port);
    }
}
