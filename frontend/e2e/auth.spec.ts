import { expect, test } from "@playwright/test";

const ADMIN_EMAIL = "admin@demo.dev";
const PASSWORD = "DevPass123!";

async function login(page: import("@playwright/test").Page, email = ADMIN_EMAIL, password = PASSWORD) {
  await page.goto("/login");
  await page.getByRole("textbox").first().fill(email);
  await page.getByRole("textbox").nth(1).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

test.describe("authentication", () => {
  test("valid credentials redirect to dashboard", async ({ page }) => {
    await login(page);

    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  });

  test("invalid credentials show an error and stay on login", async ({ page }) => {
    await login(page, ADMIN_EMAIL, "not-the-password");

    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByText("Invalid email or password.")).toBeVisible();
  });

  test("logout redirects to login and protected pages require login", async ({ page }) => {
    await login(page);
    await expect(page).toHaveURL(/\/dashboard$/);

    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login$/);

    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login$/);
  });
});
