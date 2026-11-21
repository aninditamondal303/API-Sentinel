package dev.apisentinel.scan;

import dev.apisentinel.common.Severity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.util.UUID;

/** One finding exactly as the analyzer reported it, stored as rows for filtering and statistics. */
@Entity
@Table(name = "findings")
public class Finding {

    @Id
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "scan_id", nullable = false)
    private Scan scan;

    @Column(nullable = false)
    private int position;

    @Column(name = "rule_id", nullable = false, length = 32)
    private String ruleId;

    @Column(nullable = false, length = 200)
    private String title;

    @Column(nullable = false, length = 32)
    private String category;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 16)
    private Severity severity;

    @Column(name = "requires_manual_review", nullable = false)
    private boolean requiresManualReview;

    @Column(name = "http_method", length = 16)
    private String httpMethod;

    @Column(length = 1000)
    private String path;

    @Column(nullable = false, length = 2000)
    private String location;

    @Column(name = "location_document", nullable = false, length = 16)
    private String locationDocument;

    @Column(name = "field_path", length = 1000)
    private String fieldPath;

    /** JSON text of the old value (may be a scalar, list or object). */
    @Column(name = "old_value", columnDefinition = "text")
    private String oldValue;

    @Column(name = "new_value", columnDefinition = "text")
    private String newValue;

    @Column(nullable = false, columnDefinition = "text")
    private String message;

    @Column(nullable = false, columnDefinition = "text")
    private String impact;

    @Column(nullable = false, columnDefinition = "text")
    private String remediation;

    @Column(nullable = false, length = 16)
    private String fingerprint;

    protected Finding() {
    }

    public Finding(Scan scan, int position, String ruleId, String title, String category, Severity severity,
            boolean requiresManualReview, String httpMethod, String path, String location, String locationDocument,
            String fieldPath, String oldValue, String newValue, String message, String impact, String remediation,
            String fingerprint) {
        this.id = UUID.randomUUID();
        this.scan = scan;
        this.position = position;
        this.ruleId = ruleId;
        this.title = title;
        this.category = category;
        this.severity = severity;
        this.requiresManualReview = requiresManualReview;
        this.httpMethod = httpMethod;
        this.path = path;
        this.location = location;
        this.locationDocument = locationDocument;
        this.fieldPath = fieldPath;
        this.oldValue = oldValue;
        this.newValue = newValue;
        this.message = message;
        this.impact = impact;
        this.remediation = remediation;
        this.fingerprint = fingerprint;
    }

    public UUID getId() {
        return id;
    }

    public int getPosition() {
        return position;
    }

    public String getRuleId() {
        return ruleId;
    }

    public String getTitle() {
        return title;
    }

    public String getCategory() {
        return category;
    }

    public Severity getSeverity() {
        return severity;
    }

    public boolean isRequiresManualReview() {
        return requiresManualReview;
    }

    public String getHttpMethod() {
        return httpMethod;
    }

    public String getPath() {
        return path;
    }

    public String getLocation() {
        return location;
    }

    public String getLocationDocument() {
        return locationDocument;
    }

    public String getFieldPath() {
        return fieldPath;
    }

    public String getOldValue() {
        return oldValue;
    }

    public String getNewValue() {
        return newValue;
    }

    public String getMessage() {
        return message;
    }

    public String getImpact() {
        return impact;
    }

    public String getRemediation() {
        return remediation;
    }

    public String getFingerprint() {
        return fingerprint;
    }
}
