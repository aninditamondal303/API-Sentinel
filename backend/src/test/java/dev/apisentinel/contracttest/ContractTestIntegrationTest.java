package dev.apisentinel.contracttest;

import static dev.apisentinel.support.TestApi.example;
import static org.assertj.core.api.Assertions.assertThat;

import dev.apisentinel.support.FullStackIntegrationTest;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import org.junit.jupiter.api.Test;

class ContractTestIntegrationTest extends FullStackIntegrationTest {

    private String base(String project, String spec) {
        return "/api/v1/projects/" + project + "/specifications/" + spec + "/contract-tests";
    }

    @Test
    void previewAndZipDownloadComeFromTheAnalyzer() throws IOException {
        String token = api.register("Owner");
        String project = api.createProject(token, "Inventory");
        String spec = api.uploadFile(token, project, example("examples/inventory-api/openapi.yaml"), "v1");

        var preview = api.get(base(project, spec), token).expect(200);
        assertThat(preview.list("files")).isNotEmpty();
        assertThat(preview.list("operations")).isNotEmpty();
        assertThat(preview.str("runCommand")).contains("pytest");

        var download = api.get(base(project, spec) + "/download?baseUrl=https://staging.example.com", token)
                .expect(200);
        assertThat(download.header("Content-Type")).isEqualTo("application/zip");
        assertThat(download.header("Content-Disposition")).contains("attachment").contains(".zip");

        Map<String, String> entries = unzip(download.raw());
        assertThat(entries).isNotEmpty();
        assertThat(entries.keySet()).anyMatch(n -> n.endsWith(".py"));
        assertThat(entries.keySet()).allSatisfy(n -> assertThat(n).doesNotStartWith("/").doesNotContain(".."));
        assertThat(String.join("\n", entries.values())).contains("staging.example.com");
        assertThat(entries.size()).isEqualTo(preview.list("files").size());
    }

    @Test
    void invalidBaseUrlAndForeignAccessAreRejected() {
        String token = api.register("Owner");
        String project = api.createProject(token, "Inventory");
        String spec = api.uploadFile(token, project, example("examples/inventory-api/openapi.yaml"), "v1");
        assertThat(api.get(base(project, spec) + "?baseUrl=file:///etc/passwd", token).expect(400).str("errorCode"))
                .isEqualTo("INVALID_BASE_URL");
        String mallory = api.register("Mallory");
        api.get(base(project, spec), mallory).expect(404);
        api.get(base(project, spec) + "/download", mallory).expect(404);
    }

    private static Map<String, String> unzip(byte[] bytes) throws IOException {
        Map<String, String> entries = new HashMap<>();
        try (ZipInputStream zip = new ZipInputStream(new ByteArrayInputStream(bytes))) {
            ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) {
                entries.put(entry.getName(), new String(zip.readAllBytes(), StandardCharsets.UTF_8));
            }
        }
        return entries;
    }
}
