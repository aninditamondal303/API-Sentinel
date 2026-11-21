package dev.apisentinel.contracttest;

import dev.apisentinel.analyzer.AnalyzerDtos.ContractTestResult;
import dev.apisentinel.auth.CurrentUser;
import dev.apisentinel.contracttest.ContractTestService.GeneratedSuite;
import io.swagger.v3.oas.annotations.tags.Tag;
import java.util.UUID;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "Contract tests")
@RestController
@RequestMapping("/api/v1/projects/{projectId}/specifications/{specId}/contract-tests")
public class ContractTestController {

    private final ContractTestService contractTestService;

    public ContractTestController(ContractTestService contractTestService) {
        this.contractTestService = contractTestService;
    }

    /** Preview: which operations are covered or skipped (with reasons) and the generated file contents. */
    @GetMapping
    public ContractTestResult preview(@AuthenticationPrincipal Jwt jwt, @PathVariable UUID projectId,
            @PathVariable UUID specId, @RequestParam(defaultValue = "false") boolean includeUnsafeMethods,
            @RequestParam(required = false) String baseUrl) {
        return contractTestService.generate(CurrentUser.id(jwt), projectId, specId, includeUnsafeMethods, baseUrl)
                .result();
    }

    @GetMapping("/download")
    public ResponseEntity<byte[]> download(@AuthenticationPrincipal Jwt jwt, @PathVariable UUID projectId,
            @PathVariable UUID specId, @RequestParam(defaultValue = "false") boolean includeUnsafeMethods,
            @RequestParam(required = false) String baseUrl) {
        GeneratedSuite suite = contractTestService.generate(CurrentUser.id(jwt), projectId, specId,
                includeUnsafeMethods, baseUrl);
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType("application/zip"))
                .header(HttpHeaders.CONTENT_DISPOSITION,
                        ContentDisposition.attachment().filename(ContractTestService.zipName(suite)).build()
                                .toString())
                .body(contractTestService.zip(suite));
    }
}
