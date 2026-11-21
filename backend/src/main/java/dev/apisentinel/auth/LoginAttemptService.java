package dev.apisentinel.auth;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Locale;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.stereotype.Service;

/**
 * Slows down password guessing: after {@value #MAX_FAILURES} failed logins for an email within
 * the window, further attempts are rejected until the window passes. In-memory, so it applies
 * per backend instance (documented limitation).
 */
@Service
public class LoginAttemptService {

    static final int MAX_FAILURES = 5;
    static final Duration WINDOW = Duration.ofMinutes(15);

    private record Attempts(int failures, Instant windowStart) {
    }

    private final ConcurrentHashMap<String, Attempts> attempts = new ConcurrentHashMap<>();
    private final Clock clock;

    public LoginAttemptService() {
        this(Clock.systemUTC());
    }

    LoginAttemptService(Clock clock) {
        this.clock = clock;
    }

    public boolean isBlocked(String email) {
        Attempts current = attempts.get(key(email));
        if (current == null) {
            return false;
        }
        if (current.windowStart().plus(WINDOW).isBefore(clock.instant())) {
            attempts.remove(key(email));
            return false;
        }
        return current.failures() >= MAX_FAILURES;
    }

    public void recordFailure(String email) {
        Instant now = clock.instant();
        attempts.compute(key(email), (k, current) -> {
            if (current == null || current.windowStart().plus(WINDOW).isBefore(now)) {
                return new Attempts(1, now);
            }
            return new Attempts(current.failures() + 1, current.windowStart());
        });
    }

    public void recordSuccess(String email) {
        attempts.remove(key(email));
    }

    private static String key(String email) {
        return email.trim().toLowerCase(Locale.ROOT);
    }
}
