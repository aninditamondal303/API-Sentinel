import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import type { RulesResponse } from "@/api/types";
import { problem, user } from "@/test/fixtures";
import { renderApp, signIn } from "@/test/render";
import { server } from "@/test/server";

const catalogue: RulesResponse = {
  rulesetVersion: "2026.11",
  rules: [
    { id: "OP-002", title: "Operation method removed", category: "COMPATIBILITY", severity: "CRITICAL", requiresManualReview: false,
      impact: "Clients calling this method will receive 404 or 405.", remediation: "Restore the method or deprecate it first." },
    { id: "SEC-R-001", title: "Security requirement removed", category: "SECURITY_REGRESSION", severity: "HIGH", requiresManualReview: false,
      impact: "The operation becomes reachable without credentials.", remediation: "Restore the security requirement." },
    { id: "SEC-H-004", title: "Operation explicitly public", category: "SPEC_HYGIENE", severity: "LOW", requiresManualReview: true,
      impact: "An empty security list makes the operation public.", remediation: "Confirm the operation is meant to be public." },
  ],
};

function setup(response: () => Response = () => HttpResponse.json(catalogue)) {
  signIn();
  server.use(
    http.get("*/api/v1/auth/me", () => HttpResponse.json(user)),
    http.get("*/api/v1/rules", response),
  );
}

describe("RulesPage", () => {
  it("lists every rule with its severity, category, impact and fix", async () => {
    setup();
    renderApp("/app/rules");
    expect(await screen.findByText("Operation method removed")).toBeInTheDocument();
    expect(screen.getByText(/The 3 deterministic rules behind every finding \(ruleset 2026\.11\)/)).toBeInTheDocument();
    const card = screen.getByText("OP-002").closest("article")!;
    expect(within(card).getByText("Compatibility")).toBeInTheDocument();
    expect(within(card).getByText(/Clients calling this method/)).toBeInTheDocument();
    expect(within(screen.getByText("SEC-H-004").closest("article")!).getByText("Manual review")).toBeInTheDocument();
  });

  it("filters by search text and by category", async () => {
    setup();
    renderApp("/app/rules");
    await screen.findByText("Operation method removed");
    await userEvent.type(screen.getByLabelText("Search rules"), "sec-r");
    expect(screen.getByText("Security requirement removed")).toBeInTheDocument();
    expect(screen.queryByText("Operation method removed")).toBeNull();

    await userEvent.clear(screen.getByLabelText("Search rules"));
    await userEvent.selectOptions(screen.getByLabelText("Filter by category"), "SPEC_HYGIENE");
    expect(screen.getByText("Operation explicitly public")).toBeInTheDocument();
    expect(screen.queryByText("Security requirement removed")).toBeNull();

    await userEvent.type(screen.getByLabelText("Search rules"), "no such rule");
    expect(screen.getByText("No matching rules")).toBeInTheDocument();
  });

  it("highlights the rule named in the link from a finding", async () => {
    setup();
    renderApp("/app/rules#SEC-R-001");
    const card = (await screen.findByText("SEC-R-001")).closest("article")!;
    expect(card.className).toContain("ring-2");
    expect(screen.getByText("OP-002").closest("article")!.className).not.toContain("ring-2");
  });

  it("shows an error state with retry when the analyzer is unavailable", async () => {
    setup(() => HttpResponse.json(problem(503, "ANALYZER_UNAVAILABLE", "The analysis service is unavailable."), { status: 503 }));
    renderApp("/app/rules");
    expect(await screen.findByText("Could not load this data")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
