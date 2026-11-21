import { describe, expect, it } from "vitest";
import { jwt } from "@/test/fixtures";
import { clearSession, expiryOf, loadSession, saveSession } from "./token";

describe("session storage", () => {
  it("reads exp from the token", () => {
    const token = jwt(120);
    const exp = expiryOf(token)!;
    expect(exp).toBeGreaterThan(Date.now());
    expect(exp).toBeLessThanOrEqual(Date.now() + 121_000);
    expect(expiryOf("garbage")).toBeNull();
  });

  it("stores the session in sessionStorage, not localStorage", () => {
    saveSession(jwt(), 3600);
    expect(loadSession()?.token).toBeTruthy();
    expect(localStorage.length).toBe(0);
    clearSession();
    expect(loadSession()).toBeNull();
  });

  it("drops an expired session", () => {
    saveSession(jwt(-10), 3600);
    expect(loadSession()).toBeNull();
    expect(sessionStorage.length).toBe(0);
  });
});
