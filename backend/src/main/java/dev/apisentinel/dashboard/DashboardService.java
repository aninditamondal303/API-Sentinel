package dev.apisentinel.dashboard;

import dev.apisentinel.common.Severity;
import dev.apisentinel.project.ProjectRepository;
import dev.apisentinel.scan.Decision;
import dev.apisentinel.scan.FindingRepository;
import dev.apisentinel.scan.ScanDtos.ScanResponse;
import dev.apisentinel.scan.ScanRepository;
import dev.apisentinel.scan.ScanStatus;
import dev.apisentinel.scan.ScanType;
import dev.apisentinel.spec.ApiSpecificationRepository;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Every number here is a database query over the current user's own data. Nothing is cached or estimated. */
@Service
public class DashboardService {

    private final ProjectRepository projects;
    private final ApiSpecificationRepository specifications;
    private final ScanRepository scans;
    private final FindingRepository findings;

    public DashboardService(ProjectRepository projects, ApiSpecificationRepository specifications,
            ScanRepository scans, FindingRepository findings) {
        this.projects = projects;
        this.specifications = specifications;
        this.scans = scans;
        this.findings = findings;
    }

    public record ScanCounts(long total, long compatibility, long security, long completed, long failed,
            long running, long passed, long failedThreshold) {
    }

    public record DashboardResponse(long projects, long specifications, ScanCounts scans, long breakingChanges,
            Map<Severity, Long> severityDistribution, List<ScanResponse> recentScans) {
    }

    @Transactional(readOnly = true)
    public DashboardResponse forUser(UUID userId) {
        ScanCounts scanCounts = new ScanCounts(
                scans.countByProjectOwnerId(userId),
                scans.countByProjectOwnerIdAndType(userId, ScanType.COMPATIBILITY),
                scans.countByProjectOwnerIdAndType(userId, ScanType.SECURITY),
                scans.countByProjectOwnerIdAndStatus(userId, ScanStatus.COMPLETED),
                scans.countByProjectOwnerIdAndStatus(userId, ScanStatus.FAILED),
                scans.countByProjectOwnerIdAndStatus(userId, ScanStatus.RUNNING),
                scans.countByProjectOwnerIdAndDecision(userId, Decision.PASS),
                scans.countByProjectOwnerIdAndDecision(userId, Decision.FAIL));

        Map<Severity, Long> distribution = new LinkedHashMap<>();
        for (Severity severity : List.of(Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW,
                Severity.INFO)) {
            distribution.put(severity, 0L);
        }
        for (Object[] row : findings.countBySeverityForOwner(userId)) {
            distribution.put((Severity) row[0], ((Number) row[1]).longValue());
        }

        List<ScanResponse> recent = scans.findTop10ByProjectOwnerIdOrderByCreatedAtDesc(userId).stream()
                .map(ScanResponse::from).toList();

        return new DashboardResponse(projects.countByOwnerId(userId), specifications.countByProjectOwnerId(userId),
                scanCounts, scans.sumBreakingChangesForOwner(userId), distribution, recent);
    }
}
