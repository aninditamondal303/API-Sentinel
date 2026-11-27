package dev.apisentinel.analyzer;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.util.List;
import java.util.Map;

/**
 * Request and response shapes of the analyzer's internal API, mirroring
 * contracts/analyzer-api.openapi.json. Unknown fields are ignored so the analyzer can add fields
 * without breaking the backend.
 */
public final class AnalyzerDtos {

    private AnalyzerDtos() {
    }

    // ------------------------------------------------------------------ requests
    public record SpecPayload(String content, String filename) {
    }

    public record SpecRequest(SpecPayload spec) {
    }

    public record AnalysisOptions(String failOn, boolean failOnManualReview) {
    }

    public record AnalysisRequest(SpecPayload baseline, SpecPayload candidate, AnalysisOptions options) {
    }

    public record ScanOptions(String failOn) {
    }

    public record SecurityScanRequest(SpecPayload spec, ScanOptions options) {
    }

    public record ContractTestOptions(boolean includeUnsafeMethods, String baseUrl) {
    }

    public record ContractTestRequest(SpecPayload spec, ContractTestOptions options) {
    }

    // ----------------------------------------------------------------- responses
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Issue(String pointer, String message) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record ErrorBody(String code, String message, List<Issue> issues) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record SpecSummary(String openapiVersion, String title, String apiVersion, int operationCount,
            String sha256) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record ValidationResult(boolean valid, SpecSummary spec, ErrorBody error) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record AnalyzerInfo(String version, String rulesetVersion) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Decision(String result, List<String> reasons, String failOn, Boolean failOnManualReview) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Summary(int total, Map<String, Integer> bySeverity, Map<String, Integer> byCategory,
            Integer breakingChanges, Integer manualReview, int endpointsAffected) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Finding(String ruleId, String title, String category, String severity,
            boolean requiresManualReview, String method, String path, String location, String locationDocument,
            String field, Object oldValue, Object newValue, String message, String impact, String remediation,
            String fingerprint) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record AnalysisResult(String schemaVersion, AnalyzerInfo analyzer, SpecSummary baseline,
            SpecSummary candidate, Decision decision, Summary summary, List<Finding> findings) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record SecurityScanResult(String schemaVersion, AnalyzerInfo analyzer, SpecSummary spec,
            Decision decision, Summary summary, List<Finding> findings, String disclaimer) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record GeneratedFile(String path, String content) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record GeneratedOperation(String id, String method, String path, String operationId, String status,
            String skipReason, List<String> expectedStatuses, Map<String, String> inputSources, List<String> notes,
            boolean requiresAuth) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record ContractTestSummary(int total, int ready, int skipped, int schemaValidated) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record ContractTestResult(SpecSummary spec, ContractTestSummary summary,
            List<GeneratedOperation> operations, List<GeneratedFile> files, String runCommand) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record RuleInfo(String id, String title, String category, String severity, boolean requiresManualReview,
            String impact, String remediation) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record RulesResult(String rulesetVersion, List<RuleInfo> rules) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Problem(String title, Integer status, String detail, String errorCode, String side,
            List<Issue> errors) {
    }
}
