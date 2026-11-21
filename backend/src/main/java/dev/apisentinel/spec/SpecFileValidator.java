package dev.apisentinel.spec;

import dev.apisentinel.common.ApiException;
import dev.apisentinel.spec.ApiSpecification.Format;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.regex.Pattern;
import org.springframework.http.HttpStatus;

/**
 * First line of defence for uploads, before anything is sent to the analyzer: file name, extension,
 * size and encoding. The declared Content-Type is ignored because clients control it.
 */
public final class SpecFileValidator {

    private static final Pattern UNSAFE_NAME_CHARS = Pattern.compile("[^A-Za-z0-9._ -]");
    private static final int MAX_NAME_LENGTH = 255;

    private SpecFileValidator() {
    }

    public record ValidFile(String filename, Format format, String content) {
    }

    public static ValidFile validate(String originalFilename, byte[] bytes, int maxBytes) {
        String filename = sanitizeFilename(originalFilename);
        Format format = formatOf(filename);
        if (bytes.length == 0) {
            throw ApiException.badRequest("EMPTY_FILE", "The uploaded file is empty.");
        }
        if (bytes.length > maxBytes) {
            throw new ApiException(HttpStatus.CONTENT_TOO_LARGE, "PAYLOAD_TOO_LARGE",
                    "The uploaded file exceeds the " + maxBytes + "-byte limit.");
        }
        String content = decodeUtf8(bytes);
        if (content.indexOf('\u0000') >= 0) {
            throw ApiException.badRequest("INVALID_ENCODING", "The file contains NUL bytes; it is not a text file.");
        }
        return new ValidFile(filename, format, content);
    }

    static String sanitizeFilename(String original) {
        if (original == null || original.isBlank()) {
            throw ApiException.badRequest("INVALID_FILENAME", "The uploaded file must have a name.");
        }
        // Keep only the last path segment: browsers on Windows may send full client paths.
        String name = original.replace('\\', '/');
        name = name.substring(name.lastIndexOf('/') + 1).trim();
        name = UNSAFE_NAME_CHARS.matcher(name).replaceAll("_");
        if (name.isEmpty() || name.startsWith(".")) {
            throw ApiException.badRequest("INVALID_FILENAME", "The uploaded file name is not valid.");
        }
        return name.length() > MAX_NAME_LENGTH ? name.substring(name.length() - MAX_NAME_LENGTH) : name;
    }

    static Format formatOf(String filename) {
        String lower = filename.toLowerCase(Locale.ROOT);
        if (lower.endsWith(".yaml") || lower.endsWith(".yml")) {
            return Format.YAML;
        }
        if (lower.endsWith(".json")) {
            return Format.JSON;
        }
        throw new ApiException(HttpStatus.UNSUPPORTED_MEDIA_TYPE, "UNSUPPORTED_FILE_TYPE",
                "Only .yaml, .yml and .json OpenAPI files are accepted.");
    }

    static String decodeUtf8(byte[] bytes) {
        try {
            String text = StandardCharsets.UTF_8.newDecoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .decode(ByteBuffer.wrap(bytes))
                    .toString();
            return text.startsWith("﻿") ? text.substring(1) : text;
        } catch (CharacterCodingException e) {
            throw ApiException.badRequest("INVALID_ENCODING", "The file must be UTF-8 encoded text.");
        }
    }
}
