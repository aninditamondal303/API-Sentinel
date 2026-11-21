import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { server } from "@/test/server";
import { ApiError, configureAuth, filenameFrom, request } from "./client";

describe("request()", () => {
  it("sends the bearer token and parses JSON", async () => {
    configureAuth(() => "tok-1", () => {});
    server.use(http.get("/api/v1/thing", ({ request: req }) =>
      HttpResponse.json({ auth: req.headers.get("Authorization") })));
    await expect(request<{ auth: string }>("/api/v1/thing")).resolves.toEqual({ auth: "Bearer tok-1" });
  });

  it("turns problem+json into ApiError with code, field errors and request id", async () => {
    configureAuth(() => null, () => {});
    server.use(http.post("/api/v1/x", () => HttpResponse.json(
      { status: 422, detail: "Spec invalid", errorCode: "SPEC_INVALID", requestId: "r-9", errors: [{ pointer: "/info", message: "version is required" }] },
      { status: 422, headers: { "Content-Type": "application/problem+json" } })));
    const error = await request("/api/v1/x", { method: "POST", body: {} }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 422, code: "SPEC_INVALID", message: "Spec invalid", requestId: "r-9" });
    expect((error as ApiError).errors[0]).toEqual({ pointer: "/info", message: "version is required" });
  });

  it("reports an expired session on 401 but not for anonymous calls", async () => {
    const onUnauthorized = vi.fn();
    configureAuth(() => "stale", onUnauthorized);
    server.use(http.get("/api/v1/me", () => HttpResponse.json({ errorCode: "UNAUTHENTICATED" }, { status: 401 })));
    await expect(request("/api/v1/me")).rejects.toMatchObject({ status: 401 });
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    await expect(request("/api/v1/me", { anonymous: true })).rejects.toMatchObject({ status: 401 });
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it("uses a friendly message for gateway errors without a detail", async () => {
    configureAuth(() => null, () => {});
    server.use(http.get("/api/v1/y", () => new HttpResponse(null, { status: 503 })));
    await expect(request("/api/v1/y")).rejects.toMatchObject({ status: 503, code: "HTTP_503", message: expect.stringContaining("unavailable") });
  });

  it("maps a network failure to status 0", async () => {
    configureAuth(() => null, () => {});
    server.use(http.get("/api/v1/z", () => HttpResponse.error()));
    await expect(request("/api/v1/z")).rejects.toMatchObject({ status: 0, code: "NETWORK_ERROR" });
  });

  it("returns undefined for 204", async () => {
    configureAuth(() => null, () => {});
    server.use(http.delete("/api/v1/p", () => new HttpResponse(null, { status: 204 })));
    await expect(request("/api/v1/p", { method: "DELETE" })).resolves.toBeUndefined();
  });
});

describe("filenameFrom()", () => {
  it("reads plain and RFC 5987 filenames and strips paths", () => {
    expect(filenameFrom('attachment; filename="scan-1.json"', "x")).toBe("scan-1.json");
    expect(filenameFrom("attachment; filename*=UTF-8''orders%20api.yaml", "x")).toBe("orders api.yaml");
    expect(filenameFrom('attachment; filename="../../evil.sh"', "x")).toBe("evil.sh");
    expect(filenameFrom('attachment; filename=".hidden"', "fallback.zip")).toBe("fallback.zip");
    expect(filenameFrom(null, "fallback.zip")).toBe("fallback.zip");
  });
});
