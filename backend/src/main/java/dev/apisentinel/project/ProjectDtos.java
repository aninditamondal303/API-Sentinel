package dev.apisentinel.project;

import dev.apisentinel.common.Severity;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.util.UUID;

public final class ProjectDtos {

    private ProjectDtos() {
    }

    public record ProjectRequest(
            @NotBlank @Size(min = 3, max = 100) String name,
            @Size(max = 1000) String description) {
    }

    /** {@code failOn: null} disables the severity threshold. */
    public record PolicyRequest(Severity failOn, boolean failOnManualReview) {
    }

    public record PolicyResponse(Severity failOn, boolean failOnManualReview) {
        static PolicyResponse from(CompatibilityPolicy policy) {
            return new PolicyResponse(policy.getFailOn(), policy.isFailOnManualReview());
        }
    }

    public record ProjectResponse(UUID id, String name, String description, PolicyResponse policy,
            Instant createdAt, Instant updatedAt) {
        public static ProjectResponse from(Project p) {
            return new ProjectResponse(p.getId(), p.getName(), p.getDescription(),
                    PolicyResponse.from(p.getPolicy()), p.getCreatedAt(), p.getUpdatedAt());
        }
    }
}
