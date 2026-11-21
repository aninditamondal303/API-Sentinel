package dev.apisentinel.common;

import dev.apisentinel.analyzer.AnalyzerException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.ConstraintViolationException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.HttpMediaTypeNotSupportedException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.HandlerMethodValidationException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.multipart.MaxUploadSizeExceededException;
import org.springframework.web.multipart.support.MissingServletRequestPartException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

/**
 * Maps every failure to RFC 9457 problem details with a stable errorCode and the request ID.
 * Unexpected errors are logged with their stack trace but answered with a generic message.
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(ApiException.class)
    ProblemDetail handleApi(ApiException e, HttpServletRequest request) {
        return Problems.of(e.getStatus(), e.getCode(), e.getMessage(), request, e.getErrors());
    }

    @ExceptionHandler(AnalyzerException.class)
    ProblemDetail handleAnalyzer(AnalyzerException e, HttpServletRequest request) {
        if (e.getStatus().is5xxServerError()) {
            log.warn("Analyzer call failed: {} ({})", e.getCode(), e.getInternalReason());
        }
        ProblemDetail problem = Problems.of(e.getStatus(), e.getCode(), e.getMessage(), request, e.getErrors());
        if (e.getScanId() != null) {
            problem.setProperty("scanId", e.getScanId());
        }
        return problem;
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    ProblemDetail handleBodyValidation(MethodArgumentNotValidException e, HttpServletRequest request) {
        List<Map<String, Object>> errors = new ArrayList<>();
        e.getBindingResult().getFieldErrors().forEach(fe -> errors.add(
                Map.of("field", fe.getField(), "message", String.valueOf(fe.getDefaultMessage()))));
        e.getBindingResult().getGlobalErrors().forEach(ge -> errors.add(
                Map.of("field", ge.getObjectName(), "message", String.valueOf(ge.getDefaultMessage()))));
        return Problems.of(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "The request is not valid.", request, errors);
    }

    @ExceptionHandler(HandlerMethodValidationException.class)
    ProblemDetail handleParameterValidation(HandlerMethodValidationException e, HttpServletRequest request) {
        List<Map<String, Object>> errors = new ArrayList<>();
        e.getParameterValidationResults().forEach(result -> result.getResolvableErrors().forEach(err -> errors.add(
                Map.of("field", String.valueOf(result.getMethodParameter().getParameterName()),
                        "message", String.valueOf(err.getDefaultMessage())))));
        return Problems.of(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "The request is not valid.", request, errors);
    }

    @ExceptionHandler(ConstraintViolationException.class)
    ProblemDetail handleConstraint(ConstraintViolationException e, HttpServletRequest request) {
        List<Map<String, Object>> errors = new ArrayList<>();
        e.getConstraintViolations().forEach(v -> errors.add(
                Map.of("field", String.valueOf(v.getPropertyPath()), "message", v.getMessage())));
        return Problems.of(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "The request is not valid.", request, errors);
    }

    @ExceptionHandler({MissingServletRequestParameterException.class, MissingServletRequestPartException.class})
    ProblemDetail handleMissing(Exception e, HttpServletRequest request) {
        return Problems.of(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", e.getMessage(), request);
    }

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    ProblemDetail handleTypeMismatch(MethodArgumentTypeMismatchException e, HttpServletRequest request) {
        return Problems.of(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED",
                "Parameter '" + e.getName() + "' has an invalid value.", request);
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    ProblemDetail handleUnreadable(HttpMessageNotReadableException e, HttpServletRequest request) {
        return Problems.of(HttpStatus.BAD_REQUEST, "MALFORMED_REQUEST", "The request body is not valid JSON.",
                request);
    }

    @ExceptionHandler(MaxUploadSizeExceededException.class)
    ProblemDetail handleTooLarge(MaxUploadSizeExceededException e, HttpServletRequest request) {
        return Problems.of(HttpStatus.CONTENT_TOO_LARGE, "PAYLOAD_TOO_LARGE",
                "The uploaded file exceeds the 5 MB limit.", request);
    }

    @ExceptionHandler(HttpMediaTypeNotSupportedException.class)
    ProblemDetail handleMediaType(HttpMediaTypeNotSupportedException e, HttpServletRequest request) {
        return Problems.of(HttpStatus.UNSUPPORTED_MEDIA_TYPE, "UNSUPPORTED_MEDIA_TYPE",
                "Content type is not supported by this endpoint.", request);
    }

    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    ProblemDetail handleMethod(HttpRequestMethodNotSupportedException e, HttpServletRequest request) {
        return Problems.of(HttpStatus.METHOD_NOT_ALLOWED, "METHOD_NOT_ALLOWED", "Method not allowed.", request);
    }

    @ExceptionHandler(NoResourceFoundException.class)
    ProblemDetail handleNoResource(NoResourceFoundException e, HttpServletRequest request) {
        return Problems.of(HttpStatus.NOT_FOUND, "NOT_FOUND", "No such endpoint.", request);
    }

    @ExceptionHandler(DataIntegrityViolationException.class)
    ProblemDetail handleIntegrity(DataIntegrityViolationException e, HttpServletRequest request) {
        log.info("Data integrity violation: {}", e.getMostSpecificCause().getMessage());
        return Problems.of(HttpStatus.CONFLICT, "CONFLICT", "The request conflicts with existing data.", request);
    }

    @ExceptionHandler(Exception.class)
    ProblemDetail handleUnexpected(Exception e, HttpServletRequest request) {
        log.error("Unhandled error", e);
        return Problems.of(HttpStatus.INTERNAL_SERVER_ERROR, "INTERNAL_ERROR",
                "Unexpected server error. Quote the requestId when reporting it.", request);
    }
}
