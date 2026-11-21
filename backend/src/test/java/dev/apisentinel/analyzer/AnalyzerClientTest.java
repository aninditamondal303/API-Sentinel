package dev.apisentinel.analyzer;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import dev.apisentinel.config.AnalyzerProperties;
import java.io.IOException;
import java.net.ServerSocket;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import tools.jackson.databind.json.JsonMapper;

class AnalyzerClientTest {

    @Test
    void refusedConnectionIsReportedAsUnavailable() throws IOException {
        int port;
        try (ServerSocket socket = new ServerSocket(0)) {
            port = socket.getLocalPort();
        } // closed: nothing listens on this port now
        AnalyzerClient client = new AnalyzerClient(new AnalyzerProperties("http://127.0.0.1:" + port, "token",
                Duration.ofSeconds(1), Duration.ofSeconds(1)), JsonMapper.builder().build());
        assertThatThrownBy(() -> client.validate("openapi: 3.0.3", "a.yaml"))
                .isInstanceOfSatisfying(AnalyzerException.class, e -> {
                    org.assertj.core.api.Assertions.assertThat(e.getStatus()).isEqualTo(HttpStatus.SERVICE_UNAVAILABLE);
                    org.assertj.core.api.Assertions.assertThat(e.getCode()).isEqualTo("ANALYZER_UNAVAILABLE");
                });
    }
}
