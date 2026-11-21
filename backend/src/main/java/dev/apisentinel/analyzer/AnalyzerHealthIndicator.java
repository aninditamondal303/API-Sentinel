package dev.apisentinel.analyzer;

import org.springframework.boot.health.contributor.Health;
import org.springframework.boot.health.contributor.HealthIndicator;
import org.springframework.stereotype.Component;

/** Reports whether the Python analyzer answers its readiness probe (component "analyzer" in /actuator/health). */
@Component("analyzer")
public class AnalyzerHealthIndicator implements HealthIndicator {

    private final AnalyzerClient client;

    public AnalyzerHealthIndicator(AnalyzerClient client) {
        this.client = client;
    }

    @Override
    public Health health() {
        return client.isReady() ? Health.up().build() : Health.down().build();
    }
}
