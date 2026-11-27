package dev.apisentinel;

import static org.assertj.core.api.Assertions.assertThat;

import dev.apisentinel.support.PostgresIntegrationTest;
import dev.apisentinel.support.TestApi;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.json.JsonMapper;

/**
 * Keeps contracts/backend-api.openapi.json in step with the code, so every change to the public
 * API is visible in a pull request diff (the analyzer's contract has the same kind of test).
 *
 * <p>To regenerate after an intentional API change, run from backend/:
 * {@code ./mvnw verify -Dtest=ApiContractDriftTest -Dapisentinel.updateContract=true}
 */
class ApiContractDriftTest extends PostgresIntegrationTest {

    private static final JsonMapper JSON = JsonMapper.builder().build();
    static final Path CONTRACT = TestApi.REPO_ROOT.resolve("contracts/backend-api.openapi.json");
    /** Copy of the generated contract when the test fails, uploaded by CI for review. */
    static final Path GENERATED = Path.of("target/contract/backend-api.openapi.json");

    @Test
    void committedContractMatchesTheRunningApplication() throws IOException {
        String actual = normalize(api.get("/v3/api-docs", null).expect(200).body());

        if (Boolean.getBoolean("apisentinel.updateContract")) {
            Files.createDirectories(CONTRACT.getParent());
            Files.writeString(CONTRACT, actual, StandardCharsets.UTF_8);
            return;
        }

        String committed = Files.exists(CONTRACT)
                ? normalize(Files.readString(CONTRACT, StandardCharsets.UTF_8))
                : "";
        if (!actual.equals(committed)) {
            Files.createDirectories(GENERATED.getParent());
            Files.writeString(GENERATED, actual, StandardCharsets.UTF_8);
        }
        assertThat(actual)
                .as("contracts/backend-api.openapi.json is out of date. If the API change is intended, regenerate it "
                        + "with: ./mvnw verify -Dtest=ApiContractDriftTest -Dapisentinel.updateContract=true "
                        + "(the generated file is also written to backend/" + GENERATED + ")")
                .isEqualTo(committed);
    }

    /**
     * Stable, pretty-printed form: object keys sorted, and the "servers" entry removed because
     * springdoc fills it with the address of the running test server (a random port).
     */
    static String normalize(String json) {
        Object tree = sort(JSON.readValue(json, Object.class));
        if (tree instanceof Map<?, ?> map) {
            map.remove("servers");
        }
        return JSON.writerWithDefaultPrettyPrinter().writeValueAsString(tree).replace("\r\n", "\n") + "\n";
    }

    private static Object sort(Object node) {
        if (node instanceof Map<?, ?> map) {
            Map<String, Object> sorted = new TreeMap<>();
            map.forEach((key, value) -> sorted.put(String.valueOf(key), sort(value)));
            return sorted;
        }
        if (node instanceof List<?> list) {
            List<Object> items = new ArrayList<>(list.size());
            list.forEach(item -> items.add(sort(item)));
            return items;
        }
        return node;
    }
}
