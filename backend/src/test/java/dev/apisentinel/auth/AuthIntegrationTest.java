package dev.apisentinel.auth;

import static org.assertj.core.api.Assertions.assertThat;

import dev.apisentinel.support.PostgresIntegrationTest;
import dev.apisentinel.user.User;
import dev.apisentinel.user.UserRepository;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;

class AuthIntegrationTest extends PostgresIntegrationTest {

    @Autowired
    UserRepository users;

    @Autowired
    JwtService jwtService;

    private static String email() {
        return "user." + UUID.randomUUID() + "@example.com";
    }

    @Test
    void registerLoginAndMe() {
        String email = email();
        var registered = api.post("/api/v1/auth/register",
                Map.of("email", email, "password", "Correct-horse-9", "displayName", "Ada"), null).expect(201);
        assertThat(registered.str("tokenType")).isEqualTo("Bearer");
        assertThat(registered.str("user.email")).isEqualTo(email);
        assertThat(registered.body()).doesNotContain("password");

        var login = api.post("/api/v1/auth/login", Map.of("email", email.toUpperCase(), "password", "Correct-horse-9"),
                null).expect(200);
        String token = login.str("accessToken");
        assertThat(login.num("expiresIn")).isPositive();

        var me = api.get("/api/v1/auth/me", token).expect(200);
        assertThat(me.str("email")).isEqualTo(email);
        assertThat(me.str("displayName")).isEqualTo("Ada");
    }

    @Test
    void passwordIsStoredAsBcryptHash() {
        String email = email();
        api.post("/api/v1/auth/register", Map.of("email", email, "password", "Correct-horse-9", "displayName", "B"),
                null).expect(201);
        User user = users.findByEmailIgnoreCase(email).orElseThrow();
        assertThat(user.getPasswordHash()).startsWith("{bcrypt}").doesNotContain("Correct-horse-9");
    }

    @Test
    void duplicateEmailIsRejectedCaseInsensitively() {
        String email = email();
        api.post("/api/v1/auth/register", Map.of("email", email, "password", "Correct-horse-9", "displayName", "C"),
                null).expect(201);
        var dup = api.post("/api/v1/auth/register",
                Map.of("email", email.toUpperCase(), "password", "Correct-horse-9", "displayName", "C"), null)
                .expect(409);
        assertThat(dup.str("errorCode")).isEqualTo("EMAIL_TAKEN");
        assertThat(dup.header("Content-Type")).contains("application/problem+json");
    }

    @Test
    void registrationValidatesInput() {
        var weak = api.post("/api/v1/auth/register",
                Map.of("email", "not-an-email", "password", "short", "displayName", ""), null).expect(400);
        assertThat(weak.str("errorCode")).isEqualTo("VALIDATION_FAILED");
        assertThat(weak.list("errors")).extracting(e -> e.get("field"))
                .contains("email", "password", "displayName");
    }

    @Test
    void wrongPasswordAndUnknownEmailGiveTheSameAnswer() {
        String email = email();
        api.post("/api/v1/auth/register", Map.of("email", email, "password", "Correct-horse-9", "displayName", "D"),
                null).expect(201);
        var wrong = api.post("/api/v1/auth/login", Map.of("email", email, "password", "Wrong-horse-9"), null)
                .expect(401);
        var unknown = api.post("/api/v1/auth/login", Map.of("email", email(), "password", "Wrong-horse-9"), null)
                .expect(401);
        assertThat(wrong.str("errorCode")).isEqualTo("INVALID_CREDENTIALS");
        assertThat(unknown.str("detail")).isEqualTo(wrong.str("detail"));
    }

    @Test
    void repeatedFailuresAreThrottled() {
        String email = email();
        api.post("/api/v1/auth/register", Map.of("email", email, "password", "Correct-horse-9", "displayName", "E"),
                null).expect(201);
        for (int i = 0; i < 5; i++) {
            api.post("/api/v1/auth/login", Map.of("email", email, "password", "Wrong-horse-9"), null).expect(401);
        }
        var blocked = api.post("/api/v1/auth/login", Map.of("email", email, "password", "Correct-horse-9"), null)
                .expect(429);
        assertThat(blocked.str("errorCode")).isEqualTo("TOO_MANY_ATTEMPTS");
    }

    @Test
    void protectedEndpointsRequireAValidToken() {
        assertThat(api.get("/api/v1/projects", null).expect(401).str("errorCode")).isEqualTo("UNAUTHENTICATED");
        api.get("/api/v1/projects", "not.a.jwt").expect(401);
        api.get("/api/v1/dashboard", null).expect(401);
    }

    @Test
    void tamperedAndExpiredTokensAreRejected() {
        String email = email();
        String token = api.post("/api/v1/auth/register",
                Map.of("email", email, "password", "Correct-horse-9", "displayName", "F"), null).expect(201)
                .str("accessToken");
        String[] parts = token.split("\\.");
        String tampered = parts[0] + "." + parts[1] + "." + new StringBuilder(parts[2]).reverse();
        api.get("/api/v1/auth/me", tampered).expect(401);

        User user = users.findByEmailIgnoreCase(email).orElseThrow();
        String expired = jwtService.issue(user, Instant.now().minus(3, ChronoUnit.HOURS));
        api.get("/api/v1/auth/me", expired).expect(401);
        api.get("/api/v1/auth/me", jwtService.issue(user)).expect(200);
    }

    @Test
    void responsesCarryARequestId() {
        var res = api.get("/actuator/health/liveness", null).expect(200);
        assertThat(res.header("X-Request-Id")).isNotBlank();
    }
}
