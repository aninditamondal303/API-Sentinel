package dev.apisentinel.scan;

import static dev.apisentinel.support.TestApi.example;
import static org.assertj.core.api.Assertions.assertThat;

import dev.apisentinel.support.FullStackIntegrationTest;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;

/** Every scan here is a real HTTP round trip from Spring Boot to the Python analyzer container. */
class ScanIntegrationTest extends FullStackIntegrationTest {

    @Autowired
    JdbcTemplate jdbc;

    private record Fixture(String token, String project, String baseline, String breaking, String safe) {
    }

    private Fixture fixture() {
        String token = api.register("Owner");
        String project = api.createProject(token, "Orders");
        return new Fixture(token, project,
                api.uploadFile(token, project, example("examples/orders-api/baseline.yaml"), "v1"),
                api.uploadFile(token, project, example("examples/orders-api/candidate-breaking.yaml"), "v2-breaking"),
                api.uploadFile(token, project, example("examples/orders-api/candidate-safe.yaml"), "v2-safe"));
    }

    private String scans(Fixture f) {
        return "/api/v1/projects/" + f.project() + "/scans";
    }

    @Test
    void breakingCandidateFailsAndFindingsArePersisted() {
        Fixture f = fixture();
        var scan = api.post(scans(f) + "/compatibility",
                Map.of("baselineSpecificationId", f.baseline(), "candidateSpecificationId", f.breaking()), f.token())
                .expect(201);
        String scanId = scan.str("id");
        assertThat(scan.header("Location")).endsWith(scans(f) + "/" + scanId);
        assertThat(scan.str("type")).isEqualTo("COMPATIBILITY");
        assertThat(scan.str("status")).isEqualTo("COMPLETED");
        assertThat(scan.str("decision")).isEqualTo("FAIL");
        assertThat(scan.str("failOn")).isEqualTo("HIGH");
        assertThat(scan.num("breakingChanges")).isPositive();
        assertThat(scan.num("totalFindings")).isPositive();
        assertThat(scan.str("analyzerVersion")).isNotBlank();
        assertThat(scan.str("rulesetVersion")).isNotBlank();
        assertThat(scan.list("reasons")).isNotEmpty();
        assertThat(scan.str("baseline.id")).isEqualTo(f.baseline());
        assertThat(scan.str("target.id")).isEqualTo(f.breaking());

        long total = scan.num("totalFindings");
        Integer rows = jdbc.queryForObject("SELECT COUNT(*) FROM findings WHERE scan_id = ?::uuid", Integer.class,
                scanId);
        assertThat(rows).isEqualTo((int) total);
        Map<String, Object> stored = jdbc.queryForMap(
                "SELECT status, decision, total_findings, completed_at FROM scans WHERE id = ?::uuid", scanId);
        assertThat(stored.get("status")).isEqualTo("COMPLETED");
        assertThat(stored.get("decision")).isEqualTo("FAIL");
        assertThat(stored.get("completed_at")).isNotNull();

        var counts = scan.path("bySeverity");
        long sum = ((Map<?, ?>) counts).values().stream().mapToLong(v -> ((Number) v).longValue()).sum();
        assertThat(sum).isEqualTo(total);

        var findings = api.get(scans(f) + "/" + scanId + "/findings?size=200", f.token()).expect(200);
        assertThat(findings.num("totalItems")).isEqualTo(total);
        List<Map<String, Object>> items = findings.list("items");
        assertThat(items).extracting(m -> m.get("position")).isSorted();
        assertThat(items).allSatisfy(m -> {
            assertThat(m.get("ruleId")).isNotNull();
            assertThat(m.get("severity")).isNotNull();
            assertThat((String) m.get("fingerprint")).hasSize(16);
        });

        // History endpoint returns the persisted scan.
        var history = api.get(scans(f), f.token()).expect(200);
        assertThat(history.list("items")).extracting(m -> m.get("id")).contains(scanId);
        assertThat(api.get(scans(f) + "/" + scanId, f.token()).expect(200).str("decision")).isEqualTo("FAIL");
    }

    @Test
    void findingsCanBeFiltered() {
        Fixture f = fixture();
        String scanId = api.post(scans(f) + "/compatibility",
                Map.of("baselineSpecificationId", f.baseline(), "candidateSpecificationId", f.breaking()), f.token())
                .expect(201).str("id");
        var all = api.get(scans(f) + "/" + scanId + "/findings?size=200", f.token()).expect(200);
        String severity = (String) all.list("items").get(0).get("severity");
        var filtered = api.get(scans(f) + "/" + scanId + "/findings?size=200&severity=" + severity, f.token())
                .expect(200);
        assertThat(filtered.list("items")).isNotEmpty()
                .allSatisfy(m -> assertThat(m.get("severity")).isEqualTo(severity));
        api.get(scans(f) + "/" + scanId + "/findings?severity=SEVERE", f.token()).expect(400);
        api.get(scans(f) + "/" + scanId + "/findings?size=1000", f.token()).expect(400);
    }

    @Test
    void safeCandidateWithThresholdDisabledPasses() {
        Fixture f = fixture();
        Map<String, Object> body = new HashMap<>();
        body.put("baselineSpecificationId", f.baseline());
        body.put("candidateSpecificationId", f.safe());
        body.put("useProjectPolicy", false);
        body.put("failOn", "CRITICAL");
        body.put("failOnManualReview", false);
        var scan = api.post(scans(f) + "/compatibility", body, f.token()).expect(201);
        assertThat(scan.str("status")).isEqualTo("COMPLETED");
        assertThat(scan.str("decision")).isEqualTo("PASS");
        assertThat(scan.num("breakingChanges")).isZero();
        assertThat(scan.str("failOn")).isEqualTo("CRITICAL");
    }

    @Test
    void projectPolicyIsAppliedByDefault() {
        Fixture f = fixture();
        api.put("/api/v1/projects/" + f.project() + "/policy", Map.of("failOn", "CRITICAL",
                "failOnManualReview", false), f.token()).expect(200);
        var scan = api.post(scans(f) + "/compatibility",
                Map.of("baselineSpecificationId", f.baseline(), "candidateSpecificationId", f.safe()), f.token())
                .expect(201);
        assertThat(scan.str("failOn")).isEqualTo("CRITICAL");
        assertThat(scan.path("failOnManualReview")).isEqualTo(false);
    }

    @Test
    void securityScanOfSingleSpec() {
        Fixture f = fixture();
        var scan = api.post(scans(f) + "/security", Map.of("specificationId", f.baseline()), f.token())
                .expect(201);
        assertThat(scan.str("type")).isEqualTo("SECURITY");
        assertThat(scan.header("Location")).endsWith(scans(f) + "/" + scan.str("id"));
        assertThat(scan.str("status")).isEqualTo("COMPLETED");
        assertThat(scan.path("baseline")).isNull();
        assertThat(scan.str("target.id")).isEqualTo(f.baseline());
        assertThat(scan.str("decision")).isIn("PASS", "FAIL");
        long total = scan.num("totalFindings");
        assertThat(api.get(scans(f) + "/" + scan.str("id") + "/findings?size=200", f.token()).expect(200)
                .num("totalItems")).isEqualTo(total);

        var onlySecurity = api.get(scans(f) + "?type=SECURITY", f.token()).expect(200);
        assertThat(onlySecurity.list("items")).allSatisfy(m -> assertThat(m.get("type")).isEqualTo("SECURITY"));
    }

    @Test
    void reportDownloadContainsScanAndFindings() {
        Fixture f = fixture();
        var scan = api.post(scans(f) + "/compatibility",
                Map.of("baselineSpecificationId", f.baseline(), "candidateSpecificationId", f.breaking()), f.token())
                .expect(201);
        var report = api.get(scans(f) + "/" + scan.str("id") + "/report", f.token()).expect(200);
        assertThat(report.header("Content-Disposition")).contains("attachment").contains(".json");
        assertThat(report.str("scan.id")).isEqualTo(scan.str("id"));
        assertThat(report.list("findings")).hasSize((int) scan.num("totalFindings"));
    }

    @Test
    void invalidScanRequests() {
        Fixture f = fixture();
        assertThat(api.post(scans(f) + "/compatibility",
                Map.of("baselineSpecificationId", f.baseline(), "candidateSpecificationId", f.baseline()), f.token())
                .expect(400).str("errorCode")).isEqualTo("SAME_SPECIFICATION");
        api.post(scans(f) + "/compatibility", Map.of("baselineSpecificationId", f.baseline()), f.token())
                .expect(400);
        api.post(scans(f) + "/compatibility", Map.of("baselineSpecificationId", f.baseline(),
                "candidateSpecificationId", UUID.randomUUID().toString()), f.token()).expect(404);
        api.post(scans(f) + "/security", Map.of("specificationId", UUID.randomUUID().toString()), f.token())
                .expect(404);
        api.get(scans(f) + "/" + UUID.randomUUID(), f.token()).expect(404);
    }

    @Test
    void scansAreIsolatedBetweenUsers() {
        Fixture alice = fixture();
        String scanId = api.post(scans(alice) + "/compatibility", Map.of("baselineSpecificationId",
                alice.baseline(), "candidateSpecificationId", alice.breaking()), alice.token()).expect(201).str("id");

        String mallory = api.register("Mallory");
        api.get(scans(alice) + "/" + scanId, mallory).expect(404);
        api.get(scans(alice) + "/" + scanId + "/findings", mallory).expect(404);
        api.get(scans(alice) + "/" + scanId + "/report", mallory).expect(404);
        api.post(scans(alice) + "/compatibility", Map.of("baselineSpecificationId", alice.baseline(),
                "candidateSpecificationId", alice.breaking()), mallory).expect(404);

        // Mallory cannot use Alice's spec ids inside her own project.
        String own = api.createProject(mallory, "Own");
        api.post("/api/v1/projects/" + own + "/scans/security", Map.of("specificationId", alice.baseline()),
                mallory).expect(404);
        // Nor reach Alice's scan through her own project id.
        api.get("/api/v1/projects/" + own + "/scans/" + scanId, mallory).expect(404);
    }

    @Test
    void specificationUsedByAScanCannotBeDeleted() {
        Fixture f = fixture();
        api.post(scans(f) + "/security", Map.of("specificationId", f.safe()), f.token()).expect(201);
        assertThat(api.delete("/api/v1/projects/" + f.project() + "/specifications/" + f.safe(), f.token())
                .expect(409).str("errorCode")).isEqualTo("SPECIFICATION_IN_USE");
    }

    @Test
    void deletingAProjectCascadesToScansAndFindings() {
        Fixture f = fixture();
        String scanId = api.post(scans(f) + "/compatibility",
                Map.of("baselineSpecificationId", f.baseline(), "candidateSpecificationId", f.breaking()), f.token())
                .expect(201).str("id");
        api.delete("/api/v1/projects/" + f.project(), f.token()).expect(204);
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM scans WHERE id = ?::uuid", Integer.class, scanId))
                .isZero();
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM findings WHERE scan_id = ?::uuid", Integer.class,
                scanId)).isZero();
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM api_specifications WHERE project_id = ?::uuid",
                Integer.class, f.project())).isZero();
    }
}
