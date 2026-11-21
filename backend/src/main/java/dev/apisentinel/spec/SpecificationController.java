package dev.apisentinel.spec;

import dev.apisentinel.auth.CurrentUser;
import dev.apisentinel.common.Locations;
import dev.apisentinel.common.PageResponse;
import dev.apisentinel.spec.SpecificationDtos.SpecificationFile;
import dev.apisentinel.spec.SpecificationDtos.SpecificationResponse;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

@Tag(name = "Specifications")
@RestController
@RequestMapping("/api/v1/projects/{projectId}/specifications")
public class SpecificationController {

    private final SpecificationService specificationService;

    public SpecificationController(SpecificationService specificationService) {
        this.specificationService = specificationService;
    }

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<SpecificationResponse> upload(@AuthenticationPrincipal Jwt jwt,
            @PathVariable UUID projectId, @RequestPart("file") MultipartFile file,
            @RequestParam("versionLabel") String versionLabel) throws IOException {
        SpecificationResponse created = specificationService.upload(CurrentUser.id(jwt), projectId, versionLabel,
                file.getOriginalFilename(), file.getBytes());
        return ResponseEntity.created(Locations.of("/api/v1/projects/{projectId}/specifications/{specId}",
                projectId, created.id())).body(created);
    }

    @GetMapping
    public PageResponse<SpecificationResponse> list(@AuthenticationPrincipal Jwt jwt, @PathVariable UUID projectId,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size) {
        return specificationService.list(CurrentUser.id(jwt), projectId, page, size);
    }

    @GetMapping("/{specId}")
    public SpecificationResponse get(@AuthenticationPrincipal Jwt jwt, @PathVariable UUID projectId,
            @PathVariable UUID specId) {
        return specificationService.get(CurrentUser.id(jwt), projectId, specId);
    }

    @GetMapping("/{specId}/content")
    public ResponseEntity<byte[]> download(@AuthenticationPrincipal Jwt jwt, @PathVariable UUID projectId,
            @PathVariable UUID specId) {
        SpecificationFile file = specificationService.file(CurrentUser.id(jwt), projectId, specId);
        MediaType type = file.format() == ApiSpecification.Format.JSON
                ? MediaType.APPLICATION_JSON : MediaType.parseMediaType("application/yaml");
        return ResponseEntity.ok()
                .contentType(type)
                .header(HttpHeaders.CONTENT_DISPOSITION,
                        ContentDisposition.attachment().filename(file.filename()).build().toString())
                .header("X-Content-Type-Options", "nosniff")
                .body(file.content().getBytes(StandardCharsets.UTF_8));
    }

    @DeleteMapping("/{specId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@AuthenticationPrincipal Jwt jwt, @PathVariable UUID projectId, @PathVariable UUID specId) {
        specificationService.delete(CurrentUser.id(jwt), projectId, specId);
    }
}
