package dev.apisentinel.rule;

import dev.apisentinel.analyzer.AnalyzerClient;
import dev.apisentinel.analyzer.AnalyzerDtos.RulesResult;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Exposes the analyzer's rule catalogue to signed-in users. The analyzer itself is internal, so
 * this is the only way the UI can show what is checked. Results are passed through unchanged;
 * analyzer failures become the usual 502/503/504 problem responses.
 */
@Tag(name = "Rules")
@RestController
@RequestMapping("/api/v1/rules")
public class RuleController {

    private final AnalyzerClient analyzer;

    public RuleController(AnalyzerClient analyzer) {
        this.analyzer = analyzer;
    }

    @GetMapping
    @Operation(summary = "List every analysis rule with its category, severity, impact and remediation")
    public RulesResult list() {
        return analyzer.rules();
    }
}
