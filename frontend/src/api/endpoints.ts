import { download, request } from "./client";
import type {
  ContractTestResult, Dashboard, Finding, Page, Policy, Project, Scan, ScanStatus, ScanType, Severity,
  Specification, TokenResponse, User,
} from "./types";

const enc = encodeURIComponent;

function query(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const authApi = {
  register: (body: { email: string; password: string; displayName: string }) =>
    request<TokenResponse>("/api/v1/auth/register", { method: "POST", body, anonymous: true }),
  login: (body: { email: string; password: string }) =>
    request<TokenResponse>("/api/v1/auth/login", { method: "POST", body, anonymous: true }),
  me: () => request<User>("/api/v1/auth/me"),
};

export const dashboardApi = {
  get: () => request<Dashboard>("/api/v1/dashboard"),
};

export const projectApi = {
  list: (page = 0, size = 100) => request<Page<Project>>(`/api/v1/projects${query({ page, size })}`),
  get: (id: string) => request<Project>(`/api/v1/projects/${enc(id)}`),
  create: (body: { name: string; description?: string }) =>
    request<Project>("/api/v1/projects", { method: "POST", body }),
  update: (id: string, body: { name: string; description?: string | null }) =>
    request<Project>(`/api/v1/projects/${enc(id)}`, { method: "PUT", body }),
  remove: (id: string) => request<void>(`/api/v1/projects/${enc(id)}`, { method: "DELETE" }),
  updatePolicy: (id: string, body: Policy) =>
    request<Policy>(`/api/v1/projects/${enc(id)}/policy`, { method: "PUT", body }),
};

const specBase = (projectId: string) => `/api/v1/projects/${enc(projectId)}/specifications`;

export const specApi = {
  list: (projectId: string, page = 0, size = 100) =>
    request<Page<Specification>>(`${specBase(projectId)}${query({ page, size })}`),
  get: (projectId: string, specId: string) => request<Specification>(`${specBase(projectId)}/${enc(specId)}`),
  upload: (projectId: string, file: File, versionLabel: string) => {
    const form = new FormData();
    form.append("versionLabel", versionLabel);
    form.append("file", file, file.name);
    return request<Specification>(specBase(projectId), { method: "POST", form });
  },
  remove: (projectId: string, specId: string) =>
    request<void>(`${specBase(projectId)}/${enc(specId)}`, { method: "DELETE" }),
  content: (projectId: string, specId: string, fallback: string) =>
    download(`${specBase(projectId)}/${enc(specId)}/content`, fallback),
};

const scanBase = (projectId: string) => `/api/v1/projects/${enc(projectId)}/scans`;

export interface CompatibilityScanRequest {
  baselineSpecificationId: string;
  candidateSpecificationId: string;
  useProjectPolicy: boolean;
  failOn?: Severity | null;
  failOnManualReview?: boolean;
}

export interface SecurityScanRequest {
  specificationId: string;
  useProjectPolicy: boolean;
  failOn?: Severity | null;
}

export const scanApi = {
  list: (projectId: string, filters: { type?: ScanType; status?: ScanStatus; page?: number; size?: number } = {}) =>
    request<Page<Scan>>(`${scanBase(projectId)}${query({ size: 20, ...filters })}`),
  get: (projectId: string, scanId: string) => request<Scan>(`${scanBase(projectId)}/${enc(scanId)}`),
  compatibility: (projectId: string, body: CompatibilityScanRequest) =>
    request<Scan>(`${scanBase(projectId)}/compatibility`, { method: "POST", body }),
  security: (projectId: string, body: SecurityScanRequest) =>
    request<Scan>(`${scanBase(projectId)}/security`, { method: "POST", body }),
  findings: (projectId: string, scanId: string, page = 0, size = 200) =>
    request<Page<Finding>>(`${scanBase(projectId)}/${enc(scanId)}/findings${query({ page, size })}`),
  /** Every finding of a scan, in analyzer order (pages of 200, the backend maximum). */
  allFindings: async (projectId: string, scanId: string): Promise<Finding[]> => {
    const all: Finding[] = [];
    for (let page = 0; ; page++) {
      const result = await scanApi.findings(projectId, scanId, page, 200);
      all.push(...result.items);
      if (page + 1 >= result.totalPages) return all;
    }
  },
  report: (projectId: string, scanId: string) =>
    download(`${scanBase(projectId)}/${enc(scanId)}/report`, `scan-${scanId}.json`),
};

export interface ContractTestOptions {
  includeUnsafeMethods: boolean;
  baseUrl?: string;
}

const contractBase = (projectId: string, specId: string) => `${specBase(projectId)}/${enc(specId)}/contract-tests`;

export const contractTestApi = {
  preview: (projectId: string, specId: string, options: ContractTestOptions) =>
    request<ContractTestResult>(`${contractBase(projectId, specId)}${query({ ...options })}`),
  download: (projectId: string, specId: string, options: ContractTestOptions) =>
    download(`${contractBase(projectId, specId)}/download${query({ ...options })}`, "contract-tests.zip"),
};
