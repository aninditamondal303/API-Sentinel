package dev.apisentinel.project;

import dev.apisentinel.common.ApiException;
import dev.apisentinel.common.PageResponse;
import dev.apisentinel.project.ProjectDtos.PolicyRequest;
import dev.apisentinel.project.ProjectDtos.PolicyResponse;
import dev.apisentinel.project.ProjectDtos.ProjectRequest;
import dev.apisentinel.project.ProjectDtos.ProjectResponse;
import dev.apisentinel.user.UserRepository;
import java.util.UUID;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ProjectService {

    private final ProjectRepository projects;
    private final UserRepository users;

    public ProjectService(ProjectRepository projects, UserRepository users) {
        this.projects = projects;
        this.users = users;
    }

    /** Loads a project the user owns, or 404 (also for other users' projects: no enumeration). */
    @Transactional(readOnly = true)
    public Project requireOwned(UUID projectId, UUID userId) {
        return projects.findByIdAndOwnerId(projectId, userId).orElseThrow(() -> ApiException.notFound("Project"));
    }

    @Transactional
    public ProjectResponse create(UUID userId, ProjectRequest request) {
        String name = request.name().trim();
        if (projects.existsByOwnerIdAndNameIgnoreCase(userId, name)) {
            throw ApiException.conflict("PROJECT_NAME_TAKEN", "You already have a project with this name.");
        }
        var owner = users.getReferenceById(userId);
        return ProjectResponse.from(projects.save(new Project(owner, name, trimToNull(request.description()))));
    }

    @Transactional(readOnly = true)
    public PageResponse<ProjectResponse> list(UUID userId, int page, int size) {
        var pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "createdAt"));
        return PageResponse.of(projects.findByOwnerId(userId, pageable), ProjectResponse::from);
    }

    @Transactional(readOnly = true)
    public ProjectResponse get(UUID userId, UUID projectId) {
        return ProjectResponse.from(requireOwned(projectId, userId));
    }

    @Transactional
    public ProjectResponse update(UUID userId, UUID projectId, ProjectRequest request) {
        Project project = requireOwned(projectId, userId);
        String name = request.name().trim();
        if (projects.existsByOwnerIdAndNameIgnoreCaseAndIdNot(userId, name, projectId)) {
            throw ApiException.conflict("PROJECT_NAME_TAKEN", "You already have a project with this name.");
        }
        project.update(name, trimToNull(request.description()));
        return ProjectResponse.from(project);
    }

    @Transactional
    public void delete(UUID userId, UUID projectId) {
        // Specifications, scans and findings are removed by ON DELETE CASCADE.
        projects.delete(requireOwned(projectId, userId));
    }

    @Transactional(readOnly = true)
    public PolicyResponse getPolicy(UUID userId, UUID projectId) {
        return PolicyResponse.from(requireOwned(projectId, userId).getPolicy());
    }

    @Transactional
    public PolicyResponse updatePolicy(UUID userId, UUID projectId, PolicyRequest request) {
        Project project = requireOwned(projectId, userId);
        project.updatePolicy(new CompatibilityPolicy(request.failOn(), request.failOnManualReview()));
        return PolicyResponse.from(project.getPolicy());
    }

    private static String trimToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }
}
