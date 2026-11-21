package dev.apisentinel.project;

import static org.assertj.core.api.Assertions.assertThat;

import dev.apisentinel.support.PostgresIntegrationTest;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class ProjectIntegrationTest extends PostgresIntegrationTest {

    @Test
    void crudLifecycle() {
        String token = api.register("Owner");
        String name = "Orders " + UUID.randomUUID().toString().substring(0, 8);
        var created = api.post("/api/v1/projects", Map.of("name", name, "description", "Orders API"), token)
                .expect(201);
        String id = created.str("id");
        assertThat(created.header("Location")).endsWith("/api/v1/projects/" + id);
        api.get(java.net.URI.create(created.header("Location")).getPath(), token).expect(200);
        assertThat(created.str("policy.failOn")).isEqualTo("HIGH");
        assertThat(created.path("policy.failOnManualReview")).isEqualTo(true);

        assertThat(api.get("/api/v1/projects", token).expect(200).num("totalItems")).isEqualTo(1);
        api.put("/api/v1/projects/" + id, Map.of("name", name + " v2", "description", "changed"), token).expect(200);
        assertThat(api.get("/api/v1/projects/" + id, token).expect(200).str("description")).isEqualTo("changed");

        api.delete("/api/v1/projects/" + id, token).expect(204);
        api.get("/api/v1/projects/" + id, token).expect(404);
    }

    @Test
    void duplicateNamesAreRejectedPerOwnerOnly() {
        String alice = api.register("Alice");
        String bob = api.register("Bob");
        String name = "Shared " + UUID.randomUUID().toString().substring(0, 8);
        api.post("/api/v1/projects", Map.of("name", name), alice).expect(201);
        assertThat(api.post("/api/v1/projects", Map.of("name", name.toUpperCase()), alice).expect(409)
                .str("errorCode")).isEqualTo("PROJECT_NAME_TAKEN");
        api.post("/api/v1/projects", Map.of("name", name), bob).expect(201);
    }

    @Test
    void usersCannotSeeOrChangeOtherUsersProjects() {
        String alice = api.register("Alice");
        String mallory = api.register("Mallory");
        String id = api.createProject(alice, "Private");

        api.get("/api/v1/projects/" + id, mallory).expect(404);
        api.put("/api/v1/projects/" + id, Map.of("name", "Hijacked"), mallory).expect(404);
        api.delete("/api/v1/projects/" + id, mallory).expect(404);
        api.get("/api/v1/projects/" + id + "/policy", mallory).expect(404);
        api.get("/api/v1/projects/" + id + "/specifications", mallory).expect(404);
        api.get("/api/v1/projects/" + id + "/scans", mallory).expect(404);
        assertThat(api.get("/api/v1/projects", mallory).expect(200).num("totalItems")).isZero();

        api.get("/api/v1/projects/" + id, alice).expect(200);
    }

    @Test
    void policyCanBeUpdatedAndDisabled() {
        String token = api.register("Owner");
        String id = api.createProject(token, "Policy");
        var updated = api.put("/api/v1/projects/" + id + "/policy",
                Map.of("failOn", "MEDIUM", "failOnManualReview", false), token).expect(200);
        assertThat(updated.str("failOn")).isEqualTo("MEDIUM");

        Map<String, Object> disabled = new HashMap<>();
        disabled.put("failOn", null);
        disabled.put("failOnManualReview", true);
        assertThat(api.put("/api/v1/projects/" + id + "/policy", disabled, token).expect(200).path("failOn"))
                .isNull();

        assertThat(api.put("/api/v1/projects/" + id + "/policy", Map.of("failOn", "SEVERE"), token).expect(400)
                .str("errorCode")).isEqualTo("MALFORMED_REQUEST");
    }

    @Test
    void invalidInputGivesConsistentProblems() {
        String token = api.register("Owner");
        assertThat(api.post("/api/v1/projects", Map.of("name", "x"), token).expect(400).str("errorCode"))
                .isEqualTo("VALIDATION_FAILED");
        assertThat(api.get("/api/v1/projects/not-a-uuid", token).expect(400).str("errorCode"))
                .isEqualTo("VALIDATION_FAILED");
        assertThat(api.postRaw("/api/v1/projects", "application/json", "{broken", token).expect(400)
                .str("errorCode")).isEqualTo("MALFORMED_REQUEST");
        api.get("/api/v1/projects/" + UUID.randomUUID(), token).expect(404);
    }
}
