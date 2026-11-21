package dev.apisentinel.spec;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import dev.apisentinel.common.ApiException;
import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;

class SpecFileValidatorTest {

    private static final byte[] YAML = "openapi: 3.0.3\n".getBytes(StandardCharsets.UTF_8);

    private static String code(Runnable r) {
        try {
            r.run();
        } catch (ApiException e) {
            return e.getCode();
        }
        throw new AssertionError("expected ApiException");
    }

    @Test
    void acceptsYamlYmlAndJson() {
        assertThat(SpecFileValidator.validate("a.yaml", YAML, 100).format()).isEqualTo(ApiSpecification.Format.YAML);
        assertThat(SpecFileValidator.validate("a.YML", YAML, 100).format()).isEqualTo(ApiSpecification.Format.YAML);
        assertThat(SpecFileValidator.validate("a.json", "{}".getBytes(StandardCharsets.UTF_8), 100).format())
                .isEqualTo(ApiSpecification.Format.JSON);
    }

    @Test
    void stripsClientPathsAndUnsafeCharacters() {
        assertThat(SpecFileValidator.sanitizeFilename("C:\\Users\\me\\orders api.yaml")).isEqualTo("orders api.yaml");
        assertThat(SpecFileValidator.sanitizeFilename("../../etc/x<y>.yaml")).isEqualTo("x_y_.yaml");
        assertThat(code(() -> SpecFileValidator.sanitizeFilename("../.hidden.yaml"))).isEqualTo("INVALID_FILENAME");
        assertThat(code(() -> SpecFileValidator.sanitizeFilename(" "))).isEqualTo("INVALID_FILENAME");
    }

    @Test
    void rejectsBadFiles() {
        assertThat(code(() -> SpecFileValidator.validate("a.txt", YAML, 100))).isEqualTo("UNSUPPORTED_FILE_TYPE");
        assertThat(code(() -> SpecFileValidator.validate("a.yaml", new byte[0], 100))).isEqualTo("EMPTY_FILE");
        assertThat(code(() -> SpecFileValidator.validate("a.yaml", YAML, 5))).isEqualTo("PAYLOAD_TOO_LARGE");
        assertThat(code(() -> SpecFileValidator.validate("a.yaml", new byte[] {(byte) 0xFF, 0x41}, 100)))
                .isEqualTo("INVALID_ENCODING");
        assertThat(code(() -> SpecFileValidator.validate("a.yaml", new byte[] {0x41, 0x00, 0x42}, 100)))
                .isEqualTo("INVALID_ENCODING");
    }

    @Test
    void tooLargeIs413() {
        assertThatThrownBy(() -> SpecFileValidator.validate("a.yaml", YAML, 5))
                .isInstanceOfSatisfying(ApiException.class,
                        e -> assertThat(e.getStatus()).isEqualTo(HttpStatus.CONTENT_TOO_LARGE));
    }

    @Test
    void stripsUtf8Bom() {
        byte[] withBom = {(byte) 0xEF, (byte) 0xBB, (byte) 0xBF, 'o', 'k'};
        assertThat(SpecFileValidator.validate("a.yaml", withBom, 100).content()).isEqualTo("ok");
    }
}
