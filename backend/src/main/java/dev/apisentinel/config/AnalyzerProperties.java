package dev.apisentinel.config;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

/** Connection to the internal Python analyzer service. */
@Validated
@ConfigurationProperties(prefix = "apisentinel.analyzer")
public record AnalyzerProperties(
        @NotBlank String baseUrl,
        @NotBlank(message = "APISENTINEL_INTERNAL_TOKEN must be set") String token,
        @NotNull Duration connectTimeout,
        @NotNull Duration readTimeout) {
}
