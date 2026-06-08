import { expect, type Page, test } from "@playwright/test";

const ADMIN_EMAIL = "admin@demo.dev";
const PASSWORD = "DevPass123!";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByRole("textbox").first().fill(ADMIN_EMAIL);
  await page.getByRole("textbox").nth(1).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  const authState = await page.evaluate(() => window.localStorage.getItem("trialgenesis-auth"));
  await page.addInitScript((value) => {
    if (value) window.localStorage.setItem("trialgenesis-auth", value);
  }, authState);
}

test.describe("intelligence screens", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("AI decisions queue loads", async ({ page }) => {
    await page.goto("/intelligence/decisions");

    await expect(page.getByRole("heading", { name: "AI Decisions" })).toBeVisible();
    await expect(page.getByText(/pending review|select a study|no decisions found/i).first()).toBeVisible();
  });

  test("human overrides log loads", async ({ page }) => {
    await page.goto("/intelligence/overrides");

    await expect(page.getByRole("heading", { name: "Human Overrides" })).toBeVisible();
    await expect(page.getByText(/append-only|select a study|no overrides recorded/i).first()).toBeVisible();
  });

  test("traceability chain view loads", async ({ page }) => {
    await page.goto("/intelligence/traceability");

    await expect(page.getByRole("heading", { name: "Traceability Matrix" })).toBeVisible();
    await expect(page.getByText(/Objective|Endpoint|Select a study/i).first()).toBeVisible();
  });

  test("context graph page loads", async ({ page }) => {
    await page.goto("/intelligence/graph");

    await expect(page.getByRole("heading", { name: "Context Graph" })).toBeVisible();
    await expect(page.getByText(/nodes|select a study|context graph/i).first()).toBeVisible();
  });
});
