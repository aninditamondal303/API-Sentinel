import path from "node:path";
import { expect, test } from "@playwright/test";

const examples = path.join(__dirname, "..", "..", "examples", "orders-api");

// The main journey through the real UI: React -> nginx -> Spring Boot -> Python analyzer -> PostgreSQL.
test("register, upload two versions and see the breaking compatibility scan", async ({ page }) => {
  const id = Date.now().toString(36);

  await page.goto("/register");
  await page.getByLabel("Name").fill("E2E Tester");
  await page.getByLabel("Work email").fill(`e2e.${id}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("E2e-password-9");
  await page.getByLabel("Confirm password").fill("E2e-password-9");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Welcome, E2E" })).toBeVisible();

  await page.goto("/app/projects?new=1");
  await page.getByLabel("Project name").fill(`Orders API ${id}`);
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page).toHaveURL(/\/app\/projects\/[0-9a-f-]{36}/);

  for (const [file, label] of [["baseline.yaml", "v1.0.0"], ["candidate-breaking.yaml", "v2.0.0"]]) {
    await page.getByRole("button", { name: "Upload spec", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Upload specification" });
    await dialog.getByLabel("Specification file").setInputFiles(path.join(examples, file));
    await dialog.getByLabel("Version label").fill(label);
    await dialog.getByRole("button", { name: "Validate & upload" }).click();
    await expect(page.getByText(`Uploaded ${label}`)).toBeVisible();
  }

  await page.getByRole("link", { name: "Compare versions" }).click();
  await page.getByRole("button", { name: "Run compatibility scan" }).click();
  await expect(page.getByText("Failed: this change does not meet the release policy")).toBeVisible();
  await expect(page.getByText("Breaking").first()).toBeVisible();
});
