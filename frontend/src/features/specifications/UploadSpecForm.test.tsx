import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { problem, spec } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/server";
import { UploadSpecForm } from "./UploadSpecForm";

const yaml = (name = "baseline.yaml") => new File(["openapi: 3.0.3\n"], name, { type: "application/yaml" });

describe("UploadSpecForm", () => {
  it("sends multipart file + versionLabel and reports success", async () => {
    // Inspect the FormData the client hands to fetch (jsdom's File loses its name once Node serializes it).
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    server.use(http.post("*/api/v1/projects/p-1/specifications", () => HttpResponse.json(spec("sp-9", "v1.0.0"), { status: 201 })));
    const onUploaded = vi.fn();
    renderWithProviders(<UploadSpecForm projectId="p-1" onUploaded={onUploaded} />);
    await userEvent.upload(screen.getByLabelText("Specification file"), yaml());
    await userEvent.type(screen.getByLabelText("Version label"), "v1.0.0");
    await userEvent.click(screen.getByRole("button", { name: /validate & upload/i }));
    await vi.waitFor(() => expect(onUploaded).toHaveBeenCalledWith(expect.objectContaining({ id: "sp-9" })));
    const [url, init] = fetchSpy.mock.calls.at(-1)!;
    expect(String(url)).toMatch(/\/api\/v1\/projects\/p-1\/specifications$/);
    expect(init?.method).toBe("POST");
    const form = init?.body as FormData;
    expect(form.get("versionLabel")).toBe("v1.0.0");
    expect((form.get("file") as File).name).toBe("baseline.yaml");
    // The browser sets the multipart boundary; the client must not force a Content-Type.
    expect((init?.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
  });

  it("rejects unsupported files before uploading", async () => {
    renderWithProviders(<UploadSpecForm projectId="p-1" onUploaded={vi.fn()} />);
    await userEvent.upload(screen.getByLabelText("Specification file"), new File(["x"], "notes.txt"), { applyAccept: false });
    expect(screen.getByText("Choose a .yaml, .yml or .json OpenAPI file.")).toBeInTheDocument();
  });

  it("shows the analyzer's validation issues on 422", async () => {
    server.use(http.post("*/api/v1/projects/p-1/specifications", () => HttpResponse.json(
      problem(422, "SPEC_INVALID", "The document is not a valid OpenAPI 3.x specification.",
        { errors: [{ pointer: "/info", message: "'version' is a required property" }] }), { status: 422 })));
    renderWithProviders(<UploadSpecForm projectId="p-1" onUploaded={vi.fn()} />);
    await userEvent.upload(screen.getByLabelText("Specification file"), yaml("broken.yaml"));
    await userEvent.type(screen.getByLabelText("Version label"), "v1");
    await userEvent.click(screen.getByRole("button", { name: /validate & upload/i }));
    expect(await screen.findByText("The document is not a valid OpenAPI 3.x specification.")).toBeInTheDocument();
    expect(screen.getByText("Validation issues reported by the analyzer")).toBeInTheDocument();
    expect(screen.getByText("'version' is a required property")).toBeInTheDocument();
    expect(screen.getByText("/info")).toBeInTheDocument();
  });

  it("shows a duplicate version label next to the field", async () => {
    server.use(http.post("*/api/v1/projects/p-1/specifications", () => HttpResponse.json(
      problem(409, "VERSION_LABEL_TAKEN", "This project already has a specification labelled 'v1'."), { status: 409 })));
    renderWithProviders(<UploadSpecForm projectId="p-1" onUploaded={vi.fn()} />);
    await userEvent.upload(screen.getByLabelText("Specification file"), yaml());
    await userEvent.type(screen.getByLabelText("Version label"), "v1");
    await userEvent.click(screen.getByRole("button", { name: /validate & upload/i }));
    expect(await screen.findByText("This project already has a specification labelled 'v1'.")).toBeInTheDocument();
  });
});
