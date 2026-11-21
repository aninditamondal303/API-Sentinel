package dev.apisentinel.scan;

import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface ScanRepository extends JpaRepository<Scan, UUID> {

    Optional<Scan> findByIdAndProjectId(UUID id, UUID projectId);

    @Query("""
            select s from Scan s
            where s.project.id = :projectId
              and (:type is null or s.type = :type)
              and (:status is null or s.status = :status)
            """)
    Page<Scan> search(@Param("projectId") UUID projectId, @Param("type") ScanType type,
            @Param("status") ScanStatus status, Pageable pageable);

    boolean existsByBaselineSpecificationIdOrTargetSpecificationId(UUID baselineId, UUID targetId);

    long countByProjectOwnerId(UUID ownerId);

    long countByProjectOwnerIdAndType(UUID ownerId, ScanType type);

    long countByProjectOwnerIdAndStatus(UUID ownerId, ScanStatus status);

    long countByProjectOwnerIdAndDecision(UUID ownerId, Decision decision);

    /**
     * Sum of the analyzer-reported {@code summary.breakingChanges} over the owner's completed compatibility
     * scans. The definition of "breaking" stays in the analyzer; Java only adds up persisted values.
     */
    @Query("""
            select coalesce(sum(s.breakingChanges), 0) from Scan s
            where s.project.owner.id = :ownerId
              and s.type = dev.apisentinel.scan.ScanType.COMPATIBILITY
              and s.status = dev.apisentinel.scan.ScanStatus.COMPLETED
            """)
    long sumBreakingChangesForOwner(@Param("ownerId") UUID ownerId);

    List<Scan> findTop10ByProjectOwnerIdOrderByCreatedAtDesc(UUID ownerId);
}
