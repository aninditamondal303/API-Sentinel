package dev.apisentinel.spec;

import dev.apisentinel.project.Project;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

/** Metadata of one uploaded specification version. The document itself is in {@link SpecificationContent}. */
@Entity
@Table(name = "api_specifications")
public class ApiSpecification {

    public enum Format { YAML, JSON }

    @Id
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "project_id", nullable = false)
    private Project project;

    @Column(name = "version_label", nullable = false, length = 50)
    private String versionLabel;

    @Column(name = "original_filename", nullable = false, length = 255)
    private String originalFilename;

    @Enumerated(EnumType.STRING)
    @Column(name = "source_format", nullable = false, length = 8)
    private Format format;

    @Column(name = "openapi_version", nullable = false, length = 16)
    private String openapiVersion;

    @Column(length = 255)
    private String title;

    @Column(name = "api_version", length = 100)
    private String apiVersion;

    @Column(name = "operation_count", nullable = false)
    private int operationCount;

    @Column(name = "size_bytes", nullable = false)
    private int sizeBytes;

    @Column(nullable = false, length = 64)
    private String sha256;

    @Column(name = "uploaded_by", nullable = false)
    private UUID uploadedBy;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    protected ApiSpecification() {
    }

    public ApiSpecification(Project project, String versionLabel, String originalFilename, Format format,
            String openapiVersion, String title, String apiVersion, int operationCount, int sizeBytes,
            String sha256, UUID uploadedBy) {
        this.id = UUID.randomUUID();
        this.project = project;
        this.versionLabel = versionLabel;
        this.originalFilename = originalFilename;
        this.format = format;
        this.openapiVersion = openapiVersion;
        this.title = title;
        this.apiVersion = apiVersion;
        this.operationCount = operationCount;
        this.sizeBytes = sizeBytes;
        this.sha256 = sha256;
        this.uploadedBy = uploadedBy;
        this.createdAt = Instant.now();
    }

    public UUID getId() {
        return id;
    }

    public Project getProject() {
        return project;
    }

    public String getVersionLabel() {
        return versionLabel;
    }

    public String getOriginalFilename() {
        return originalFilename;
    }

    public Format getFormat() {
        return format;
    }

    public String getOpenapiVersion() {
        return openapiVersion;
    }

    public String getTitle() {
        return title;
    }

    public String getApiVersion() {
        return apiVersion;
    }

    public int getOperationCount() {
        return operationCount;
    }

    public int getSizeBytes() {
        return sizeBytes;
    }

    public String getSha256() {
        return sha256;
    }

    public UUID getUploadedBy() {
        return uploadedBy;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
