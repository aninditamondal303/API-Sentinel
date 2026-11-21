package dev.apisentinel.config;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.time.Duration;
import java.util.Base64;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

/** JWT signing settings. The application refuses to start without a strong secret. */
@Validated
@ConfigurationProperties(prefix = "apisentinel.jwt")
public record JwtProperties(
        @NotBlank(message = "APISENTINEL_JWT_SECRET must be set") String secret,
        @NotBlank String issuer,
        @NotNull Duration ttl) {

    public static final int MIN_SECRET_BYTES = 32;

    public JwtProperties {
        if (secret != null && !secret.isBlank()) {
            byte[] decoded;
            try {
                decoded = Base64.getDecoder().decode(secret.trim());
            } catch (IllegalArgumentException e) {
                throw new IllegalArgumentException("APISENTINEL_JWT_SECRET must be Base64-encoded");
            }
            if (decoded.length < MIN_SECRET_BYTES) {
                throw new IllegalArgumentException(
                        "APISENTINEL_JWT_SECRET must decode to at least " + MIN_SECRET_BYTES + " bytes");
            }
        }
    }

    public byte[] secretBytes() {
        return Base64.getDecoder().decode(secret.trim());
    }
}
