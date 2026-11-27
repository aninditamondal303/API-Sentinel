package dev.apisentinel.analyzer;

import dev.apisentinel.analyzer.AnalyzerDtos.AnalysisOptions;
import dev.apisentinel.analyzer.AnalyzerDtos.AnalysisRequest;
import dev.apisentinel.analyzer.AnalyzerDtos.AnalysisResult;
import dev.apisentinel.analyzer.AnalyzerDtos.ContractTestOptions;
import dev.apisentinel.analyzer.AnalyzerDtos.ContractTestRequest;
import dev.apisentinel.analyzer.AnalyzerDtos.ContractTestResult;
import dev.apisentinel.analyzer.AnalyzerDtos.Problem;
import dev.apisentinel.analyzer.AnalyzerDtos.RulesResult;
import dev.apisentinel.analyzer.AnalyzerDtos.ScanOptions;
import dev.apisentinel.analyzer.AnalyzerDtos.SecurityScanRequest;
import dev.apisentinel.analyzer.AnalyzerDtos.SecurityScanResult;
import dev.apisentinel.analyzer.AnalyzerDtos.SpecPayload;
import dev.apisentinel.analyzer.AnalyzerDtos.SpecRequest;
import dev.apisentinel.analyzer.AnalyzerDtos.ValidationResult;
import dev.apisentinel.common.RequestIdFilter;
import dev.apisentinel.common.Severity;
import dev.apisentinel.config.AnalyzerProperties;
import java.net.ConnectException;
import java.net.UnknownHostException;
import java.net.http.HttpClient;
import java.net.http.HttpTimeoutException;
import java.nio.channels.UnresolvedAddressException;
import java.util.List;
import java.util.Map;
import java.util.function.Supplier;
import org.slf4j.MDC;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;
import tools.jackson.databind.json.JsonMapper;

/**
 * The only class that talks to the Python analyzer. It sends the internal token, propagates the
 * request ID and translates every transport or HTTP failure into an {@link AnalyzerException}.
 * No analysis logic lives here: results come back exactly as the analyzer produced them.
 */
@Component
public class AnalyzerClient {

    private static final String TOKEN_HEADER = "X-Internal-Token";

    private final RestClient restClient;
    private final JsonMapper jsonMapper;

    public AnalyzerClient(AnalyzerProperties properties, JsonMapper jsonMapper) {
        this.jsonMapper = jsonMapper;
        HttpClient httpClient = HttpClient.newBuilder()
                .connectTimeout(properties.connectTimeout())
                .version(HttpClient.Version.HTTP_1_1)
                .build();
        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
        requestFactory.setReadTimeout(properties.readTimeout());
        this.restClient = RestClient.builder()
                .baseUrl(properties.baseUrl())
                .requestFactory(requestFactory)
                .defaultHeader(TOKEN_HEADER, properties.token())
                .build();
    }

    /** True when the analyzer answers its readiness probe with 2xx; never throws. */
    public boolean isReady() {
        try {
            return restClient.get().uri("/health/ready").retrieve().toBodilessEntity().getStatusCode()
                    .is2xxSuccessful();
        } catch (RuntimeException e) {
            return false;
        }
    }

    public ValidationResult validate(String content, String filename) {
        return post("/internal/v1/specs/validate", new SpecRequest(new SpecPayload(content, filename)),
                ValidationResult.class);
    }

    public AnalysisResult analyze(SpecPayload baseline, SpecPayload candidate, Severity failOn,
            boolean failOnManualReview) {
        AnalysisRequest request = new AnalysisRequest(baseline, candidate,
                new AnalysisOptions(failOn == null ? null : failOn.name(), failOnManualReview));
        return post("/internal/v1/analyses", request, AnalysisResult.class);
    }

    public SecurityScanResult securityScan(SpecPayload spec, Severity failOn) {
        SecurityScanRequest request = new SecurityScanRequest(spec,
                new ScanOptions(failOn == null ? null : failOn.name()));
        return post("/internal/v1/security-scans", request, SecurityScanResult.class);
    }

    public ContractTestResult contractTests(SpecPayload spec, boolean includeUnsafeMethods, String baseUrl) {
        ContractTestRequest request = new ContractTestRequest(spec,
                new ContractTestOptions(includeUnsafeMethods, baseUrl));
        return post("/internal/v1/contract-tests", request, ContractTestResult.class);
    }

    /** The analyzer's rule catalogue (id, category, severity, impact, remediation for every rule). */
    public RulesResult rules() {
        String path = "/internal/v1/rules";
        return call(path, () -> restClient.get()
                .uri(path)
                .accept(MediaType.APPLICATION_JSON)
                .headers(h -> {
                    String requestId = MDC.get(RequestIdFilter.MDC_KEY);
                    if (requestId != null) {
                        h.set(RequestIdFilter.HEADER, requestId);
                    }
                })
                .retrieve()
                .body(RulesResult.class));
    }

    private <T> T post(String path, Object body, Class<T> type) {
        return call(path, () -> restClient.post()
                .uri(path)
                .contentType(MediaType.APPLICATION_JSON)
                .accept(MediaType.APPLICATION_JSON)
                .headers(h -> {
                    String requestId = MDC.get(RequestIdFilter.MDC_KEY);
                    if (requestId != null) {
                        h.set(RequestIdFilter.HEADER, requestId);
                    }
                })
                .body(body)
                .retrieve()
                .body(type));
    }

    private <T> T call(String path, Supplier<T> request) {
        T result;
        try {
            result = request.get();
        } catch (RestClientResponseException e) {
            throw translate(path, e.getStatusCode(), e.getResponseBodyAsString());
        } catch (ResourceAccessException e) {
            throw translateTransport(path, e);
        } catch (RestClientException e) {
            throw AnalyzerException.error(path + ": " + e.getClass().getSimpleName());
        }
        if (result == null) {
            throw AnalyzerException.error(path + ": empty response body");
        }
        return result;
    }

    private AnalyzerException translate(String path, HttpStatusCode status, String body) {
        Problem problem = parseProblem(body);
        String code = problem != null && problem.errorCode() != null ? problem.errorCode() : "HTTP_" + status.value();
        String internal = path + " returned " + status.value() + " " + code;
        int value = status.value();
        if (value == 422 || (value == 413 && "SPEC_TOO_LARGE".equals(code))) {
            // A problem with the user's specification: safe and useful to pass on.
            List<Map<String, Object>> errors = problem == null || problem.errors() == null ? List.of()
                    : problem.errors().stream()
                            .map(i -> Map.<String, Object>of("pointer", String.valueOf(i.pointer()),
                                    "message", String.valueOf(i.message())))
                            .toList();
            String detail = problem != null && problem.detail() != null ? problem.detail()
                    : "The specification could not be processed.";
            return new AnalyzerException(HttpStatus.valueOf(value), code, detail, internal, errors);
        }
        // 400/401/404/415/5xx mean a bug or misconfiguration on our side: never expose details.
        return AnalyzerException.error(internal);
    }

    private static AnalyzerException translateTransport(String path, ResourceAccessException e) {
        for (Throwable cause = e; cause != null; cause = cause.getCause()) {
            if (cause instanceof HttpTimeoutException) {
                return AnalyzerException.timeout(path + ": " + cause.getClass().getSimpleName());
            }
            if (cause instanceof ConnectException || cause instanceof UnknownHostException
                    || cause instanceof UnresolvedAddressException) {
                return AnalyzerException.unavailable(path + ": " + cause.getClass().getSimpleName());
            }
        }
        return AnalyzerException.unavailable(path + ": " + e.getClass().getSimpleName());
    }

    private Problem parseProblem(String body) {
        if (body == null || body.isBlank()) {
            return null;
        }
        try {
            return jsonMapper.readValue(body, Problem.class);
        } catch (RuntimeException e) {
            return null;
        }
    }
}
