package dev.apisentinel.spec;

import java.time.Instant;
import java.util.UUID;

public final class SpecificationDtos {

    private SpecificationDtos() {
    }

    public record SpecificationResponse(UUID id, UUID projectId, String versionLabel, String originalFilename,
            ApiSpecification.Format format, String openapiVersion, String title, String apiVersion,
            int operationCount, int sizeBytes, String sha256, Instant uploadedAt) {

        public static SpecificationResponse from(ApiSpecification s) {
            return new SpecificationResponse(s.getId(), s.getProject().getId(), s.getVersionLabel(),
                    s.getOriginalFilename(), s.getFormat(), s.getOpenapiVersion(), s.getTitle(), s.getApiVersion(),
                    s.getOperationCount(), s.getSizeBytes(), s.getSha256(), s.getCreatedAt());
        }
    }

    public record SpecificationFile(String filename, ApiSpecification.Format format, String content) {
    }
}
