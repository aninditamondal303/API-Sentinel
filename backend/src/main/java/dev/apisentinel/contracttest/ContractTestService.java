package dev.apisentinel.contracttest;

import dev.apisentinel.analyzer.AnalyzerClient;
import dev.apisentinel.analyzer.AnalyzerDtos.ContractTestResult;
import dev.apisentinel.analyzer.AnalyzerDtos.GeneratedFile;
import dev.apisentinel.analyzer.AnalyzerDtos.SpecPayload;
import dev.apisentinel.common.ApiException;
import dev.apisentinel.spec.ApiSpecification;
import dev.apisentinel.spec.SpecificationService;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.net.URI;
import java.net.URISyntaxException;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.UUID;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import org.springframework.stereotype.Service;

/**
 * Generates contract tests through the analyzer and packages them. Generated tests are never
 * executed by the backend.
 */
@Service
public class ContractTestService {

    private static final Pattern SAFE_FILE_NAME = Pattern.compile("^[A-Za-z0-9_.-]{1,100}$");

    private final SpecificationService specificationService;
    private final AnalyzerClient analyzer;

    public ContractTestService(SpecificationService specificationService, AnalyzerClient analyzer) {
        this.specificationService = specificationService;
        this.analyzer = analyzer;
    }

    public record GeneratedSuite(ApiSpecification specification, ContractTestResult result) {
    }

    public GeneratedSuite generate(UUID userId, UUID projectId, UUID specId, boolean includeUnsafeMethods,
            String baseUrl) {
        String validatedBaseUrl = validateBaseUrl(baseUrl);
        Loaded loaded = load(userId, projectId, specId);
        ContractTestResult result = analyzer.contractTests(loaded.payload(), includeUnsafeMethods, validatedBaseUrl);
        return new GeneratedSuite(loaded.specification(), result);
    }

    /** Zips the generated files under one folder; file names come from the analyzer and are re-checked. */
    public byte[] zip(GeneratedSuite suite) {
        String folder = "contract-tests-" + slug(suite.specification().getVersionLabel());
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ZipOutputStream zip = new ZipOutputStream(bytes)) {
            for (GeneratedFile file : suite.result().files()) {
                if (!SAFE_FILE_NAME.matcher(file.path()).matches()) {
                    throw new IllegalStateException("Unexpected generated file name");
                }
                zip.putNextEntry(new ZipEntry(folder + "/" + file.path()));
                zip.write(file.content().getBytes(StandardCharsets.UTF_8));
                zip.closeEntry();
            }
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        return bytes.toByteArray();
    }

    public static String zipName(GeneratedSuite suite) {
        return "contract-tests-" + slug(suite.specification().getVersionLabel()) + ".zip";
    }

    private record Loaded(ApiSpecification specification, SpecPayload payload) {
    }

    // No transaction here on purpose: the analyzer call must not hold a database connection.
    // requireSpec() and payload() run in their own short read-only transactions.
    private Loaded load(UUID userId, UUID projectId, UUID specId) {
        ApiSpecification spec = specificationService.requireSpec(userId, projectId, specId);
        return new Loaded(spec, specificationService.payload(spec));
    }

    static String validateBaseUrl(String baseUrl) {
        if (baseUrl == null || baseUrl.isBlank()) {
            return null;
        }
        try {
            URI uri = new URI(baseUrl.trim());
            String scheme = uri.getScheme() == null ? "" : uri.getScheme().toLowerCase(Locale.ROOT);
            if (!(scheme.equals("http") || scheme.equals("https")) || uri.getHost() == null) {
                throw new URISyntaxException(baseUrl, "not an http(s) URL");
            }
            return uri.toString();
        } catch (URISyntaxException e) {
            throw ApiException.badRequest("INVALID_BASE_URL", "baseUrl must be an absolute http:// or https:// URL.");
        }
    }

    private static String slug(String label) {
        String slug = label.replaceAll("[^A-Za-z0-9._-]", "-");
        return slug.isEmpty() ? "spec" : slug;
    }
}
