import { expect, type Page, test } from "@playwright/test";

type Role = "ADMIN" | "CONTRIBUTOR" | "REVIEWER";

const PASSWORD = "DevPass123!";
const EMAIL_BY_ROLE: Record<Role, string> = {
  ADMIN: "admin@demo.dev",
  CONTRIBUTOR: "contrib@demo.dev",
  REVIEWER: "reviewer@demo.dev",
};

const STUDY_ID = "e2e-study-submission";

async function loginUi(page: Page, role: Role) {
  await page.goto("/login");
  await page.getByRole("textbox").first().fill(EMAIL_BY_ROLE[role]);
  await page.getByRole("textbox").nth(1).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.evaluate((selectedRole) => {
    const raw = window.localStorage.getItem("trialgenesis-auth");
    if (!raw) return;
    const parsed = JSON.parse(raw) as { state?: { role?: string } };
    if (parsed.state) parsed.state.role = selectedRole;
    window.localStorage.setItem("trialgenesis-auth", JSON.stringify(parsed));
  }, role);
  const authState = await page.evaluate(() => window.localStorage.getItem("trialgenesis-auth"));
  await page.addInitScript((value) => {
    if (value) window.localStorage.setItem("trialgenesis-auth", value);
  }, authState);
}

function mockStudy(page: Page) {
  return page.route("**/api/v1/studies/*", async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    await route.fulfill({
      json: {
        id: STUDY_ID,
        organization_id: "e2e-org",
        name: "E2E Submission Study",
        short_name: "E2E-SUB",
        protocol_number: "E2E-001",
        status: "ACTIVE",
        created_at: "2026-06-08T00:00:00.000Z",
        updated_at: "2026-06-08T00:00:00.000Z",
      },
    });
  });
}

function mockSubmissionApis(
  page: Page,
  options: {
    ready?: boolean;
    packageStatus?: "DRAFT" | "PACKAGING" | "READY";
    errorMessage?: string | null;
    pollTransitions?: boolean;
  } = {}
) {
  const {
    ready = true,
    packageStatus = "READY",
    errorMessage = null,
    pollTransitions = false,
  } = options;

  let createCount = 0;
  let currentStatus = packageStatus;
  const packageId = "pkg-e2e-001";

  page.route("**/api/v1/submissions/studies/*/readiness", async (route) => {
    await route.fulfill({
      json: {
        study_id: STUDY_ID,
        ready,
        issues: ready ? [] : ["Missing approved SDTM_DATASET artifact."],
        required_artifacts: {
          SDTM_DATASET: ready ? "sdtm-1" : null,
          ADAM_DATASET: ready ? "adam-1" : null,
          TLF: ready ? "tlf-1" : null,
          CSR: ready ? "csr-1" : null,
        },
      },
    });
  });

  page.route("**/api/v1/submissions/studies/*/create", async (route) => {
    createCount += 1;
    currentStatus = pollTransitions ? "DRAFT" : packageStatus;
    await route.fulfill({
      json: {
        package_id: packageId,
        status: "DRAFT",
        artifact_ids: ["sdtm-1", "adam-1", "tlf-1", "csr-1"],
        issues: [],
      },
    });
  });

  page.route("**/api/v1/submissions/studies/*", async (route) => {
    if (route.request().url().includes("/readiness") || route.request().url().includes("/create")) {
      await route.continue();
      return;
    }
    if (createCount === 0 && !errorMessage) {
      await route.fulfill({ json: { items: [], total: 0 } });
      return;
    }
    if (pollTransitions && createCount > 0 && currentStatus === "DRAFT") {
      currentStatus = "PACKAGING";
    } else if (pollTransitions && currentStatus === "PACKAGING") {
      currentStatus = "READY";
    }
    await route.fulfill({
      json: {
        items: [
          {
            id: packageId,
            study_id: STUDY_ID,
            organization_id: "e2e-org",
            status: currentStatus,
            artifact_ids: ["sdtm-1", "adam-1", "tlf-1", "csr-1"],
            local_path: "/tmp/pkg",
            package_checksum: "abc123",
            error_message: errorMessage,
            created_by_id: "admin-1",
            created_at: "2026-06-08T00:00:00.000Z",
            updated_at: "2026-06-08T00:00:00.000Z",
          },
        ],
        total: 1,
      },
    });
  });

  page.route(`**/api/v1/submissions/${packageId}/manifest`, async (route) => {
    await route.fulfill({
      json: {
        package_id: packageId,
        study_id: STUDY_ID,
        status: "READY",
        package_checksum: "abc123",
        error_message: null,
        data_classification: "SYNTHETIC_DEMO",
        manifest: {
          data_classification: "SYNTHETIC_DEMO",
          files: [
            {
              path: "m5/define.xml",
              size_bytes: 1200,
              sha256: "a".repeat(64),
              grade: "generated",
            },
            {
              path: "m5/reviewers-guide.pdf",
              size_bytes: 200,
              sha256: "b".repeat(64),
              grade: "placeholder",
            },
            {
              path: "csr/csr-1.pdf",
              size_bytes: 300,
              sha256: "c".repeat(64),
              grade: "placeholder",
            },
          ],
        },
      },
    });
  });

  page.route(`**/api/v1/submissions/${packageId}/download`, async (route) => {
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "application/zip",
        "Content-Disposition": 'attachment; filename="submission_e2e.zip"',
      },
      body: Buffer.from("PK\x03\x04mock-zip"),
    });
  });
}

async function mockPeripheralApis(page: Page) {
  await page.route("**/api/v1/artifacts**", async (route) => {
    await route.fulfill({ json: { items: [], total: 0 } });
  });
  await page.route("**/api/v1/adam/studies/*/adam-readiness", async (route) => {
    await route.fulfill({
      json: { ready: true, issues: [], sdtm_artifact_count: 1, adam_artifact_count: 1 },
    });
  });
  await page.route("**/api/v1/csr/studies/*/csr-readiness", async (route) => {
    await route.fulfill({
      json: { ready: true, issues: [], tlf_artifact_count: 1, csr_artifact_count: 1 },
    });
  });
  await page.route("**/api/v1/intelligence/validation-evidence**", async (route) => {
    await route.fulfill({ json: { items: [], total: 0 } });
  });
  await page.route("**/api/v1/intelligence/decisions**", async (route) => {
    await route.fulfill({ json: { items: [], total: 0 } });
  });
  await page.route("**/api/v1/studies/*/members", async (route) => {
    await route.fulfill({ json: [] });
  });
}

test.describe("Submission packaging", () => {
  test("admin happy path — create, manifest, download", async ({ page }) => {
    await loginUi(page, "ADMIN");
    await mockStudy(page);
    await mockSubmissionApis(page, { pollTransitions: true });
    await mockPeripheralApis(page);

    await page.goto(`/studies/${STUDY_ID}/submission`);
    await expect(page.getByRole("button", { name: "Package Submission" })).toBeEnabled();
    await page.getByRole("button", { name: "Package Submission" }).click();

    const packagePanel = page.locator("section").filter({ hasText: "Submission package" });
    await expect(packagePanel.getByText("READY", { exact: true })).toBeVisible({
      timeout: 15000,
    });
    await page.getByRole("button", { name: "View manifest" }).click();
    await expect(page.getByText("SYNTHETIC DEMO DATA")).toBeVisible();
    await expect(page.getByText("PLACEHOLDER — not regulatory-grade")).toHaveCount(2);

    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download ZIP" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toContain("submission");
  });

  test("blocked readiness disables create button", async ({ page }) => {
    await loginUi(page, "ADMIN");
    await mockStudy(page);
    await mockSubmissionApis(page, { ready: false });
    await mockPeripheralApis(page);

    await page.goto(`/studies/${STUDY_ID}/submission`);
    await expect(page.getByRole("button", { name: "Package Submission" })).toBeDisabled();
    await expect(page.getByText("Backend blockers")).toBeVisible();
  });

  test("failed package shows error banner", async ({ page }) => {
    await loginUi(page, "ADMIN");
    await mockStudy(page);
    await mockSubmissionApis(page, {
      packageStatus: "DRAFT",
      errorMessage: "Background assembly failed",
    });
    await page.route("**/api/v1/submissions/studies/*", async (route) => {
      const url = route.request().url();
      if (url.includes("/readiness") || url.includes("/create")) {
        await route.continue();
        return;
      }
      await route.fulfill({
        json: {
          items: [
            {
              id: "pkg-e2e-001",
              study_id: STUDY_ID,
              organization_id: "e2e-org",
              status: "DRAFT",
              artifact_ids: [],
              local_path: null,
              package_checksum: null,
              error_message: "Background assembly failed",
              created_by_id: "admin-1",
              created_at: "2026-06-08T00:00:00.000Z",
              updated_at: "2026-06-08T00:00:00.000Z",
            },
          ],
          total: 1,
        },
      });
    });
    await mockPeripheralApis(page);

    await page.goto(`/studies/${STUDY_ID}/submission`);
    await expect(page.getByText("Package assembly failed")).toBeVisible();
    await expect(page.getByText("Background assembly failed")).toBeVisible();
  });

  test("contributor sees read-only explanation", async ({ page }) => {
    await loginUi(page, "CONTRIBUTOR");
    await mockStudy(page);
    await mockSubmissionApis(page);
    await mockPeripheralApis(page);

    await page.goto(`/studies/${STUDY_ID}/submission`);
    await expect(page.getByText("Submission packaging requires the Admin role")).toBeVisible();
    await expect(page.getByRole("button", { name: "Package Submission" })).toHaveCount(0);
  });

  test("reviewer can view manifest but not download", async ({ page }) => {
    await loginUi(page, "REVIEWER");
    await mockStudy(page);
    await mockSubmissionApis(page, { packageStatus: "READY" });
    await mockPeripheralApis(page);

    await page.route("**/api/v1/submissions/studies/*", async (route) => {
      if (route.request().url().includes("/readiness")) {
        await route.continue();
        return;
      }
      await route.fulfill({
        json: {
          items: [
            {
              id: "pkg-e2e-001",
              study_id: STUDY_ID,
              organization_id: "e2e-org",
              status: "READY",
              artifact_ids: [],
              local_path: "/tmp/pkg",
              package_checksum: "abc",
              error_message: null,
              created_by_id: "admin-1",
              created_at: "2026-06-08T00:00:00.000Z",
              updated_at: "2026-06-08T00:00:00.000Z",
            },
          ],
          total: 1,
        },
      });
    });

    await page.goto(`/studies/${STUDY_ID}/submission`);
    await page.getByRole("button", { name: "View manifest" }).click();
    await expect(page.getByText("SYNTHETIC DEMO DATA")).toBeVisible();
    await expect(page.getByRole("button", { name: "Download ZIP" })).toHaveCount(0);
  });
});
