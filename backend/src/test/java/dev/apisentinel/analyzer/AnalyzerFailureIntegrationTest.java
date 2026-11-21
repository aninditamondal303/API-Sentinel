package dev.apisentinel.analyzer;

import static org.assertj.core.api.Assertions.assertThat;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import dev.apisentinel.support.PostgresIntegrationTest;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/**
 * Failure modes cannot be produced on demand by the real analyzer, so this test points the backend at a
 * tiny local HTTP server that misbehaves in controlled ways. Everything else (DB, Spring, HTTP) is real.
 */
class AnalyzerFailureIntegrationTest extends PostgresIntegrationTest {

    enum Mode { OK, SLOW, ERROR_500, GARBAGE, DROP, UNAUTHORIZED }

    static final AtomicReference<Mode> MODE = new AtomicReference<>(Mode.OK);
    static final HttpServer STUB = startStub();

    private static final String VALID = """
            {"valid":true,"spec":{"openapiVersion":"3.0.3","title":"Stub","apiVersion":"1",
             "operationCount":1,"sha256":"x"},"error":null}""";

    @Autowired
    JdbcTemplate jdbc;

    @DynamicPropertySource
    static void stubAnalyzer(DynamicPropertyRegistry registry) {
        registry.add("apisentinel.analyzer.base-url",
                () -> "http://127.0.0.1:" + STUB.getAddress().getPort());
        registry.add("apisentinel.analyzer.read-timeout", () -> "2s");
    }

    @AfterAll
    static void stop() {
        STUB.stop(0);
    }

    private static HttpServer startStub() {
        try {
            HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
            server.setExecutor(Executors.newCachedThreadPool());
            server.createContext("/internal/v1/specs/validate", ex -> respond(ex, 200, VALID));
            server.createContext("/internal/v1/", AnalyzerFailureIntegrationTest::misbehave);
            server.start();
            return server;
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    private static void misbehave(HttpExchange ex) throws IOException {
        ex.getRequestBody().readAllBytes();
        switch (MODE.get()) {
            case SLOW -> {
                try {
                    Thread.sleep(5000);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
                respond(ex, 200, "{}");
            }
            case ERROR_500 -> respond(ex, 500,
                    "{\"title\":\"Internal\",\"detail\":\"Traceback secret at /opt/venv\",\"errorCode\":\"INTERNAL\"}");
            case GARBAGE -> respond(ex, 200, "<html>not json</html>");
            case UNAUTHORIZED -> respond(ex, 401, "{\"errorCode\":\"UNAUTHORIZED\"}");
            case DROP -> ex.close();
            default -> respond(ex, 500, "{}");
        }
    }

    private static void respond(HttpExchange ex, int status, String body) throws IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().add("Content-Type", "application/json");
        ex.sendResponseHeaders(status, bytes.length);
        ex.getResponseBody().write(bytes);
        ex.close();
    }

    private record Setup(String token, String scans, String spec) {
    }

    private Setup setup() {
        MODE.set(Mode.OK);
        String token = api.register("Owner");
        String project = api.createProject(token, "Failing");
        String spec = api.upload("/api/v1/projects/" + project + "/specifications", "s.yaml",
                "openapi: 3.0.3".getBytes(StandardCharsets.UTF_8), "v1", token).expect(201).str("id");
        return new Setup(token, "/api/v1/projects/" + project + "/scans", spec);
    }

    private void assertFailedScanPersisted(String scanId, String code) {
        Map<String, Object> row = jdbc.queryForMap(
                "SELECT status, error_code, completed_at FROM scans WHERE id = ?::uuid", scanId);
        assertThat(row.get("status")).isEqualTo("FAILED");
        assertThat(row.get("error_code")).isEqualTo(code);
        assertThat(row.get("completed_at")).isNotNull();
    }

    @Test
    void timeoutGives504AndAFailedScan() {
        Setup s = setup();
        MODE.set(Mode.SLOW);
        var res = api.post(s.scans() + "/security", Map.of("specificationId", s.spec()), s.token()).expect(504);
        assertThat(res.str("errorCode")).isEqualTo("ANALYZER_TIMEOUT");
        assertFailedScanPersisted(res.str("scanId"), "ANALYZER_TIMEOUT");
    }

    @Test
    void analyzer500Gives502WithoutLeakingDetails() {
        Setup s = setup();
        MODE.set(Mode.ERROR_500);
        var res = api.post(s.scans() + "/security", Map.of("specificationId", s.spec()), s.token()).expect(502);
        assertThat(res.str("errorCode")).isEqualTo("ANALYZER_ERROR");
        assertThat(res.body()).doesNotContain("Traceback").doesNotContain("/opt/venv")
                .doesNotContain("integration-test-internal-token");
        assertFailedScanPersisted(res.str("scanId"), "ANALYZER_ERROR");

        var listed = api.get(s.scans() + "/" + res.str("scanId"), s.token()).expect(200);
        assertThat(listed.str("status")).isEqualTo("FAILED");
    }

    @Test
    void misconfiguredTokenIsReportedAsAnalyzerError() {
        Setup s = setup();
        MODE.set(Mode.UNAUTHORIZED);
        api.post(s.scans() + "/security", Map.of("specificationId", s.spec()), s.token()).expect(502);
    }

    @Test
    void nonJsonResponseGives502() {
        Setup s = setup();
        MODE.set(Mode.GARBAGE);
        assertThat(api.post(s.scans() + "/security", Map.of("specificationId", s.spec()), s.token()).expect(502)
                .str("errorCode")).isEqualTo("ANALYZER_ERROR");
    }

    @Test
    void droppedConnectionGives503() {
        Setup s = setup();
        MODE.set(Mode.DROP);
        var res = api.post(s.scans() + "/security", Map.of("specificationId", s.spec()), s.token());
        assertThat(res.status()).as(res.body()).isIn(502, 503);
        assertFailedScanPersisted(res.str("scanId"), res.str("errorCode"));
    }

    @Test
    void analyzerWithoutReadinessProbeIsDownButBackendStaysReady() {
        // The stub has no /health/ready endpoint (404), so the analyzer component must report DOWN.
        String token = api.register("Ops");
        var health = api.get("/actuator/health", token).expect(503);
        assertThat(health.str("components.analyzer.status")).isEqualTo("DOWN");
        assertThat(health.str("components.db.status")).isEqualTo("UP");
        assertThat(api.get("/actuator/health/readiness", null).expect(200).str("status")).isEqualTo("UP");
    }

    @Test
    void contractTestFailureIsNotPersistedAsScan() {
        Setup s = setup();
        MODE.set(Mode.ERROR_500);
        String project = s.scans().replace("/scans", "");
        api.get(project + "/specifications/" + s.spec() + "/contract-tests", s.token()).expect(502);
    }
}
