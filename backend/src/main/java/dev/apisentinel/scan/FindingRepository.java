package dev.apisentinel.scan;

import dev.apisentinel.common.Severity;
import java.util.List;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface FindingRepository extends JpaRepository<Finding, UUID> {

    @Query("""
            select f from Finding f
            where f.scan.id = :scanId
              and (:severity is null or f.severity = :severity)
              and (:category is null or f.category = :category)
              and (:path is null or f.path = :path)
            """)
    Page<Finding> search(@Param("scanId") UUID scanId, @Param("severity") Severity severity,
            @Param("category") String category, @Param("path") String path, Pageable pageable);

    List<Finding> findByScanIdOrderByPositionAsc(UUID scanId);

    long countByScanId(UUID scanId);

    /** Severity distribution across all completed scans of one user's projects. */
    @Query("""
            select f.severity, count(f) from Finding f
            where f.scan.project.owner.id = :ownerId and f.scan.status = dev.apisentinel.scan.ScanStatus.COMPLETED
            group by f.severity
            """)
    List<Object[]> countBySeverityForOwner(@Param("ownerId") UUID ownerId);
}
