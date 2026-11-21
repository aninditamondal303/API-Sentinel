import type { Finding, Severity } from "@/api/types";

const RANK: Record<Severity, number> = { INFO: 0, LOW: 1, MEDIUM: 2, HIGH: 3, CRITICAL: 4 };

export function severityRank(severity: Severity): number {
  return RANK[severity];
}

/**
 * Same definition the analyzer uses for summary.breakingChanges: a COMPATIBILITY finding of HIGH or
 * CRITICAL severity. Used only to group findings for display; counts shown come from the backend.
 */
export function isBreaking(finding: Finding): boolean {
  return finding.category === "COMPATIBILITY" && RANK[finding.severity] >= RANK.HIGH;
}

export type FindingGroup = "breaking" | "manual" | "other";

export function groupOf(finding: Finding): FindingGroup {
  if (isBreaking(finding)) return "breaking";
  if (finding.requiresManualReview) return "manual";
  return "other";
}

export function groupFindings(findings: Finding[]): Record<FindingGroup, Finding[]> {
  const groups: Record<FindingGroup, Finding[]> = { breaking: [], manual: [], other: [] };
  for (const finding of findings) groups[groupOf(finding)].push(finding);
  return groups;
}

export function categoryLabel(category: string): string {
  switch (category) {
    case "COMPATIBILITY": return "Compatibility";
    case "SECURITY_REGRESSION": return "Security";
    case "SPEC_HYGIENE": return "Spec hygiene";
    default: return category.replace(/_/g, " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
  }
}
