package dev.apisentinel.scan;

import dev.apisentinel.analyzer.AnalyzerClient;
import dev.apisentinel.analyzer.AnalyzerDtos;
import dev.apisentinel.analyzer.AnalyzerDtos.AnalysisResult;
import dev.apisentinel.analyzer.AnalyzerDtos.SecurityScanResult;
import dev.apisentinel.analyzer.AnalyzerDtos.SpecPayload;
import dev.apisentinel.analyzer.AnalyzerException;
import dev.apisentinel.common.ApiException;
import dev.apisentinel.common.PageResponse;
import dev.apisentinel.common.Severity;
import dev.apisentinel.project.CompatibilityPolicy;
import dev.apisentinel.project.Project;
import dev.apisentinel.project.ProjectService;
import dev.apisentinel.scan.ScanDtos.CompatibilityScanRequest;
import dev.apisentinel.scan.ScanDtos.FindingResponse;
import dev.apisentinel.scan.ScanDtos.ScanReport;
import dev.apisentinel.scan.ScanDtos.ScanResponse;
import dev.apisentinel.scan.ScanDtos.SecurityScanRequest;
import dev.apisentinel.spec.ApiSpecification;
import dev.apisentinel.spec.SpecificationService;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionTemplate;
import tools.jackson.databind.json.JsonMapper;

/**
 * Orchestrates scans. The analyzer call happens outside any database transaction: the scan row is
 * committed as RUNNING first, then updated to COMPLETED (with findings) or FAILED, so failures and
 * timeouts are always visible in the scan history.
 */
@Service
public class ScanService {

    private static final Logger log = LoggerFactory.getLogger(ScanService.class);

    private final ScanRepository scans;
    private final FindingRepository findings;
    private final ProjectService projectService;
    private final SpecificationService specificationService;
    private final AnalyzerClient analyzer;
    private final TransactionTemplate tx;
    private final JsonMapper jsonMapper;

    public ScanService(ScanRepository scans, FindingRepository findings, ProjectService projectService,
            SpecificationService specificationService, AnalyzerClient analyzer,
            PlatformTransactionManager transactionManager, JsonMapper jsonMapper) {
        this.scans = scans;
        this.findings = findings;
        this.projectService = projectService;
        this.specificationService = specificationService;
        this.analyzer = analyzer;
        this.tx = new TransactionTemplate(transactionManager);
        this.jsonMapper = jsonMapper;
    }

    public ScanResponse createCompatibilityScan(UUID userId, UUID projectId, CompatibilityScanRequest request) {
        if (request.baselineSpecificationId().equals(request.candidateSpecificationId())) {
            throw ApiException.badRequest("SAME_SPECIFICATION",
                    "Baseline and candidate must be different specification versions.");
        }
        record Prepared(UUID scanId, SpecPayload baseline, SpecPayload candidate, Severity failOn, boolean manual) {
        }
        Prepared prepared = tx.execute(status -> {
            Project project = projectService.requireOwned(projectId, userId);
            ApiSpecification baseline = specificationService.requireSpec(userId, projectId,
                    request.baselineSpecificationId());
            ApiSpecification candidate = specificationService.requireSpec(userId, projectId,
                    request.candidateSpecificationId());
            CompatibilityPolicy policy = project.getPolicy();
            boolean usePolicy = request.useProjectPolicy() == null || request.useProjectPolicy();
            Severity failOn = usePolicy ? policy.getFailOn() : request.failOn();
            boolean manual = usePolicy ? policy.isFailOnManualReview()
                    : request.failOnManualReview() == null || request.failOnManualReview();
            Scan scan = scans.save(Scan.compatibility(project, baseline, candidate, failOn, manual, userId));
            return new Prepared(scan.getId(), specificationService.payload(baseline),
                    specificationService.payload(candidate), failOn, manual);
        });

        AnalysisResult result;
        try {
            result = analyzer.analyze(prepared.baseline(), prepared.candidate(), prepared.failOn(), prepared.manual());
        } catch (AnalyzerException e) {
            markFailed(prepared.scanId(), e);
            throw e.withScanId(prepared.scanId());
        }
        return tx.execute(status -> {
            Scan scan = scans.findById(prepared.scanId()).orElseThrow();
            saveFindings(scan, result.findings());
            var summary = result.summary();
            scan.complete(parseDecision(result.decision()), joinReasons(result.decision()), summary.bySeverity(),
                    summary.total(), orZero(summary.breakingChanges()), orZero(summary.manualReview()),
                    summary.endpointsAffected(), result.analyzer().version(), result.analyzer().rulesetVersion());
            return ScanResponse.from(scan);
        });
    }

    public ScanResponse createSecurityScan(UUID userId, UUID projectId, SecurityScanRequest request) {
        record Prepared(UUID scanId, SpecPayload spec, Severity failOn) {
        }
        Prepared prepared = tx.execute(status -> {
            Project project = projectService.requireOwned(projectId, userId);
            ApiSpecification spec = specificationService.requireSpec(userId, projectId, request.specificationId());
            boolean usePolicy = request.useProjectPolicy() == null || request.useProjectPolicy();
            Severity failOn = usePolicy ? project.getPolicy().getFailOn() : request.failOn();
            Scan scan = scans.save(Scan.security(project, spec, failOn, userId));
            return new Prepared(scan.getId(), specificationService.payload(spec), failOn);
        });

        SecurityScanResult result;
        try {
            result = analyzer.securityScan(prepared.spec(), prepared.failOn());
        } catch (AnalyzerException e) {
            markFailed(prepared.scanId(), e);
            throw e.withScanId(prepared.scanId());
        }
        return tx.execute(status -> {
            Scan scan = scans.findById(prepared.scanId()).orElseThrow();
            saveFindings(scan, result.findings());
            var summary = result.summary();
            scan.complete(parseDecision(result.decision()), joinReasons(result.decision()), summary.bySeverity(),
                    summary.total(), 0, 0, summary.endpointsAffected(), result.analyzer().version(),
                    result.analyzer().rulesetVersion());
            return ScanResponse.from(scan);
        });
    }

    @Transactional(readOnly = true)
    public PageResponse<ScanResponse> list(UUID userId, UUID projectId, ScanType type, ScanStatus status, int page,
            int size) {
        projectService.requireOwned(projectId, userId);
        var pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "createdAt"));
        return PageResponse.of(scans.search(projectId, type, status, pageable), ScanResponse::from);
    }

    @Transactional(readOnly = true)
    public ScanResponse get(UUID userId, UUID projectId, UUID scanId) {
        return ScanResponse.from(requireScan(userId, projectId, scanId));
    }

    @Transactional(readOnly = true)
    public PageResponse<FindingResponse> findings(UUID userId, UUID projectId, UUID scanId, Severity severity,
            String category, String path, int page, int size) {
        requireScan(userId, projectId, scanId);
        var pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.ASC, "position"));
        String normalizedCategory = category == null || category.isBlank() ? null
                : category.trim().toUpperCase(Locale.ROOT);
        String normalizedPath = path == null || path.isBlank() ? null : path.trim();
        return PageResponse.of(findings.search(scanId, severity, normalizedCategory, normalizedPath, pageable),
                this::toResponse);
    }

    @Transactional(readOnly = true)
    public ScanReport report(UUID userId, UUID projectId, UUID scanId) {
        Scan scan = requireScan(userId, projectId, scanId);
        List<FindingResponse> all = findings.findByScanIdOrderByPositionAsc(scanId).stream()
                .map(this::toResponse).toList();
        Map<String, String> notes = scan.getType() == ScanType.SECURITY
                ? Map.of("disclaimer", "Static specification checks only. API Sentinel reads what the specification "
                        + "declares; it is not a penetration test and does not detect runtime vulnerabilities.")
                : Map.of();
        return new ScanReport("api-sentinel-scan-report/v1", ScanResponse.from(scan), all, notes);
    }

    private Scan requireScan(UUID userId, UUID projectId, UUID scanId) {
        projectService.requireOwned(projectId, userId);
        return scans.findByIdAndProjectId(scanId, projectId).orElseThrow(() -> ApiException.notFound("Scan"));
    }

    private void markFailed(UUID scanId, AnalyzerException e) {
        log.warn("Scan {} failed: {} ({})", scanId, e.getCode(), e.getInternalReason());
        tx.executeWithoutResult(status -> scans.findById(scanId).ifPresent(scan -> scan.fail(e.getCode(),
                e.getMessage())));
    }

    private void saveFindings(Scan scan, List<AnalyzerDtos.Finding> reported) {
        List<Finding> rows = new ArrayList<>(reported.size());
        for (int i = 0; i < reported.size(); i++) {
            AnalyzerDtos.Finding f = reported.get(i);
            rows.add(new Finding(scan, i, f.ruleId(), f.title(), f.category(), Severity.valueOf(f.severity()),
                    f.requiresManualReview(), f.method(), f.path(), f.location(), f.locationDocument(), f.field(),
                    toJson(f.oldValue()), toJson(f.newValue()), f.message(), f.impact(), f.remediation(),
                    f.fingerprint()));
        }
        findings.saveAll(rows);
    }

    private FindingResponse toResponse(Finding f) {
        return new FindingResponse(f.getId(), f.getPosition(), f.getRuleId(), f.getTitle(), f.getCategory(),
                f.getSeverity(), f.isRequiresManualReview(), f.getHttpMethod(), f.getPath(), f.getLocation(),
                f.getLocationDocument(), f.getFieldPath(), fromJson(f.getOldValue()), fromJson(f.getNewValue()),
                f.getMessage(), f.getImpact(), f.getRemediation(), f.getFingerprint());
    }

    private String toJson(Object value) {
        return value == null ? null : jsonMapper.writeValueAsString(value);
    }

    private Object fromJson(String json) {
        return json == null ? null : jsonMapper.readValue(json, Object.class);
    }

    private static Decision parseDecision(AnalyzerDtos.Decision decision) {
        return "FAIL".equals(decision.result()) ? Decision.FAIL : Decision.PASS;
    }

    private static String joinReasons(AnalyzerDtos.Decision decision) {
        return decision.reasons() == null ? null : String.join("\n", decision.reasons());
    }

    private static int orZero(Integer value) {
        return value == null ? 0 : value;
    }
}
