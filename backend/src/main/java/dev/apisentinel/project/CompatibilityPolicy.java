package dev.apisentinel.project;

import dev.apisentinel.common.Severity;
import jakarta.persistence.Column;
import jakarta.persistence.Embeddable;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;

/**
 * A project's default pass/fail rule for scans. {@code failOn == null} disables the severity
 * threshold. Scans snapshot these values when they are created.
 */
@Embeddable
public class CompatibilityPolicy {

    @Enumerated(EnumType.STRING)
    @Column(name = "policy_fail_on", length = 16)
    private Severity failOn;

    @Column(name = "policy_fail_on_manual_review", nullable = false)
    private boolean failOnManualReview;

    protected CompatibilityPolicy() {
    }

    public CompatibilityPolicy(Severity failOn, boolean failOnManualReview) {
        this.failOn = failOn;
        this.failOnManualReview = failOnManualReview;
    }

    public static CompatibilityPolicy defaults() {
        return new CompatibilityPolicy(Severity.HIGH, true);
    }

    public Severity getFailOn() {
        return failOn;
    }

    public boolean isFailOnManualReview() {
        return failOnManualReview;
    }
}
