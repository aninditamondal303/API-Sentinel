import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { dashboard, emptyDashboard, page, problem, project, user } from "@/test/fixtures";
import { renderApp, signIn } from "@/test/render";
import { server } from "@/test/server";

function base() {
  signIn();
  server.use(
    http.get("*/api/v1/auth/me", () => HttpResponse.json(user)),
    http.get("*/api/v1/projects", () => HttpResponse.json(page([project]))),
  );
}

describe("DashboardPage", () => {
  it("renders the backend's figures and recent scans", async () => {
    base();
    server.use(http.get("*/api/v1/dashboard", () => HttpResponse.json(dashboard)));
    renderApp("/app");
    const breaking = (await screen.findByText("Breaking changes")).closest("div.card") as HTMLElement;
    expect(within(breaking).getByText("9")).toBeInTheDocument();
    expect(screen.getByText("4 compatibility · 3 security")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Critical 3, High 7, Medium 5, Low 0, Info 2/ })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /open compatibility scan/i })).toHaveAttribute("href", "/app/projects/p-1/scans/s-1");
  });

  it("shows empty states for a new account", async () => {
    base();
    server.use(http.get("*/api/v1/dashboard", () => HttpResponse.json(emptyDashboard)));
    renderApp("/app");
    expect(await screen.findByText("No findings yet")).toBeInTheDocument();
    expect(screen.getAllByText("No scans yet").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Create a project" })).toBeInTheDocument();
  });

  it("shows an error state with the request id", async () => {
    base();
    server.use(http.get("*/api/v1/dashboard", () => HttpResponse.json(problem(500, "INTERNAL_ERROR", "Unexpected error."), { status: 500 })));
    renderApp("/app");
    expect(await screen.findByText("Unexpected error.")).toBeInTheDocument();
    expect(screen.getByText("Request ID req-123")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
