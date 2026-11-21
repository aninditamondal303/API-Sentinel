import type { Dashboard, Finding, Project, Scan, Specification, TokenResponse, User } from "@/api/types";

// Shapes follow the backend DTOs (see api/types.ts); values are test data for unit tests only.
export const user: User = { id: "u-1", email: "ada@example.com", displayName: "Ada Lovelace", createdAt: "2026-11-21T10:00:00Z" };

export function jwt(expSecondsFromNow = 3600): string {
  const b64 = (o: object) => btoa(JSON.stringify(o)).replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
  return `${b64({ alg: "HS256" })}.${b64({ sub: user.id, exp: Math.floor(Date.now() / 1000) + expSecondsFromNow })}.signature`;
}

export const tokenResponse = (): TokenResponse => ({ accessToken: jwt(), tokenType: "Bearer", expiresIn: 3600, user });

export const project: Project = {
  id: "p-1", name: "Orders API", description: "Order management", createdAt: "2026-11-21T10:00:00Z", updatedAt: "2026-11-21T10:00:00Z",
  policy: { failOn: "HIGH", failOnManualReview: true },
};

export const spec = (id: string, label: string): Specification => ({
  id, projectId: "p-1", versionLabel: label, originalFilename: `${label}.yaml`, format: "YAML", openapiVersion: "3.0.3",
  title: "Orders API", apiVersion: "1.0.0", operationCount: 4, sizeBytes: 2048, sha256: "a".repeat(64), uploadedAt: "2026-11-21T10:00:00Z",
});

export const compatScan: Scan = {
  id: "s-1", projectId: "p-1", type: "COMPATIBILITY", status: "COMPLETED",
  baseline: { id: "sp-1", versionLabel: "v1", title: "Orders API", apiVersion: "1.0.0" },
  target: { id: "sp-2", versionLabel: "v2", title: "Orders API", apiVersion: "2.0.0" },
  failOn: "HIGH", failOnManualReview: true, decision: "FAIL", reasons: ["1 finding at or above HIGH"],
  totalFindings: 3, bySeverity: { critical: 1, high: 0, medium: 1, low: 0, info: 1 }, breakingChanges: 1, manualReview: 1,
  endpointsAffected: 2, analyzerVersion: "0.2.0", rulesetVersion: "2026.11", errorCode: null, errorMessage: null, durationMs: 42,
  createdAt: "2026-11-21T10:05:00Z", completedAt: "2026-11-21T10:05:00Z",
};

const finding = (overrides: Partial<Finding>): Finding => ({
  id: "f", position: 0, ruleId: "R-000", title: "Title", category: "COMPATIBILITY", severity: "INFO", requiresManualReview: false,
  method: "GET", path: "/orders", location: null, locationDocument: null, field: null, oldValue: null, newValue: null,
  message: "Message", impact: null, remediation: null, fingerprint: "0123456789abcdef", ...overrides,
});

export const findings: Finding[] = [
  finding({ id: "f-1", position: 0, ruleId: "OP-001", title: "Operation removed", severity: "CRITICAL", method: "DELETE", path: "/orders/{id}",
    message: "DELETE /orders/{id} was removed.", impact: "Clients calling it receive 404.", remediation: "Deprecate before removing." }),
  finding({ id: "f-2", position: 1, ruleId: "SC-010", title: "Enum value added to response", severity: "MEDIUM", requiresManualReview: true }),
  finding({ id: "f-3", position: 2, ruleId: "OP-100", title: "Operation added", severity: "INFO", path: "/health" }),
];

export const dashboard: Dashboard = {
  projects: 2, specifications: 5,
  scans: { total: 7, compatibility: 4, security: 3, completed: 6, failed: 1, running: 0, passed: 2, failedThreshold: 4 },
  breakingChanges: 9, severityDistribution: { CRITICAL: 3, HIGH: 7, MEDIUM: 5, LOW: 0, INFO: 2 },
  recentScans: [compatScan],
};

export const emptyDashboard: Dashboard = {
  projects: 0, specifications: 0,
  scans: { total: 0, compatibility: 0, security: 0, completed: 0, failed: 0, running: 0, passed: 0, failedThreshold: 0 },
  breakingChanges: 0, severityDistribution: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 }, recentScans: [],
};

export const page = <T,>(items: T[]) => ({ items, page: 0, size: 100, totalItems: items.length, totalPages: items.length ? 1 : 0 });

export const problem = (status: number, errorCode: string, detail: string, extra: object = {}) => ({
  type: "about:blank", title: "Error", status, detail, errorCode, requestId: "req-123", ...extra,
});
