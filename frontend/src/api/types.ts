// Mirrors the Spring Boot DTOs (dev.apisentinel.*Dtos). Field names are the backend's JSON names.

export type Severity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO";
export const SEVERITIES: readonly Severity[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"];

export interface Page<T> {
  items: T[];
  page: number;
  size: number;
  totalItems: number;
  totalPages: number;
}

export interface User {
  id: string;
  email: string;
  displayName: string;
  createdAt: string;
}

export interface TokenResponse {
  accessToken: string;
  tokenType: string;
  expiresIn: number;
  user: User;
}

export interface Policy {
  failOn: Severity | null;
  failOnManualReview: boolean;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  policy: Policy;
  createdAt: string;
  updatedAt: string;
}

export interface Specification {
  id: string;
  projectId: string;
  versionLabel: string;
  originalFilename: string;
  format: "YAML" | "JSON";
  openapiVersion: string;
  title: string;
  apiVersion: string;
  operationCount: number;
  sizeBytes: number;
  sha256: string;
  uploadedAt: string;
}

export type ScanType = "COMPATIBILITY" | "SECURITY";
export type ScanStatus = "RUNNING" | "COMPLETED" | "FAILED";
export type Decision = "PASS" | "FAIL";

export interface SpecRef {
  id: string;
  versionLabel: string;
  title: string;
  apiVersion: string;
}

export interface SeverityCounts {
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
}

export interface Scan {
  id: string;
  projectId: string;
  type: ScanType;
  status: ScanStatus;
  baseline: SpecRef | null;
  target: SpecRef;
  failOn: Severity | null;
  failOnManualReview: boolean;
  decision: Decision | null;
  reasons: string[];
  totalFindings: number;
  bySeverity: SeverityCounts;
  breakingChanges: number;
  manualReview: number;
  endpointsAffected: number;
  analyzerVersion: string | null;
  rulesetVersion: string | null;
  errorCode: string | null;
  errorMessage: string | null;
  durationMs: number | null;
  createdAt: string;
  completedAt: string | null;
}

export interface Finding {
  id: string;
  position: number;
  ruleId: string;
  title: string;
  category: string;
  severity: Severity;
  requiresManualReview: boolean;
  method: string | null;
  path: string | null;
  location: string | null;
  locationDocument: string | null;
  field: string | null;
  oldValue: unknown;
  newValue: unknown;
  message: string;
  impact: string | null;
  remediation: string | null;
  fingerprint: string;
}

export interface ScanCounts {
  total: number;
  compatibility: number;
  security: number;
  completed: number;
  failed: number;
  running: number;
  passed: number;
  failedThreshold: number;
}

export interface Dashboard {
  projects: number;
  specifications: number;
  scans: ScanCounts;
  breakingChanges: number;
  severityDistribution: Record<Severity, number>;
  recentScans: Scan[];
}

export interface GeneratedOperation {
  id: string;
  method: string;
  path: string;
  operationId: string | null;
  status: string;
  skipReason: string | null;
  expectedStatuses: string[];
  inputSources: Record<string, string> | null;
  notes: string[] | null;
  requiresAuth: boolean;
}

export interface ContractTestResult {
  spec: { openapiVersion: string; title: string; apiVersion: string; operationCount: number } | null;
  summary: { total: number; ready: number; skipped: number; schemaValidated: number };
  operations: GeneratedOperation[];
  files: { path: string; content: string }[];
  runCommand: string;
}

export interface FieldIssue {
  field?: string;
  pointer?: string;
  message: string;
}
