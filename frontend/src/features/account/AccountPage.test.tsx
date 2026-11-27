import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { problem, user } from "@/test/fixtures";
import { renderApp, signIn } from "@/test/render";
import { server } from "@/test/server";

async function fill(current: string, next: string, confirm = next) {
  await userEvent.type(await screen.findByLabelText("Current password"), current);
  await userEvent.type(screen.getByLabelText("New password"), next);
  await userEvent.type(screen.getByLabelText("Confirm new password"), confirm);
  await userEvent.click(screen.getByRole("button", { name: "Change password" }));
}

function setup() {
  signIn();
  server.use(http.get("*/api/v1/auth/me", () => HttpResponse.json(user)));
}

describe("AccountPage", () => {
  it("changes the password and clears the form", async () => {
    setup();
    let body: unknown;
    server.use(http.post("*/api/v1/auth/password", async ({ request }) => {
      body = await request.json();
      return new HttpResponse(null, { status: 204 });
    }));
    renderApp("/app/account");
    expect(await screen.findByText(user.email)).toBeInTheDocument();
    await fill("Correct-horse-9", "Battery-staple-7");
    expect(await screen.findByText(/Password changed/)).toBeInTheDocument();
    expect(body).toEqual({ currentPassword: "Correct-horse-9", newPassword: "Battery-staple-7" });
    expect(screen.getByLabelText("Current password")).toHaveValue("");
  });

  it("validates before calling the backend", async () => {
    setup();
    renderApp("/app/account");
    await fill("Correct-horse-9", "short", "different");
    expect(screen.getByText("Use 8 to 128 characters.")).toBeInTheDocument();
    expect(screen.getByText("Passwords do not match.")).toBeInTheDocument();
  });

  it("shows a wrong current password on its field and keeps the user signed in", async () => {
    setup();
    server.use(http.post("*/api/v1/auth/password", () => HttpResponse.json(
      { ...problem(400, "INVALID_CURRENT_PASSWORD", "The current password is incorrect."), errors: [{ field: "currentPassword", message: "is incorrect" }] },
      { status: 400 })));
    renderApp("/app/account");
    await fill("Wrong-pass-1", "Battery-staple-7");
    expect(await screen.findByText("This is not your current password.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Account" })).toBeInTheDocument();
    expect(sessionStorage.getItem("apisentinel.session")).not.toBeNull();
  });
});
