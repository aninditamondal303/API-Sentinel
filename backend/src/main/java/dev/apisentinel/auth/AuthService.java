package dev.apisentinel.auth;

import dev.apisentinel.auth.AuthDtos.ChangePasswordRequest;
import dev.apisentinel.auth.AuthDtos.LoginRequest;
import dev.apisentinel.auth.AuthDtos.RegisterRequest;
import dev.apisentinel.auth.AuthDtos.TokenResponse;
import dev.apisentinel.auth.AuthDtos.UserResponse;
import dev.apisentinel.common.ApiException;
import dev.apisentinel.user.User;
import dev.apisentinel.user.UserRepository;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AuthService {

    private static final String BEARER = "Bearer";

    private final UserRepository users;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;
    private final LoginAttemptService loginAttempts;
    // Compared against when the email is unknown, so both failure paths cost a hash check.
    private final String dummyHash;

    public AuthService(UserRepository users, PasswordEncoder passwordEncoder, JwtService jwtService,
            LoginAttemptService loginAttempts) {
        this.users = users;
        this.passwordEncoder = passwordEncoder;
        this.jwtService = jwtService;
        this.loginAttempts = loginAttempts;
        this.dummyHash = passwordEncoder.encode(UUID.randomUUID().toString());
    }

    @Transactional
    public TokenResponse register(RegisterRequest request) {
        String email = normalize(request.email());
        if (users.existsByEmailIgnoreCase(email)) {
            throw ApiException.conflict("EMAIL_TAKEN", "An account with this email already exists.");
        }
        User user = users.save(new User(email, passwordEncoder.encode(request.password()),
                request.displayName().trim()));
        return token(user);
    }

    @Transactional(readOnly = true)
    public TokenResponse login(LoginRequest request) {
        String email = normalize(request.email());
        if (loginAttempts.isBlocked(email)) {
            throw new ApiException(HttpStatus.TOO_MANY_REQUESTS, "TOO_MANY_ATTEMPTS",
                    "Too many failed login attempts. Try again later.");
        }
        Optional<User> user = users.findByEmailIgnoreCase(email);
        String hash = user.map(User::getPasswordHash).orElse(dummyHash);
        boolean matches = passwordEncoder.matches(request.password(), hash);
        if (user.isEmpty() || !matches) {
            loginAttempts.recordFailure(email);
            throw new ApiException(HttpStatus.UNAUTHORIZED, "INVALID_CREDENTIALS", "Invalid email or password.");
        }
        loginAttempts.recordSuccess(email);
        return token(user.get());
    }

    @Transactional(readOnly = true)
    public UserResponse me(UUID userId) {
        return users.findById(userId).map(UserResponse::from)
                .orElseThrow(() -> new ApiException(HttpStatus.UNAUTHORIZED, "UNAUTHENTICATED",
                        "The account for this token no longer exists."));
    }

    /**
     * Changes the password of the signed-in user after checking the current one. Wrong current
     * passwords count towards the same per-email lockout as failed logins, so a stolen token cannot
     * be used to guess the password. The error is a 400 field error (not 401), because a 401 on an
     * authenticated request means "session ended" to the client.
     */
    @Transactional
    public void changePassword(UUID userId, ChangePasswordRequest request) {
        User user = users.findById(userId)
                .orElseThrow(() -> new ApiException(HttpStatus.UNAUTHORIZED, "UNAUTHENTICATED",
                        "The account for this token no longer exists."));
        String email = user.getEmail();
        if (loginAttempts.isBlocked(email)) {
            throw new ApiException(HttpStatus.TOO_MANY_REQUESTS, "TOO_MANY_ATTEMPTS",
                    "Too many failed attempts. Try again later.");
        }
        if (!passwordEncoder.matches(request.currentPassword(), user.getPasswordHash())) {
            loginAttempts.recordFailure(email);
            throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_CURRENT_PASSWORD",
                    "The current password is incorrect.",
                    List.of(Map.of("field", "currentPassword", "message", "is incorrect")));
        }
        loginAttempts.recordSuccess(email);
        if (passwordEncoder.matches(request.newPassword(), user.getPasswordHash())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "The request is not valid.",
                    List.of(Map.of("field", "newPassword", "message", "must be different from the current password")));
        }
        user.changePasswordHash(passwordEncoder.encode(request.newPassword()));
    }

    private TokenResponse token(User user) {
        return new TokenResponse(jwtService.issue(user), BEARER, jwtService.ttlSeconds(), UserResponse.from(user));
    }

    private static String normalize(String email) {
        return email.trim().toLowerCase(Locale.ROOT);
    }
}
