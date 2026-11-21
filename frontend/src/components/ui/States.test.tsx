import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/api/client";
import { ErrorState } from "./States";

const renderState = (error: unknown, onRetry = vi.fn()) =>
  render(<MemoryRouter><ErrorState error={error} onRetry={onRetry} /></MemoryRouter>);

describe("ErrorState", () => {
  it("treats 404 as not found, without a retry button", () => {
    renderState(new ApiError(404, "NOT_FOUND", "Project was not found.", [], "r-1"));
    expect(screen.getByText("Not found")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to projects" })).toHaveAttribute("href", "/app/projects");
  });

  it("treats a malformed id in the URL (400 VALIDATION_FAILED) as not found", () => {
    renderState(new ApiError(400, "VALIDATION_FAILED", "Parameter 'projectId' has an invalid value."));
    expect(screen.getByText("Not found")).toBeInTheDocument();
  });

  it("offers a retry and the request id for server errors", () => {
    renderState(new ApiError(503, "ANALYZER_UNAVAILABLE", "Unavailable.", [], "r-9"));
    expect(screen.getByText("Unavailable.")).toBeInTheDocument();
    expect(screen.getByText("Request ID r-9")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
