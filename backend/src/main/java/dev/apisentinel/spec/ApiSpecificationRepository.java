package dev.apisentinel.spec;

import java.util.Optional;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ApiSpecificationRepository extends JpaRepository<ApiSpecification, UUID> {

    Optional<ApiSpecification> findByIdAndProjectId(UUID id, UUID projectId);

    Page<ApiSpecification> findByProjectId(UUID projectId, Pageable pageable);

    boolean existsByProjectIdAndVersionLabelIgnoreCase(UUID projectId, String versionLabel);

    Optional<ApiSpecification> findFirstByProjectIdAndSha256(UUID projectId, String sha256);

    long countByProjectOwnerId(UUID ownerId);
}
