package dev.apisentinel.dashboard;

import static dev.apisentinel.support.TestApi.example;
import static org.assertj.core.api.Assertions.assertThat;

import dev.apisentinel.support.FullStackIntegrationTest;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;

class DashboardIntegrationTest extends FullStackIntegrationTest {

    @Autowired
    JdbcTemplate jdbc;

    @Test
    void emptyDashboardForNewUser() {
        String token = api.register("Fresh");
        var res = api.get("/api/v1/dashboard", token).expect(200);
        assertThat(res.num("projects")).isZero();
        assertThat(res.num("specifications")).isZero();
        assertThat(res.num("scans.total")).isZero();
        assertThat(res.num("breakingChanges")).isZero();
        assertThat((Map<?, ?>) res.path("severityDistribution")).hasSize(5)
                .allSatisfy((k, v) -> assertThat(((Number) v).longValue()).isZero());
        assertThat(res.list("recentScans")).isEmpty();
    }

    @Test
    void dashboardMatchesTheDatabaseAndIgnoresOtherUsers() {
        String token = api.register("Owner");
        String project = api.createProject(token, "Orders");
        String baseline = api.uploadFile(token, project, example("examples/orders-api/baseline.yaml"), "v1");
        String breaking = api.uploadFile(token, project, example("examples/orders-api/candidate-breaking.yaml"),
                "v2");
        String scans = "/api/v1/projects/" + project + "/scans";
        var compat = api.post(scans + "/compatibility",
                Map.of("baselineSpecificationId", baseline, "candidateSpecificationId", breaking), token).expect(201);
        var security = api.post(scans + "/security", Map.of("specificationId", baseline), token).expect(201);

        // Noise from another user must not leak into this dashboard.
        String other = api.register("Other");
        String otherProject = api.createProject(other, "Noise");
        String otherSpec = api.uploadFile(other, otherProject, example("examples/inventory-api/openapi.yaml"), "v1");
        api.post("/api/v1/projects/" + otherProject + "/scans/security", Map.of("specificationId", otherSpec), other)
                .expect(201);

        var dash = api.get("/api/v1/dashboard", token).expect(200);
        assertThat(dash.num("projects")).isEqualTo(1);
        assertThat(dash.num("specifications")).isEqualTo(2);
        assertThat(dash.num("scans.total")).isEqualTo(2);
        assertThat(dash.num("scans.compatibility")).isEqualTo(1);
        assertThat(dash.num("scans.security")).isEqualTo(1);
        assertThat(dash.num("scans.completed")).isEqualTo(2);
        assertThat(dash.num("scans.failed")).isZero();
        assertThat(dash.num("scans.failedThreshold")).isGreaterThanOrEqualTo(1);

        long findingTotal = compat.num("totalFindings") + security.num("totalFindings");
        long distributionTotal = ((Map<?, ?>) dash.path("severityDistribution")).values().stream()
                .mapToLong(v -> ((Number) v).longValue()).sum();
        assertThat(distributionTotal).isEqualTo(findingTotal);

        // Breaking changes are the analyzer's summary.breakingChanges: COMPATIBILITY-category findings of
        // HIGH or CRITICAL severity. Security-regression findings inside a compatibility scan do not count.
        long analyzerBreaking = compat.num("breakingChanges");
        assertThat(analyzerBreaking).isPositive();
        assertThat(dash.num("breakingChanges")).isEqualTo(analyzerBreaking);
        Long persistedSum = jdbc.queryForObject("""
                SELECT COALESCE(SUM(breaking_changes), 0) FROM scans
                WHERE project_id = ?::uuid AND scan_type = 'COMPATIBILITY' AND status = 'COMPLETED'
                """, Long.class, project);
        assertThat(dash.num("breakingChanges")).isEqualTo(persistedSum);
        Long fromFindings = jdbc.queryForObject("""
                SELECT COUNT(*) FROM findings f JOIN scans s ON s.id = f.scan_id
                WHERE s.project_id = ?::uuid AND s.scan_type = 'COMPATIBILITY'
                  AND f.category = 'COMPATIBILITY' AND f.severity IN ('HIGH','CRITICAL')
                """, Long.class, project);
        assertThat(dash.num("breakingChanges")).isEqualTo(fromFindings);
        // Regression guard: this example also yields HIGH+ security-regression findings in the
        // compatibility scan, which must stay excluded from the breaking-change count.
        Long highNonCompat = jdbc.queryForObject("""
                SELECT COUNT(*) FROM findings f JOIN scans s ON s.id = f.scan_id
                WHERE s.id = ?::uuid AND f.category <> 'COMPATIBILITY' AND f.severity IN ('HIGH','CRITICAL')
                """, Long.class, compat.str("id"));
        assertThat(highNonCompat).as("HIGH+ non-compatibility findings in the breaking example").isPositive();

        assertThat(dash.list("recentScans")).extracting(m -> m.get("id"))
                .containsExactly(security.str("id"), compat.str("id"));
    }
}
