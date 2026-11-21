package dev.apisentinel.support;

import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/** Adds the real Python analyzer container: Java-to-Python calls in these tests are genuine. */
public abstract class FullStackIntegrationTest extends PostgresIntegrationTest {

    @DynamicPropertySource
    static void analyzer(DynamicPropertyRegistry registry) {
        registry.add("apisentinel.analyzer.base-url", TestContainers::analyzerUrl);
    }
}
