package dev.apisentinel.support;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import tools.jackson.databind.json.JsonMapper;

/** Minimal real-HTTP client for integration tests (no mocks between the test and the server). */
public final class TestApi {

    private static final JsonMapper JSON = JsonMapper.builder().build();
    public static final Path REPO_ROOT = Path.of("..").toAbsolutePath().normalize();

    private final HttpClient http = HttpClient.newHttpClient();
    private final String baseUrl;

    public TestApi(String baseUrl) {
        this.baseUrl = baseUrl;
    }

    public record Response(int status, byte[] raw, java.net.http.HttpHeaders headers) {

        public String body() {
            return new String(raw, StandardCharsets.UTF_8);
        }

        public Object json() {
            return JSON.readValue(body(), Object.class);
        }

        public Object path(String dotted) {
            Object current = json();
            for (String part : dotted.split("\\.")) {
                if (current instanceof Map<?, ?> map) {
                    current = map.get(part);
                } else if (current instanceof List<?> list) {
                    current = list.get(Integer.parseInt(part));
                } else {
                    return null;
                }
            }
            return current;
        }

        public String str(String dotted) {
            Object value = path(dotted);
            return value == null ? null : value.toString();
        }

        public long num(String dotted) {
            return ((Number) path(dotted)).longValue();
        }

        @SuppressWarnings("unchecked")
        public List<Map<String, Object>> list(String dotted) {
            return (List<Map<String, Object>>) path(dotted);
        }

        public String header(String name) {
            return headers.firstValue(name).orElse(null);
        }

        public Response expect(int expected) {
            assertThat(status).as("HTTP status; body: %s", body()).isEqualTo(expected);
            return this;
        }
    }

    public Response get(String path, String token) {
        return send(builder(path, token).GET());
    }

    public Response delete(String path, String token) {
        return send(builder(path, token).DELETE());
    }

    public Response post(String path, Object body, String token) {
        return send(builder(path, token).header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(JSON.writeValueAsString(body))));
    }

    public Response put(String path, Object body, String token) {
        return send(builder(path, token).header("Content-Type", "application/json")
                .PUT(HttpRequest.BodyPublishers.ofString(JSON.writeValueAsString(body))));
    }

    public Response postRaw(String path, String contentType, String body, String token) {
        return send(builder(path, token).header("Content-Type", contentType)
                .POST(HttpRequest.BodyPublishers.ofString(body)));
    }

    /** multipart/form-data upload with a file part and a versionLabel field (either may be null). */
    public Response upload(String path, String filename, byte[] content, String versionLabel, String token) {
        String boundary = "----apisentinel" + UUID.randomUUID();
        ByteArrayOutputStream body = new ByteArrayOutputStream();
        try {
            if (versionLabel != null) {
                body.write(("--" + boundary + "\r\nContent-Disposition: form-data; name=\"versionLabel\"\r\n\r\n"
                        + versionLabel + "\r\n").getBytes(StandardCharsets.UTF_8));
            }
            if (content != null) {
                body.write(("--" + boundary + "\r\nContent-Disposition: form-data; name=\"file\"; filename=\""
                        + filename + "\"\r\nContent-Type: application/octet-stream\r\n\r\n")
                        .getBytes(StandardCharsets.UTF_8));
                body.write(content);
                body.write("\r\n".getBytes(StandardCharsets.UTF_8));
            }
            body.write(("--" + boundary + "--\r\n").getBytes(StandardCharsets.UTF_8));
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
        return send(builder(path, token).header("Content-Type", "multipart/form-data; boundary=" + boundary)
                .POST(HttpRequest.BodyPublishers.ofByteArray(body.toByteArray())));
    }

    // ------------------------------------------------------------- shortcuts
    public String register(String displayName) {
        String email = displayName.toLowerCase().replace(' ', '.') + "." + UUID.randomUUID() + "@example.com";
        return post("/api/v1/auth/register",
                Map.of("email", email, "password", "Correct-horse-9", "displayName", displayName), null)
                .expect(201).str("accessToken");
    }

    public String createProject(String token, String name) {
        return post("/api/v1/projects", Map.of("name", name + " " + UUID.randomUUID().toString().substring(0, 8)),
                token).expect(201).str("id");
    }

    public String uploadFile(String token, String projectId, Path file, String label) {
        return upload("/api/v1/projects/" + projectId + "/specifications", file.getFileName().toString(),
                readBytes(file), label, token).expect(201).str("id");
    }

    public static byte[] readBytes(Path file) {
        try {
            return Files.readAllBytes(file);
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    public static Path example(String relative) {
        return REPO_ROOT.resolve(relative);
    }

    private HttpRequest.Builder builder(String path, String token) {
        HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create(baseUrl + path));
        if (token != null) {
            builder.header("Authorization", "Bearer " + token);
        }
        return builder;
    }

    private Response send(HttpRequest.Builder builder) {
        try {
            HttpResponse<byte[]> response = http.send(builder.build(), HttpResponse.BodyHandlers.ofByteArray());
            return new Response(response.statusCode(), response.body(), response.headers());
        } catch (IOException e) {
            throw new IllegalStateException(e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException(e);
        }
    }
}
