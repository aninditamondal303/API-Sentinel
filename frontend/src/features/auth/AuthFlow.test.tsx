import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { dashboard, page, problem, project, tokenResponse, user } from "@/test/fixtures";
import { renderApp, signIn } from "@/test/render";
import { server } from "@/test/server";

function dashboardHandlers() {
  server.use(
    http.get("*/api/v1/auth/me", () => HttpResponse.json(user)),
    http.get("*/api/v1/dashboard", () => HttpResponse.json(dashboard)),
    http.get("*/api/v1/projects", () => HttpResponse.json(page([project]))),
  );
}

describe("authentication flow", () => {
  it("redirects anonymous users from the app to the login page", async () => {
    renderApp("/app/projects");
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
  });

  it("validates the login form before calling the backend", async () => {
    renderApp("/login");
    await userEvent.click(await screen.findByRole("button", { name: "Sign in" }));
    expect(screen.getByText("Enter your email address.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
  });

  it("shows a clear message for wrong credentials", async () => {
    server.use(http.post("*/api/v1/auth/login", () => HttpResponse.json(problem(401, "INVALID_CREDENTIALS", "Invalid email or password."), { status: 401 })));
    renderApp("/login");
    await userEvent.type(await screen.findByLabelText("Email"), "ada@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "Wrong-pass-1");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password.");
  });

  it("logs in, stores the session in sessionStorage and shows the dashboard", async () => {
    let body: unknown;
    server.use(http.post("*/api/v1/auth/login", async ({ request }) => { body = await request.json(); return HttpResponse.json(tokenResponse()); }));
    dashboardHandlers();
    renderApp("/login?next=%2Fapp");
    await userEvent.type(await screen.findByLabelText("Email"), " ada@example.com ");
    await userEvent.type(screen.getByLabelText("Password"), "Correct-horse-9");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("heading", { name: /Welcome, Ada/ })).toBeInTheDocument();
    expect(await screen.findByText("4 compatibility · 3 security")).toBeInTheDocument();
    expect(body).toEqual({ email: "ada@example.com", password: "Correct-horse-9" });
    expect(sessionStorage.getItem("apisentinel.session")).toContain("\"token\"");
    expect(localStorage.length).toBe(0);
  });

  it("maps EMAIL_TAKEN to the email field on registration", async () => {
    server.use(http.post("*/api/v1/auth/register", () => HttpResponse.json(problem(409, "EMAIL_TAKEN", "taken"), { status: 409 })));
    renderApp("/register");
    await userEvent.type(await screen.findByLabelText("Name"), "Ada");
    await userEvent.type(screen.getByLabelText("Work email"), "ada@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "Correct-horse-9");
    await userEvent.type(screen.getByLabelText("Confirm password"), "Correct-horse-9");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("An account with this email already exists.")).toBeInTheDocument();
  });

  it("ends the session when the backend rejects the token", async () => {
    signIn();
    server.use(http.get("*/api/v1/auth/me", () => HttpResponse.json(problem(401, "UNAUTHENTICATED", "expired"), { status: 401 })));
    renderApp("/app");
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
    await waitFor(() => expect(sessionStorage.getItem("apisentinel.session")).toBeNull());
  });

  it("does not follow an external next= redirect after login", async () => {
    const { safeNext } = await import("@/auth/RequireAuth");
    expect(safeNext("https://evil.example")).toBe("/app");
    expect(safeNext("//evil.example")).toBe("/app");
    expect(safeNext("/app/projects")).toBe("/app/projects");
  });
});
