package dev.apisentinel.common;

import jakarta.servlet.http.HttpServletRequest;
import java.net.URI;
import java.util.List;
import java.util.Map;
import org.slf4j.MDC;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;

/** Builds the single error format used by every endpoint and by the security filters. */
public final class Problems {

    private Problems() {
    }

    public static ProblemDetail of(HttpStatus status, String code, String detail, HttpServletRequest request) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(status, detail);
        problem.setTitle(status.getReasonPhrase());
        if (request != null) {
            problem.setInstance(URI.create(request.getRequestURI()));
        }
        problem.setProperty("errorCode", code);
        problem.setProperty("requestId", MDC.get(RequestIdFilter.MDC_KEY));
        return problem;
    }

    public static ProblemDetail of(HttpStatus status, String code, String detail, HttpServletRequest request,
            List<Map<String, Object>> errors) {
        ProblemDetail problem = of(status, code, detail, request);
        if (errors != null && !errors.isEmpty()) {
            problem.setProperty("errors", errors);
        }
        return problem;
    }
}
