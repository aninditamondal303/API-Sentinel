package dev.apisentinel.rule;

import static org.assertj.core.api.Assertions.assertThat;

import dev.apisentinel.support.FullStackIntegrationTest;
import dev.apisentinel.support.TestContainers;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.json.JsonMapper;

class RuleIntegrationTest extends FullStackIntegrationTest {

    @Test
    void requiresAuthentication() {
        api.get("/api/v1/rules", null).expect(401);
    }

    @Test
    void returnsTheAnalyzersRuleCatalogueUnchanged() throws IOException, InterruptedException {
        var response = api.get("/api/v1/rules", api.register("Rules")).expect(200);
        List<Map<String, Object>> rules = response.list("rules");

        Map<?, ?> fromAnalyzer = analyzerCatalogue();
        assertThat(response.str("rulesetVersion")).isNotBlank().isEqualTo(fromAnalyzer.get("rulesetVersion"));
        assertThat(rules).hasSize(((List<?>) fromAnalyzer.get("rules")).size());
        assertThat(rules).extracting(r -> r.get("id")).doesNotHaveDuplicates().contains("OP-002");
        assertThat(rules).allSatisfy(rule -> assertThat(rule).containsKeys(
                "id", "title", "category", "severity", "requiresManualReview", "impact", "remediation"));
    }

    /** Reads GET /internal/v1/rules straight from the analyzer container, for comparison. */
    private static Map<?, ?> analyzerCatalogue() throws IOException, InterruptedException {
        HttpRequest request = HttpRequest.newBuilder(URI.create(TestContainers.analyzerUrl() + "/internal/v1/rules"))
                .header("X-Internal-Token", TestContainers.INTERNAL_TOKEN)
                .GET()
                .build();
        HttpResponse<String> response = HttpClient.newHttpClient().send(request, HttpResponse.BodyHandlers.ofString());
        assertThat(response.statusCode()).isEqualTo(200);
        return JsonMapper.builder().build().readValue(response.body(), Map.class);
    }
}
