import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { emptyDashboard, page, tokenResponse, user } from "@/test/fixtures";
import { renderApp, signIn } from "@/test/render";
import { server } from "@/test/server";

describe("AppShell", () => {
  it("renders each logo with its own gradient id, referenced by that same SVG", async () => {
    signIn();
    server.use(
      http.get("*/api/v1/auth/me", () => HttpResponse.json(user)),
      http.get("*/api/v1/dashboard", () => HttpResponse.json(emptyDashboard)),
      http.get("*/api/v1/projects", () => HttpResponse.json(page([]))),
    );
    const { container } = renderApp("/app");
    // Sidebar logo (desktop) + header logo (mobile) are both in the DOM once the shell renders.
    await waitFor(() => expect(container.querySelectorAll("svg linearGradient").length).toBeGreaterThanOrEqual(2));
    const gradients = [...container.querySelectorAll("svg linearGradient")];
    const ids = gradients.map((g) => g.id);
    expect(ids.every((id) => id.length > 0)).toBe(true);
    expect(new Set(ids).size).toBe(ids.length);
    for (const gradient of gradients) {
      const svg = gradient.closest("svg")!;
      const strokes = [...svg.querySelectorAll("[stroke^='url(']")].map((el) => el.getAttribute("stroke"));
      expect(strokes).toEqual([`url(#${gradient.id})`]);
    }
  });

  it("signs out to the login page without a stale next= parameter", async () => {
    signIn();
    server.use(
      http.get("*/api/v1/auth/me", () => HttpResponse.json(user)),
      http.get("*/api/v1/dashboard", () => HttpResponse.json(emptyDashboard)),
      http.get("*/api/v1/projects", () => HttpResponse.json(page([]))),
      http.post("*/api/v1/auth/login", () => HttpResponse.json(tokenResponse())),
    );
    renderApp("/app/projects");
    await screen.findByRole("heading", { name: "Projects" });
    await userEvent.click(screen.getAllByRole("button", { name: "Sign out" })[0]!);
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
    await waitFor(() => expect(sessionStorage.getItem("apisentinel.session")).toBeNull());
    expect(screen.queryByText("Your session ended. Please sign in again.")).not.toBeInTheDocument();
    // Signing in again must open the dashboard, not the page that was open before sign-out
    // (a stale ?next=/app/projects would send the user back to Projects).
    await userEvent.type(screen.getByLabelText("Email"), "ada@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "Correct-horse-9");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("heading", { name: /Welcome, Ada/ })).toBeInTheDocument();
  });

  it("returns to the original page after an expired session is renewed", async () => {
    let meCalls = 0;
    signIn();
    server.use(
      // First /me (session restore) is rejected: the stored token has expired server-side.
      http.get("*/api/v1/auth/me", () => (meCalls++ === 0
        ? HttpResponse.json({ errorCode: "UNAUTHENTICATED" }, { status: 401 })
        : HttpResponse.json(user))),
      http.get("*/api/v1/projects", () => HttpResponse.json(page([]))),
      http.post("*/api/v1/auth/login", () => HttpResponse.json(tokenResponse())),
    );
    renderApp("/app/projects");
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Email"), "ada@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "Correct-horse-9");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("heading", { name: "Projects" })).toBeInTheDocument();
  });
});
