package dev.apisentinel.spec;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.util.UUID;

/**
 * The uploaded document, stored once and separately from its metadata so that listings never
 * load it. Scans reference specifications by ID instead of copying their content.
 */
@Entity
@Table(name = "specification_contents")
public class SpecificationContent {

    @Id
    @Column(name = "specification_id")
    private UUID specificationId;

    @Column(nullable = false, columnDefinition = "text")
    private String content;

    protected SpecificationContent() {
    }

    public SpecificationContent(UUID specificationId, String content) {
        this.specificationId = specificationId;
        this.content = content;
    }

    public UUID getSpecificationId() {
        return specificationId;
    }

    public String getContent() {
        return content;
    }
}
