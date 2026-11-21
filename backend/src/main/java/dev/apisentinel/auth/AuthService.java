package dev.apisentinel.auth;

import dev.apisentinel.auth.AuthDtos.LoginRequest;
import dev.apisentinel.auth.AuthDtos.RegisterRequest;
import dev.apisentinel.auth.AuthDtos.TokenResponse;
import dev.apisentinel.auth.AuthDtos.UserResponse;
import dev.apisentinel.common.ApiException;
import dev.apisentinel.user.User;
import dev.apisentinel.user.UserRepository;
import java.util.Locale;
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

    private TokenResponse token(User user) {
        return new TokenResponse(jwtService.issue(user), BEARER, jwtService.ttlSeconds(), UserResponse.from(user));
    }

    private static String normalize(String email) {
        return email.trim().toLowerCase(Locale.ROOT);
    }
}
