package dev.apisentinel.scan;

import dev.apisentinel.common.Severity;
import dev.apisentinel.project.Project;
import dev.apisentinel.spec.ApiSpecification;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.time.Duration;
import java.time.Instant;
import java.util.UUID;

/**
 * One analysis run. It records the exact thresholds it was judged with, so changing the project
 * policy later never changes the meaning of an old result.
 */
@Entity
@Table(name = "scans")
public class Scan {

    @Id
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "project_id", nullable = false)
    private Project project;

    @Enumerated(EnumType.STRING)
    @Column(name = "scan_type", nullable = false, length = 16)
    private ScanType type;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 16)
    private ScanStatus status;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "baseline_specification_id")
    private ApiSpecification baselineSpecification;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "target_specification_id", nullable = false)
    private ApiSpecification targetSpecification;

    @Enumerated(EnumType.STRING)
    @Column(name = "fail_on", length = 16)
    private Severity failOn;

    @Column(name = "fail_on_manual_review", nullable = false)
    private boolean failOnManualReview;

    @Enumerated(EnumType.STRING)
    @Column(length = 8)
    private Decision decision;

    @Column(name = "decision_reasons", columnDefinition = "text")
    private String decisionReasons;

    @Column(name = "total_findings", nullable = false)
    private int totalFindings;

    @Column(name = "critical_count", nullable = false)
    private int criticalCount;

    @Column(name = "high_count", nullable = false)
    private int highCount;

    @Column(name = "medium_count", nullable = false)
    private int mediumCount;

    @Column(name = "low_count", nullable = false)
    private int lowCount;

    @Column(name = "info_count", nullable = false)
    private int infoCount;

    @Column(name = "breaking_changes", nullable = false)
    private int breakingChanges;

    @Column(name = "manual_review_count", nullable = false)
    private int manualReviewCount;

    @Column(name = "endpoints_affected", nullable = false)
    private int endpointsAffected;

    @Column(name = "analyzer_version", length = 32)
    private String analyzerVersion;

    @Column(name = "ruleset_version", length = 32)
    private String rulesetVersion;

    @Column(name = "error_code", length = 64)
    private String errorCode;

    @Column(name = "error_message", length = 500)
    private String errorMessage;

    @Column(name = "duration_ms")
    private Long durationMs;

    @Column(name = "created_by", nullable = false)
    private UUID createdBy;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "completed_at")
    private Instant completedAt;

    protected Scan() {
    }

    private Scan(Project project, ScanType type, ApiSpecification baseline, ApiSpecification target,
            Severity failOn, boolean failOnManualReview, UUID createdBy) {
        this.id = UUID.randomUUID();
        this.project = project;
        this.type = type;
        this.status = ScanStatus.RUNNING;
        this.baselineSpecification = baseline;
        this.targetSpecification = target;
        this.failOn = failOn;
        this.failOnManualReview = failOnManualReview;
        this.createdBy = createdBy;
        this.createdAt = Instant.now();
    }

    public static Scan compatibility(Project project, ApiSpecification baseline, ApiSpecification candidate,
            Severity failOn, boolean failOnManualReview, UUID createdBy) {
        return new Scan(project, ScanType.COMPATIBILITY, baseline, candidate, failOn, failOnManualReview, createdBy);
    }

    public static Scan security(Project project, ApiSpecification spec, Severity failOn, UUID createdBy) {
        return new Scan(project, ScanType.SECURITY, null, spec, failOn, false, createdBy);
    }

    /** Copies the analyzer's own counts and decision; nothing is recomputed here. */
    public void complete(Decision decision, String reasons, java.util.Map<String, Integer> bySeverity, int total,
            int breakingChanges, int manualReview, int endpointsAffected, String analyzerVersion,
            String rulesetVersion) {
        this.status = ScanStatus.COMPLETED;
        this.decision = decision;
        this.decisionReasons = reasons;
        this.totalFindings = total;
        this.criticalCount = bySeverity.getOrDefault("CRITICAL", 0);
        this.highCount = bySeverity.getOrDefault("HIGH", 0);
        this.mediumCount = bySeverity.getOrDefault("MEDIUM", 0);
        this.lowCount = bySeverity.getOrDefault("LOW", 0);
        this.infoCount = bySeverity.getOrDefault("INFO", 0);
        this.breakingChanges = breakingChanges;
        this.manualReviewCount = manualReview;
        this.endpointsAffected = endpointsAffected;
        this.analyzerVersion = analyzerVersion;
        this.rulesetVersion = rulesetVersion;
        finish();
    }

    public void fail(String errorCode, String errorMessage) {
        this.status = ScanStatus.FAILED;
        this.errorCode = errorCode;
        this.errorMessage = errorMessage == null || errorMessage.length() <= 500
                ? errorMessage : errorMessage.substring(0, 500);
        finish();
    }

    private void finish() {
        this.completedAt = Instant.now();
        this.durationMs = Duration.between(createdAt, completedAt).toMillis();
    }

    public UUID getId() {
        return id;
    }

    public Project getProject() {
        return project;
    }

    public ScanType getType() {
        return type;
    }

    public ScanStatus getStatus() {
        return status;
    }

    public ApiSpecification getBaselineSpecification() {
        return baselineSpecification;
    }

    public ApiSpecification getTargetSpecification() {
        return targetSpecification;
    }

    public Severity getFailOn() {
        return failOn;
    }

    public boolean isFailOnManualReview() {
        return failOnManualReview;
    }

    public Decision getDecision() {
        return decision;
    }

    public String getDecisionReasons() {
        return decisionReasons;
    }

    public int getTotalFindings() {
        return totalFindings;
    }

    public int getCriticalCount() {
        return criticalCount;
    }

    public int getHighCount() {
        return highCount;
    }

    public int getMediumCount() {
        return mediumCount;
    }

    public int getLowCount() {
        return lowCount;
    }

    public int getInfoCount() {
        return infoCount;
    }

    public int getBreakingChanges() {
        return breakingChanges;
    }

    public int getManualReviewCount() {
        return manualReviewCount;
    }

    public int getEndpointsAffected() {
        return endpointsAffected;
    }

    public String getAnalyzerVersion() {
        return analyzerVersion;
    }

    public String getRulesetVersion() {
        return rulesetVersion;
    }

    public String getErrorCode() {
        return errorCode;
    }

    public String getErrorMessage() {
        return errorMessage;
    }

    public Long getDurationMs() {
        return durationMs;
    }

    public UUID getCreatedBy() {
        return createdBy;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getCompletedAt() {
        return completedAt;
    }
}
