package dev.apisentinel.project;

import java.util.Optional;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

/** Every lookup is scoped to the owner, so another user's project is simply "not found". */
public interface ProjectRepository extends JpaRepository<Project, UUID> {

    Optional<Project> findByIdAndOwnerId(UUID id, UUID ownerId);

    Page<Project> findByOwnerId(UUID ownerId, Pageable pageable);

    long countByOwnerId(UUID ownerId);

    boolean existsByOwnerIdAndNameIgnoreCase(UUID ownerId, String name);

    boolean existsByOwnerIdAndNameIgnoreCaseAndIdNot(UUID ownerId, String name, UUID id);
}
