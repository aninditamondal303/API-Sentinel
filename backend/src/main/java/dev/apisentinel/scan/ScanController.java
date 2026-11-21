package dev.apisentinel.scan;

import dev.apisentinel.auth.CurrentUser;
import dev.apisentinel.common.Locations;
import dev.apisentinel.common.PageResponse;
import dev.apisentinel.common.Severity;
import dev.apisentinel.scan.ScanDtos.CompatibilityScanRequest;
import dev.apisentinel.scan.ScanDtos.FindingResponse;
import dev.apisentinel.scan.ScanDtos.ScanReport;
import dev.apisentinel.scan.ScanDtos.ScanResponse;
import dev.apisentinel.scan.ScanDtos.SecurityScanRequest;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.util.UUID;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "Scans")
@RestController
@RequestMapping("/api/v1/projects/{projectId}/scans")
public class ScanController {

    private final ScanService scanService;

    public ScanController(ScanService scanService) {
        this.scanService = scanService;
    }

    @PostMapping("/compatibility")
    public ResponseEntity<ScanResponse> compatibility(@AuthenticationPrincipal Jwt jwt, @PathVariable UUID projectId,
            @Valid @RequestBody CompatibilityScanRequest request) {
        return created(scanService.createCompatibilityScan(CurrentUser.id(jwt), projectId, request));
    }

    @PostMapping("/security")
    public ResponseEntity<ScanResponse> security(@AuthenticationPrincipal Jwt jwt, @PathVariable UUID projectId,
            @Valid @RequestBody SecurityScanRequest request) {
        return created(scanService.createSecurityScan(CurrentUser.id(jwt), projectId, request));
    }

    private static ResponseEntity<ScanResponse> created(ScanResponse scan) {
        return ResponseEntity.created(Locations.of("/api/v1/projects/{projectId}/scans/{scanId}", scan.projectId(),
                scan.id())).body(scan);
    }

    @GetMapping
    public PageResponse<ScanResponse> list(@AuthenticationPrincipal Jwt jwt, @PathVariable UUID projectId,
            @RequestParam(required = false) ScanType type, @RequestParam(required = false) ScanStatus status,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size) {
        return scanService.list(CurrentUser.id(jwt), projectId, type, status, page, size);
    }

    @GetMapping("/{scanId}")
    public ScanResponse get(@AuthenticationPrincipal Jwt jwt, @PathVariable UUID projectId,
            @PathVariable UUID scanId) {
        return scanService.get(CurrentUser.id(jwt), projectId, scanId);
    }

    @GetMapping("/{scanId}/findings")
    public PageResponse<FindingResponse> findings(@AuthenticationPrincipal Jwt jwt, @PathVariable UUID projectId,
            @PathVariable UUID scanId, @RequestParam(required = false) Severity severity,
            @RequestParam(required = false) String category, @RequestParam(required = false) String path,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "50") @Min(1) @Max(200) int size) {
        return scanService.findings(CurrentUser.id(jwt), projectId, scanId, severity, category, path, page, size);
    }

    @GetMapping("/{scanId}/report")
    public ResponseEntity<ScanReport> report(@AuthenticationPrincipal Jwt jwt, @PathVariable UUID projectId,
            @PathVariable UUID scanId) {
        ScanReport report = scanService.report(CurrentUser.id(jwt), projectId, scanId);
        return ResponseEntity.ok()
                .contentType(MediaType.APPLICATION_JSON)
                .header(HttpHeaders.CONTENT_DISPOSITION,
                        ContentDisposition.attachment().filename("scan-" + scanId + ".json").build().toString())
                .body(report);
    }
}
