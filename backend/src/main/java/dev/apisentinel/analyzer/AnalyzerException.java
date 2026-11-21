package dev.apisentinel.analyzer;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpStatus;

/**
 * A failed call to the analyzer. The client-facing message never contains the internal token,
 * URLs or raw analyzer errors; the internal reason is only logged.
 */
public class AnalyzerException extends RuntimeException {

    private final HttpStatus status;
    private final String code;
    private final String internalReason;
    private final List<Map<String, Object>> errors;
    private UUID scanId;

    public AnalyzerException(HttpStatus status, String code, String publicMessage, String internalReason,
            List<Map<String, Object>> errors) {
        super(publicMessage);
        this.status = status;
        this.code = code;
        this.internalReason = internalReason;
        this.errors = errors == null ? List.of() : errors;
    }

    public static AnalyzerException unavailable(String reason) {
        return new AnalyzerException(HttpStatus.SERVICE_UNAVAILABLE, "ANALYZER_UNAVAILABLE",
                "The analysis service is unavailable. Try again shortly.", reason, null);
    }

    public static AnalyzerException timeout(String reason) {
        return new AnalyzerException(HttpStatus.GATEWAY_TIMEOUT, "ANALYZER_TIMEOUT",
                "The analysis service did not respond in time.", reason, null);
    }

    public static AnalyzerException error(String reason) {
        return new AnalyzerException(HttpStatus.BAD_GATEWAY, "ANALYZER_ERROR",
                "The analysis service failed to process the request.", reason, null);
    }

    public HttpStatus getStatus() {
        return status;
    }

    public String getCode() {
        return code;
    }

    public String getInternalReason() {
        return internalReason;
    }

    public List<Map<String, Object>> getErrors() {
        return errors;
    }

    public UUID getScanId() {
        return scanId;
    }

    public AnalyzerException withScanId(UUID scanId) {
        this.scanId = scanId;
        return this;
    }
}
