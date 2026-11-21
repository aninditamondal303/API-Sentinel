package dev.apisentinel.scan;

public enum ScanType {
    /** Baseline vs candidate breaking-change analysis. */
    COMPATIBILITY,
    /** Single-specification security hygiene checks. */
    SECURITY
}
