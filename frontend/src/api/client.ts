import type { FieldIssue } from "./types";

/** An RFC 9457 problem returned by the backend (or a transport failure, status 0). */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly errors: FieldIssue[];
  readonly requestId: string | null;
  readonly scanId: string | null;

  constructor(status: number, code: string, message: string, errors: FieldIssue[] = [],
      requestId: string | null = null, scanId: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.errors = errors;
    this.requestId = requestId;
    this.scanId = scanId;
  }
}

type TokenProvider = () => string | null;
type UnauthorizedHandler = () => void;

let tokenProvider: TokenProvider = () => null;
let onUnauthorized: UnauthorizedHandler = () => {};

/** Wired by AuthProvider: the client never reads storage itself. */
export function configureAuth(provider: TokenProvider, unauthorized: UnauthorizedHandler): void {
  tokenProvider = provider;
  onUnauthorized = unauthorized;
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  form?: FormData;
  signal?: AbortSignal;
  /** Do not treat 401 as an expired session (used by login itself). */
  anonymous?: boolean;
}

const FALLBACK_MESSAGES: Record<number, string> = {
  0: "Cannot reach the API Sentinel server. Check that the backend is running.",
  401: "Your session has expired. Please sign in again.",
  403: "You do not have access to this resource.",
  404: "The requested resource was not found.",
  413: "The file is too large.",
  429: "Too many attempts. Please wait a few minutes and try again.",
  502: "The analysis service returned an error. Please try again.",
  503: "The analysis service is unavailable right now. Please try again shortly.",
  504: "The analysis took too long and was stopped.",
};

async function send(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json, application/problem+json, */*" };
  const token = options.anonymous ? null : tokenProvider();
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (options.form) {
    body = options.form;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }
  let response: Response;
  try {
    response = await fetch(new URL(path, window.location.origin).toString(), { method: options.method ?? "GET", headers, body, signal: options.signal,
      credentials: "same-origin" });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "NETWORK_ERROR", FALLBACK_MESSAGES[0]!);
  }
  if (!response.ok) {
    throw await toApiError(response, Boolean(options.anonymous));
  }
  return response;
}

async function toApiError(response: Response, anonymous: boolean): Promise<ApiError> {
  let problem: Record<string, unknown> = {};
  try {
    const text = await response.text();
    problem = text ? (JSON.parse(text) as Record<string, unknown>) : {};
  } catch {
    problem = {};
  }
  if (response.status === 401 && !anonymous) onUnauthorized();
  const code = typeof problem.errorCode === "string" ? problem.errorCode : `HTTP_${response.status}`;
  const detail = typeof problem.detail === "string" && problem.detail ? problem.detail
    : FALLBACK_MESSAGES[response.status] ?? `Request failed (HTTP ${response.status}).`;
  const errors = Array.isArray(problem.errors) ? (problem.errors as FieldIssue[]) : [];
  const requestId = typeof problem.requestId === "string" ? problem.requestId
    : response.headers.get("X-Request-Id");
  const scanId = typeof problem.scanId === "string" ? problem.scanId : null;
  return new ApiError(response.status, code, detail, errors, requestId, scanId);
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await send(path, options);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export interface Download {
  blob: Blob;
  filename: string;
}

/** Fetches a binary attachment with the bearer token (a plain <a href> could not send it). */
export async function download(path: string, fallbackName: string): Promise<Download> {
  const response = await send(path, {});
  return { blob: await response.blob(), filename: filenameFrom(response.headers.get("Content-Disposition"), fallbackName) };
}

export function filenameFrom(disposition: string | null, fallback: string): string {
  if (!disposition) return fallback;
  const star = /filename\*=(?:UTF-8'')?([^;]+)/i.exec(disposition);
  if (star?.[1]) {
    try {
      return sanitize(decodeURIComponent(star[1].trim().replace(/^"|"$/g, "")), fallback);
    } catch {
      /* fall through */
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(disposition);
  return plain?.[1] ? sanitize(plain[1].trim(), fallback) : fallback;
}

function sanitize(name: string, fallback: string): string {
  const base = name.split(/[\\/]/).pop() ?? "";
  return base && !base.startsWith(".") ? base : fallback;
}

export function saveBlob({ blob, filename }: Download): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
