import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { compatScan, findings, project, user } from "@/test/fixtures";
import { renderApp, signIn } from "@/test/render";
import { server } from "@/test/server";

function setup(scan = compatScan, list = findings) {
  signIn();
  server.use(
    http.get("*/api/v1/auth/me", () => HttpResponse.json(user)),
    http.get("*/api/v1/projects/p-1", () => HttpResponse.json(project)),
    http.get("*/api/v1/projects/p-1/scans/s-1", () => HttpResponse.json(scan)),
    http.get("*/api/v1/projects/p-1/scans/s-1/findings", () =>
      HttpResponse.json({ items: list, page: 0, size: 200, totalItems: list.length, totalPages: 1 })),
  );
}

describe("ScanDetailPage", () => {
  it("shows the decision and opens on breaking changes with impact and remediation", async () => {
    setup();
    renderApp("/app/projects/p-1/scans/s-1");
    expect(await screen.findByText(/Failed: this change does not meet/)).toBeInTheDocument();
    expect(screen.getByText("1 finding at or above HIGH")).toBeInTheDocument();
    expect(await screen.findByText("Operation removed")).toBeInTheDocument();
    expect(screen.getByText("Clients calling it receive 404.")).toBeInTheDocument();
    expect(screen.getByText("Deprecate before removing.")).toBeInTheDocument();
    expect(screen.queryByText("Enum value added to response")).not.toBeInTheDocument();
  });

  it("separates manual-review findings from breaking changes", async () => {
    setup();
    renderApp("/app/projects/p-1/scans/s-1");
    await userEvent.click(await screen.findByRole("tab", { name: /Manual review/ }));
    expect(screen.getByText("Enum value added to response")).toBeInTheDocument();
    expect(screen.queryByText("Operation removed")).not.toBeInTheDocument();
  });

  it("filters findings by severity", async () => {
    setup();
    renderApp("/app/projects/p-1/scans/s-1");
    await userEvent.click(await screen.findByRole("tab", { name: /^All/ }));
    await userEvent.selectOptions(screen.getByLabelText("Filter by severity"), "INFO");
    expect(screen.getByText("Operation added")).toBeInTheDocument();
    expect(screen.queryByText("Operation removed")).not.toBeInTheDocument();
  });

  it("labels security scans as specification-level analysis", async () => {
    setup({ ...compatScan, type: "SECURITY", baseline: null, decision: "PASS", reasons: [] }, []);
    renderApp("/app/projects/p-1/scans/s-1");
    expect(await screen.findByRole("heading", { name: "Security analysis" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("not a penetration test");
  });

  it("explains a scan that failed in the analyzer", async () => {
    setup({ ...compatScan, status: "FAILED", decision: null, errorCode: "ANALYZER_TIMEOUT", errorMessage: "The analysis took too long." }, []);
    renderApp("/app/projects/p-1/scans/s-1");
    expect(await screen.findByText("The scan could not be completed")).toBeInTheDocument();
    expect(screen.getByText("ANALYZER_TIMEOUT")).toBeInTheDocument();
  });
});
