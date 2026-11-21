package dev.apisentinel.project;

import dev.apisentinel.auth.CurrentUser;
import dev.apisentinel.common.PageResponse;
import dev.apisentinel.project.ProjectDtos.PolicyRequest;
import dev.apisentinel.project.ProjectDtos.PolicyResponse;
import dev.apisentinel.project.ProjectDtos.ProjectRequest;
import dev.apisentinel.project.ProjectDtos.ProjectResponse;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.util.UUID;
import dev.apisentinel.common.Locations;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "Projects")
@RestController
@RequestMapping("/api/v1/projects")
public class ProjectController {

    private final ProjectService projectService;

    public ProjectController(ProjectService projectService) {
        this.projectService = projectService;
    }

    @PostMapping
    public ResponseEntity<ProjectResponse> create(@AuthenticationPrincipal Jwt jwt,
            @Valid @RequestBody ProjectRequest request) {
        ProjectResponse created = projectService.create(CurrentUser.id(jwt), request);
        return ResponseEntity.created(Locations.of("/api/v1/projects/{id}", created.id())).body(created);
    }

    @GetMapping
    public PageResponse<ProjectResponse> list(@AuthenticationPrincipal Jwt jwt,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size) {
        return projectService.list(CurrentUser.id(jwt), page, size);
    }

    @GetMapping("/{projectId}")
    public ProjectResponse get(@AuthenticationPrincipal Jwt jwt, @PathVariable UUID projectId) {
        return projectService.get(CurrentUser.id(jwt), projectId);
    }

    @PutMapping("/{projectId}")
    public ProjectResponse update(@AuthenticationPrincipal Jwt jwt, @PathVariable UUID projectId,
            @Valid @RequestBody ProjectRequest request) {
        return projectService.update(CurrentUser.id(jwt), projectId, request);
    }

    @DeleteMapping("/{projectId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@AuthenticationPrincipal Jwt jwt, @PathVariable UUID projectId) {
        projectService.delete(CurrentUser.id(jwt), projectId);
    }

    @GetMapping("/{projectId}/policy")
    public PolicyResponse getPolicy(@AuthenticationPrincipal Jwt jwt, @PathVariable UUID projectId) {
        return projectService.getPolicy(CurrentUser.id(jwt), projectId);
    }

    @PutMapping("/{projectId}/policy")
    public PolicyResponse updatePolicy(@AuthenticationPrincipal Jwt jwt, @PathVariable UUID projectId,
            @Valid @RequestBody PolicyRequest request) {
        return projectService.updatePolicy(CurrentUser.id(jwt), projectId, request);
    }
}
