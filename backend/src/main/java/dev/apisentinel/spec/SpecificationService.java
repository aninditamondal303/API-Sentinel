package dev.apisentinel.spec;

import dev.apisentinel.analyzer.AnalyzerClient;
import dev.apisentinel.analyzer.AnalyzerDtos.SpecPayload;
import dev.apisentinel.analyzer.AnalyzerDtos.ValidationResult;
import dev.apisentinel.common.ApiException;
import dev.apisentinel.common.PageResponse;
import dev.apisentinel.config.UploadProperties;
import dev.apisentinel.project.Project;
import dev.apisentinel.project.ProjectService;
import dev.apisentinel.scan.ScanRepository;
import dev.apisentinel.spec.SpecFileValidator.ValidFile;
import dev.apisentinel.spec.SpecificationDtos.SpecificationFile;
import dev.apisentinel.spec.SpecificationDtos.SpecificationResponse;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.regex.Pattern;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class SpecificationService {

    private static final Pattern VERSION_LABEL = Pattern.compile("^[A-Za-z0-9][A-Za-z0-9._+-]{0,49}$");

    private final ApiSpecificationRepository specifications;
    private final SpecificationContentRepository contents;
    private final ScanRepository scans;
    private final ProjectService projectService;
    private final AnalyzerClient analyzer;
    private final UploadProperties uploadProperties;

    public SpecificationService(ApiSpecificationRepository specifications, SpecificationContentRepository contents,
            ScanRepository scans, ProjectService projectService, AnalyzerClient analyzer,
            UploadProperties uploadProperties) {
        this.specifications = specifications;
        this.contents = contents;
        this.scans = scans;
        this.projectService = projectService;
        this.analyzer = analyzer;
        this.uploadProperties = uploadProperties;
    }

    /**
     * Upload flow: local file checks, then structural validation by the analyzer (the single
     * source of truth for what a valid spec is), then duplicate checks, then one insert.
     */
    @Transactional
    public SpecificationResponse upload(UUID userId, UUID projectId, String versionLabel, String filename,
            byte[] bytes) {
        Project project = projectService.requireOwned(projectId, userId);
        String label = versionLabel == null ? "" : versionLabel.trim();
        if (!VERSION_LABEL.matcher(label).matches()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "The request is not valid.",
                    List.of(Map.of("field", "versionLabel", "message",
                            "must be 1-50 characters: letters, digits, '.', '_', '+' or '-'")));
        }
        ValidFile file = SpecFileValidator.validate(filename, bytes, uploadProperties.maxSpecBytes());
        if (specifications.existsByProjectIdAndVersionLabelIgnoreCase(projectId, label)) {
            throw ApiException.conflict("VERSION_LABEL_TAKEN",
                    "This project already has a specification labelled '" + label + "'.");
        }
        String sha256 = sha256(file.content());
        specifications.findFirstByProjectIdAndSha256(projectId, sha256).ifPresent(existing -> {
            throw ApiException.conflict("DUPLICATE_CONTENT",
                    "Identical content was already uploaded as '" + existing.getVersionLabel() + "'.");
        });

        ValidationResult result = analyzer.validate(file.content(), file.filename());
        if (!result.valid()) {
            String code = result.error() != null && result.error().code() != null
                    ? result.error().code() : "SPEC_INVALID";
            String message = result.error() != null && result.error().message() != null
                    ? result.error().message() : "The specification is not valid.";
            List<Map<String, Object>> issues = result.error() == null || result.error().issues() == null
                    ? List.of()
                    : result.error().issues().stream()
                            .map(i -> Map.<String, Object>of("pointer", String.valueOf(i.pointer()),
                                    "message", String.valueOf(i.message())))
                            .toList();
            HttpStatus status = "SPEC_TOO_LARGE".equals(code) ? HttpStatus.CONTENT_TOO_LARGE
                    : HttpStatus.UNPROCESSABLE_CONTENT;
            throw new ApiException(status, code, message, issues);
        }

        var info = result.spec();
        ApiSpecification spec = specifications.save(new ApiSpecification(project, label, file.filename(),
                file.format(), info.openapiVersion(), truncate(info.title(), 255), truncate(info.apiVersion(), 100),
                info.operationCount(), bytes.length, sha256, userId));
        contents.save(new SpecificationContent(spec.getId(), file.content()));
        return SpecificationResponse.from(spec);
    }

    @Transactional(readOnly = true)
    public PageResponse<SpecificationResponse> list(UUID userId, UUID projectId, int page, int size) {
        projectService.requireOwned(projectId, userId);
        var pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "createdAt"));
        return PageResponse.of(specifications.findByProjectId(projectId, pageable), SpecificationResponse::from);
    }

    @Transactional(readOnly = true)
    public SpecificationResponse get(UUID userId, UUID projectId, UUID specId) {
        return SpecificationResponse.from(requireSpec(userId, projectId, specId));
    }

    @Transactional(readOnly = true)
    public SpecificationFile file(UUID userId, UUID projectId, UUID specId) {
        ApiSpecification spec = requireSpec(userId, projectId, specId);
        return new SpecificationFile(spec.getOriginalFilename(), spec.getFormat(), content(spec.getId()));
    }

    @Transactional
    public void delete(UUID userId, UUID projectId, UUID specId) {
        ApiSpecification spec = requireSpec(userId, projectId, specId);
        if (scans.existsByBaselineSpecificationIdOrTargetSpecificationId(specId, specId)) {
            throw ApiException.conflict("SPECIFICATION_IN_USE",
                    "This specification is referenced by scans and cannot be deleted.");
        }
        contents.deleteById(specId);
        specifications.delete(spec);
    }

    /** Loads a specification of a project the user owns, or 404. */
    @Transactional(readOnly = true)
    public ApiSpecification requireSpec(UUID userId, UUID projectId, UUID specId) {
        projectService.requireOwned(projectId, userId);
        return specifications.findByIdAndProjectId(specId, projectId)
                .orElseThrow(() -> ApiException.notFound("Specification"));
    }

    @Transactional(readOnly = true)
    public SpecPayload payload(ApiSpecification spec) {
        return new SpecPayload(content(spec.getId()), spec.getOriginalFilename());
    }

    private String content(UUID specId) {
        return contents.findById(specId).map(SpecificationContent::getContent)
                .orElseThrow(() -> new IllegalStateException("Missing content for specification " + specId));
    }

    private static String sha256(String content) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(content.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    private static String truncate(String value, int max) {
        return value == null || value.length() <= max ? value : value.substring(0, max);
    }
}
