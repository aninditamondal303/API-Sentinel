package dev.apisentinel.auth;

import dev.apisentinel.user.User;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.util.UUID;

public final class AuthDtos {

    private AuthDtos() {
    }

    public record RegisterRequest(
            @NotBlank @Email @Size(max = 254) String email,
            @NotBlank @Size(min = 8, max = 128, message = "must be 8 to 128 characters")
            @Pattern(regexp = "^(?=.*[A-Za-z])(?=.*\\d).*$", message = "must contain a letter and a digit")
            String password,
            @NotBlank @Size(max = 100) String displayName) {
    }

    public record ChangePasswordRequest(
            @NotBlank @Size(max = 128) String currentPassword,
            @NotBlank @Size(min = 8, max = 128, message = "must be 8 to 128 characters")
            @Pattern(regexp = "^(?=.*[A-Za-z])(?=.*\\d).*$", message = "must contain a letter and a digit")
            String newPassword) {
    }

    public record LoginRequest(@NotBlank @Size(max = 254) String email, @NotBlank @Size(max = 128) String password) {
    }

    public record UserResponse(UUID id, String email, String displayName, Instant createdAt) {
        public static UserResponse from(User user) {
            return new UserResponse(user.getId(), user.getEmail(), user.getDisplayName(), user.getCreatedAt());
        }
    }

    public record TokenResponse(String accessToken, String tokenType, long expiresIn, UserResponse user) {
    }
}
