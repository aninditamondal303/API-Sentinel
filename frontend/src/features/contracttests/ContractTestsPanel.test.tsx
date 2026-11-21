import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import type { ContractTestResult } from "@/api/types";
import { problem } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/server";
import { ContractTestsPanel } from "./ContractTestsPanel";

const result: ContractTestResult = {
  spec: { openapiVersion: "3.0.3", title: "Inventory", apiVersion: "1", operationCount: 2 },
  summary: { total: 2, ready: 1, skipped: 1, schemaValidated: 1 },
  operations: [
    { id: "get-items", method: "GET", path: "/items", operationId: "listItems", status: "ready", skipReason: null, expectedStatuses: ["200"], inputSources: {}, notes: [], requiresAuth: false },
    { id: "post-items", method: "POST", path: "/items", operationId: "createItem", status: "skipped", skipReason: "Unsafe method (POST) excluded", expectedStatuses: [], inputSources: {}, notes: [], requiresAuth: true },
  ],
  files: [{ path: "test_contract.py", content: "def test_list_items():\n    pass\n" }, { path: "conftest.py", content: "# fixtures\n" }],
  runCommand: "pytest -q",
};

const base = "*/api/v1/projects/p-1/specifications/sp-1/contract-tests";

describe("ContractTestsPanel", () => {
  it("generates a preview with the chosen options", async () => {
    let url: URL | null = null;
    server.use(http.get(base, ({ request }) => { url = new URL(request.url); return HttpResponse.json(result); }));
    renderWithProviders(<ContractTestsPanel projectId="p-1" specId="sp-1" />);
    await userEvent.type(screen.getByLabelText(/Default base URL/), "https://staging.example.com");
    await userEvent.click(screen.getByRole("button", { name: "Generate preview" }));
    expect(await screen.findByText("Unsafe method (POST) excluded")).toBeInTheDocument();
    expect(screen.getByText(/def test_list_items/)).toBeInTheDocument();
    expect(screen.getByText("pytest -q")).toBeInTheDocument();
    expect(url!.searchParams.get("baseUrl")).toBe("https://staging.example.com");
    expect(url!.searchParams.get("includeUnsafeMethods")).toBe("false");
    await userEvent.click(screen.getByRole("tab", { name: /conftest.py/ }));
    expect(screen.getByText("# fixtures")).toBeInTheDocument();
  });

  it("rejects a non-http base URL without calling the backend", async () => {
    renderWithProviders(<ContractTestsPanel projectId="p-1" specId="sp-1" />);
    await userEvent.type(screen.getByLabelText(/Default base URL/), "file:///etc/passwd");
    await userEvent.click(screen.getByRole("button", { name: "Generate preview" }));
    expect(screen.getByText("Use an http:// or https:// URL.")).toBeInTheDocument();
  });

  it("downloads the backend's ZIP", async () => {
    server.use(
      http.get(base, () => HttpResponse.json(result)),
      http.get(`${base}/download`, () => new HttpResponse(new Uint8Array([80, 75, 3, 4]), {
        headers: { "Content-Type": "application/zip", "Content-Disposition": 'attachment; filename="inventory-contract-tests.zip"' } })),
    );
    const createObjectURL = vi.fn(() => "blob:mock");
    Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    renderWithProviders(<ContractTestsPanel projectId="p-1" specId="sp-1" />);
    await userEvent.click(screen.getByRole("button", { name: "Generate preview" }));
    await userEvent.click(await screen.findByRole("button", { name: "Download ZIP" }));
    expect(await screen.findByText("Downloaded inventory-contract-tests.zip.")).toBeInTheDocument();
    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(click).toHaveBeenCalledTimes(1);
  });

  it("shows backend errors from generation", async () => {
    server.use(http.get(base, () => HttpResponse.json(problem(502, "ANALYZER_ERROR", "The analysis service returned an error."), { status: 502 })));
    renderWithProviders(<ContractTestsPanel projectId="p-1" specId="sp-1" />);
    await userEvent.click(screen.getByRole("button", { name: "Generate preview" }));
    expect(await screen.findByText("The analysis service returned an error.")).toBeInTheDocument();
  });
});
