package dev.apisentinel;

import static org.assertj.core.api.Assertions.assertThat;

import dev.apisentinel.support.FullStackIntegrationTest;
import org.junit.jupiter.api.Test;

class HealthIntegrationTest extends FullStackIntegrationTest {

    @Test
    void livenessAndReadinessAreUp() {
        assertThat(api.get("/actuator/health/liveness", null).expect(200).str("status")).isEqualTo("UP");
        assertThat(api.get("/actuator/health/readiness", null).expect(200).str("status")).isEqualTo("UP");
    }

    @Test
    void componentsAreVisibleOnlyToAuthenticatedCallers() {
        var anonymous = api.get("/actuator/health", null).expect(200);
        assertThat(anonymous.str("status")).isEqualTo("UP");
        assertThat(anonymous.path("components")).isNull();

        var authenticated = api.get("/actuator/health", api.register("Ops")).expect(200);
        assertThat(authenticated.str("components.db.status")).isEqualTo("UP");
        assertThat(authenticated.str("components.analyzer.status")).isEqualTo("UP");
        assertThat(authenticated.body()).doesNotContain("jdbc:").doesNotContain("integration-test-internal-token");
    }

    @Test
    void otherActuatorEndpointsAreNotExposed() {
        String token = api.register("Ops");
        api.get("/actuator/env", token).expect(404);
        api.get("/actuator/beans", token).expect(404);
    }
}
