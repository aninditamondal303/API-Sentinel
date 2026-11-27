package dev.apisentinel.auth;

import static org.assertj.core.api.Assertions.assertThat;

import dev.apisentinel.support.PostgresIntegrationTest;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class PasswordChangeIntegrationTest extends PostgresIntegrationTest {

    private static final String PASSWORD = "Correct-horse-9";
    private static final String PATH = "/api/v1/auth/password";

    private record Account(String email, String token) {
    }

    private Account register() {
        String email = "pw." + UUID.randomUUID() + "@example.com";
        String token = api.post("/api/v1/auth/register",
                Map.of("email", email, "password", PASSWORD, "displayName", "Grace"), null)
                .expect(201).str("accessToken");
        return new Account(email, token);
    }

    @Test
    void changesThePasswordSoOnlyTheNewOneSignsIn() {
        Account account = register();

        var response = api.post(PATH, Map.of("currentPassword", PASSWORD, "newPassword", "Battery-staple-7"),
                account.token()).expect(204);
        assertThat(response.body()).isEmpty();

        api.post("/api/v1/auth/login", Map.of("email", account.email(), "password", PASSWORD), null).expect(401);
        api.post("/api/v1/auth/login", Map.of("email", account.email(), "password", "Battery-staple-7"), null)
                .expect(200);
    }

    @Test
    void rejectsAWrongCurrentPasswordAsAFieldErrorWithoutEndingTheSession() {
        Account account = register();

        var response = api.post(PATH, Map.of("currentPassword", "Not-my-password-1", "newPassword", "Battery-staple-7"),
                account.token()).expect(400);
        assertThat(response.str("errorCode")).isEqualTo("INVALID_CURRENT_PASSWORD");
        assertThat(response.str("errors.0.field")).isEqualTo("currentPassword");

        // The old password still works and the token is still accepted.
        api.post("/api/v1/auth/login", Map.of("email", account.email(), "password", PASSWORD), null).expect(200);
        api.get("/api/v1/auth/me", account.token()).expect(200);
    }

    @Test
    void appliesTheRegistrationPasswordRulesAndRefusesTheSamePassword() {
        Account account = register();

        var weak = api.post(PATH, Map.of("currentPassword", PASSWORD, "newPassword", "short"), account.token())
                .expect(400);
        assertThat(weak.str("errorCode")).isEqualTo("VALIDATION_FAILED");
        assertThat(weak.str("errors.0.field")).isEqualTo("newPassword");

        var same = api.post(PATH, Map.of("currentPassword", PASSWORD, "newPassword", PASSWORD), account.token())
                .expect(400);
        assertThat(same.str("errors.0.field")).isEqualTo("newPassword");
        assertThat(same.str("errors.0.message")).contains("different");
    }

    @Test
    void requiresAuthentication() {
        api.post(PATH, Map.of("currentPassword", PASSWORD, "newPassword", "Battery-staple-7"), null).expect(401);
    }
}
