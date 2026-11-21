package dev.apisentinel.spec;

import static dev.apisentinel.support.TestApi.example;
import static dev.apisentinel.support.TestApi.readBytes;
import static org.assertj.core.api.Assertions.assertThat;

import dev.apisentinel.support.FullStackIntegrationTest;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;

/** Uploads go through the real analyzer's /specs/validate endpoint. */
class SpecificationIntegrationTest extends FullStackIntegrationTest {

    private static final String BASE = "/api/v1/projects/%s/specifications";

    @Autowired
    SpecificationContentRepository contents;

    @Test
    void uploadYamlStoresAnalyzerMetadataAndExactContent() throws Exception {
        String token = api.register("Owner");
        String project = api.createProject(token, "Orders");
        byte[] bytes = readBytes(example("examples/orders-api/baseline.yaml"));

        var created = api.upload(BASE.formatted(project), "baseline.yaml", bytes, "v1.0.0", token).expect(201);
        assertThat(created.str("versionLabel")).isEqualTo("v1.0.0");
        assertThat(created.str("format")).isEqualTo("YAML");
        assertThat(created.str("openapiVersion")).startsWith("3.");
        assertThat(created.str("title")).isNotBlank();
        assertThat(created.num("operationCount")).isPositive();
        assertThat(created.num("sizeBytes")).isEqualTo(bytes.length);
        assertThat(created.str("sha256"))
                .isEqualTo(HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)));

        String id = created.str("id");
        assertThat(created.header("Location")).endsWith(BASE.formatted(project) + "/" + id);
        var content = api.get(BASE.formatted(project) + "/" + id + "/content", token).expect(200);
        assertThat(content.raw()).isEqualTo(bytes);
        assertThat(content.header("Content-Disposition")).contains("attachment").contains("baseline.yaml");
        assertThat(content.header("X-Content-Type-Options")).isEqualTo("nosniff");

        assertThat(api.get(BASE.formatted(project), token).expect(200).num("totalItems")).isEqualTo(1);
        assertThat(contents.findById(java.util.UUID.fromString(id))).isPresent();
    }

    @Test
    void uploadJsonIsAccepted() {
        String token = api.register("Owner");
        String project = api.createProject(token, "Json");
        String json = """
                {"openapi":"3.0.3","info":{"title":"Ping","version":"1"},
                 "paths":{"/ping":{"get":{"responses":{"200":{"description":"ok"}}}}}}
                """;
        var created = api.upload(BASE.formatted(project), "ping.json", json.getBytes(StandardCharsets.UTF_8),
                "v1", token).expect(201);
        assertThat(created.str("format")).isEqualTo("JSON");
        assertThat(created.num("operationCount")).isEqualTo(1);
    }

    @Test
    void invalidOpenApiIsRejectedWithAnalyzerIssues() {
        String token = api.register("Owner");
        String project = api.createProject(token, "Invalid");
        String broken = "openapi: 3.0.3\ninfo:\n  title: Broken\npaths: {}\n"; // info.version missing
        var res = api.upload(BASE.formatted(project), "broken.yaml", broken.getBytes(StandardCharsets.UTF_8), "v1",
                token).expect(422);
        assertThat(res.str("errorCode")).isEqualTo("SPEC_INVALID");
        assertThat(res.list("errors")).isNotEmpty();
        assertThat(api.get(BASE.formatted(project), token).expect(200).num("totalItems")).isZero();
    }

    @Test
    void unparseableYamlIsRejected() {
        String token = api.register("Owner");
        String project = api.createProject(token, "Garbage");
        var res = api.upload(BASE.formatted(project), "bad.yaml",
                "openapi: [unclosed".getBytes(StandardCharsets.UTF_8), "v1", token).expect(422);
        assertThat(res.str("errorCode")).isEqualTo("SPEC_PARSE_ERROR");
    }

    @Test
    void fileLevelChecks() {
        String token = api.register("Owner");
        String project = api.createProject(token, "Checks");
        String base = BASE.formatted(project);
        assertThat(api.upload(base, "spec.txt", "x".getBytes(StandardCharsets.UTF_8), "v1", token).expect(415)
                .str("errorCode")).isEqualTo("UNSUPPORTED_FILE_TYPE");
        assertThat(api.upload(base, "spec.yaml", new byte[0], "v1", token).expect(400).str("errorCode"))
                .isEqualTo("EMPTY_FILE");
        assertThat(api.upload(base, "spec.yaml", new byte[] {(byte) 0xC3, (byte) 0x28}, "v1", token).expect(400)
                .str("errorCode")).isEqualTo("INVALID_ENCODING");
        assertThat(api.upload(base, "spec.yaml", "openapi: 3.0.3".getBytes(StandardCharsets.UTF_8), "bad label!",
                token).expect(400).str("errorCode")).isEqualTo("VALIDATION_FAILED");
        api.upload(base, "spec.yaml", null, "v1", token).expect(400);
        api.upload(base, "spec.yaml", "openapi: 3.0.3".getBytes(StandardCharsets.UTF_8), null, token).expect(400);
    }

    @Test
    void oversizedUploadIsRejectedWith413() {
        String token = api.register("Owner");
        String project = api.createProject(token, "Large");
        byte[] big = new byte[5 * 1024 * 1024 + 10];
        java.util.Arrays.fill(big, (byte) 'a');
        var res = api.upload(BASE.formatted(project), "big.yaml", big, "v1", token).expect(413);
        assertThat(res.str("errorCode")).isEqualTo("PAYLOAD_TOO_LARGE");
    }

    @Test
    void duplicateLabelOrContentIsRejected() {
        String token = api.register("Owner");
        String project = api.createProject(token, "Dupes");
        byte[] bytes = readBytes(example("examples/orders-api/baseline.yaml"));
        byte[] other = readBytes(example("examples/orders-api/candidate-safe.yaml"));
        api.upload(BASE.formatted(project), "baseline.yaml", bytes, "v1", token).expect(201);
        assertThat(api.upload(BASE.formatted(project), "c.yaml", other, "V1", token).expect(409).str("errorCode"))
                .isEqualTo("VERSION_LABEL_TAKEN");
        assertThat(api.upload(BASE.formatted(project), "copy.yaml", bytes, "v2", token).expect(409)
                .str("errorCode")).isEqualTo("DUPLICATE_CONTENT");
    }

    @Test
    void otherUsersCannotReadUploadOrDeleteSpecs() {
        String alice = api.register("Alice");
        String mallory = api.register("Mallory");
        String project = api.createProject(alice, "Private");
        String spec = api.uploadFile(alice, project, example("examples/orders-api/baseline.yaml"), "v1");
        String path = BASE.formatted(project) + "/" + spec;

        api.get(path, mallory).expect(404);
        api.get(path + "/content", mallory).expect(404);
        api.delete(path, mallory).expect(404);
        api.upload(BASE.formatted(project), "x.yaml", readBytes(example("examples/orders-api/candidate-safe.yaml")),
                "v2", mallory).expect(404);

        // A spec id from Alice's project is not reachable through Mallory's own project either.
        String malloryProject = api.createProject(mallory, "Mine");
        api.get(BASE.formatted(malloryProject) + "/" + spec, mallory).expect(404);
        api.get(path, alice).expect(200);
    }

    @Test
    void deleteUnusedSpecification() {
        String token = api.register("Owner");
        String project = api.createProject(token, "Delete");
        String spec = api.uploadFile(token, project, example("examples/orders-api/baseline.yaml"), "v1");
        api.delete(BASE.formatted(project) + "/" + spec, token).expect(204);
        api.get(BASE.formatted(project) + "/" + spec, token).expect(404);
        assertThat(contents.findById(java.util.UUID.fromString(spec))).isEmpty();
    }

    @Test
    void ignoresClientPathInFilename() {
        String token = api.register("Owner");
        String project = api.createProject(token, "Paths");
        var res = api.upload(BASE.formatted(project), "C:\\Users\\x\\..\\orders.yaml",
                readBytes(example("examples/orders-api/baseline.yaml")), "v1", token).expect(201);
        assertThat(res.str("originalFilename")).isEqualTo("orders.yaml");
        assertThat(res.body()).doesNotContain("Users");
    }
}
