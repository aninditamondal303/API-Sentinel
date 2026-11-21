package dev.apisentinel.common;

import java.net.URI;
import org.springframework.web.servlet.support.ServletUriComponentsBuilder;

/** Builds the Location header for 201 Created responses. */
public final class Locations {

    private Locations() {
    }

    public static URI of(String pathTemplate, Object... variables) {
        return ServletUriComponentsBuilder.fromCurrentContextPath().path(pathTemplate).buildAndExpand(variables)
                .toUri();
    }
}
