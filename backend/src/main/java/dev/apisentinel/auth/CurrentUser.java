package dev.apisentinel.auth;

import java.util.UUID;
import org.springframework.security.oauth2.jwt.Jwt;

/** Reads the authenticated user's ID from a validated JWT (its subject claim). */
public final class CurrentUser {

    private CurrentUser() {
    }

    public static UUID id(Jwt jwt) {
        return UUID.fromString(jwt.getSubject());
    }
}
