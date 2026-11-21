package dev.apisentinel.scan;

import dev.apisentinel.common.Severity;
import dev.apisentinel.spec.ApiSpecification;
import jakarta.validation.constraints.NotNull;
import java.time.Instant;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public final class ScanDtos {

    private ScanDtos() {
    }

    /**
     * Thresholds are optional: when {@code useProjectPolicy} is true (default) the project's policy
     * is applied; otherwise {@code failOn} (null disables it) and {@code failOnManualReview} are used.
     */
    public record CompatibilityScanRequest(
            @NotNull UUID baselineSpecificationId,
            @NotNull UUID candidateSpecificationId,
            Boolean useProjectPolicy,
            Severity failOn,
            Boolean failOnManualReview) {
    }

    public record SecurityScanRequest(@NotNull UUID specificationId, Boolean useProjectPolicy, Severity failOn) {
    }

    public record SpecRef(UUID id, String versionLabel, String title, String apiVersion) {
        static SpecRef from(ApiSpecification s) {
            return s == null ? null : new SpecRef(s.getId(), s.getVersionLabel(), s.getTitle(), s.getApiVersion());
        }
    }

    public record SeverityCounts(int critical, int high, int medium, int low, int info) {
    }

    public record ScanResponse(UUID id, UUID projectId, ScanType type, ScanStatus status, SpecRef baseline,
            SpecRef target, Severity failOn, boolean failOnManualReview, Decision decision, List<String> reasons,
            int totalFindings, SeverityCounts bySeverity, int breakingChanges, int manualReview,
            int endpointsAffected, String analyzerVersion, String rulesetVersion, String errorCode,
            String errorMessage, Long durationMs, Instant createdAt, Instant completedAt) {

        public static ScanResponse from(Scan s) {
            List<String> reasons = s.getDecisionReasons() == null || s.getDecisionReasons().isBlank()
                    ? List.of() : Arrays.asList(s.getDecisionReasons().split("\n"));
            return new ScanResponse(s.getId(), s.getProject().getId(), s.getType(), s.getStatus(),
                    SpecRef.from(s.getBaselineSpecification()), SpecRef.from(s.getTargetSpecification()),
                    s.getFailOn(), s.isFailOnManualReview(), s.getDecision(), reasons, s.getTotalFindings(),
                    new SeverityCounts(s.getCriticalCount(), s.getHighCount(), s.getMediumCount(), s.getLowCount(),
                            s.getInfoCount()),
                    s.getBreakingChanges(), s.getManualReviewCount(), s.getEndpointsAffected(),
                    s.getAnalyzerVersion(), s.getRulesetVersion(), s.getErrorCode(), s.getErrorMessage(),
                    s.getDurationMs(), s.getCreatedAt(), s.getCompletedAt());
        }
    }

    public record FindingResponse(UUID id, int position, String ruleId, String title, String category,
            Severity severity, boolean requiresManualReview, String method, String path, String location,
            String locationDocument, String field, Object oldValue, Object newValue, String message, String impact,
            String remediation, String fingerprint) {
    }

    /** Downloadable JSON report: the scan plus every finding, in the analyzer's order. */
    public record ScanReport(String reportType, ScanResponse scan, List<FindingResponse> findings,
            Map<String, String> notes) {
    }
}
