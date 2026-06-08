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

test.describe.serial("study lifecycle data pipeline", () => {
  test("admin can create a study, upload CSV data, and open column mapping", async ({ page }) => {
    const runId = Date.now().toString();
    const protocolNumber = `E2E-${runId}`;
    const studyName = `E2E Data Pipeline ${runId}`;
    const csvName = `subjects-${runId}.csv`;
    const fileId = `e2e-file-${runId}`;
    const datasetId = `e2e-dataset-${runId}`;

    await login(page);

    await page.goto("/studies");
    await page.getByRole("link", { name: "New study" }).click();
    await expect(page.getByRole("heading", { name: "New Study" })).toBeVisible();

    await page.getByPlaceholder("e.g. CTG-2024-001").fill(protocolNumber);
    await page.getByPlaceholder("Full study title").fill(studyName);
    await page.getByPlaceholder("e.g. Non-Small Cell Lung Cancer").fill("E2E test indication");
    await page.getByPlaceholder("e.g. Oncology").fill("Automation");
    await page.getByRole("combobox").selectOption("PHASE_2");
    await page.getByPlaceholder("Sponsoring organization").fill("TrialGenesis QA");
    await page.getByRole("button", { name: "FDA" }).click();
    await page.getByRole("button", { name: "Create study" }).click();

    await expect(page.getByRole("heading", { name: studyName })).toBeVisible();

    await page.goto("/studies");
    const studyLink = page.getByRole("link", { name: studyName });
    await expect(studyLink).toBeVisible();
    const studyHref = await studyLink.getAttribute("href");
    expect(studyHref).toBeTruthy();
    await studyLink.click({ force: true });
    await expect(page.getByRole("heading", { name: studyName })).toBeVisible();
    const studyId = studyHref!.split("/").filter(Boolean).at(-1);
    expect(studyId).toBeTruthy();

    const uploadedFile = {
      id: fileId,
      organization_id: "e2e-org",
      study_id: studyId!,
      uploaded_by_id: "e2e-admin",
      original_filename: csvName,
      stored_filename: csvName,
      file_size_bytes: 46,
      mime_type: "text/csv",
      description: null,
      extracted_metadata: { row_count: 2 },
      file_hash: "e2e-hash",
      upload_status: "PARSED",
      created_at: "2026-06-08T00:00:00.000Z",
    };

    await page.route(`**/api/v1/studies/${studyId}/uploads**`, async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({ json: uploadedFile });
        return;
      }
      await route.fulfill({
        json: { items: [uploadedFile], total: 1, page: 1, page_size: 25, has_next: false, has_prev: false },
      });
    });
    await page.route(`**/raw-data/files/${fileId}`, async (route) => {
      await route.fulfill({ json: uploadedFile });
    });
    await page.route(`**/raw-data/files/${fileId}/datasets`, async (route) => {
      await route.fulfill({
        json: {
          items: [
            {
              id: datasetId,
              organization_id: "e2e-org",
              study_id: studyId!,
              uploaded_file_id: fileId,
              dataset_name: "subjects",
              row_count: 2,
              column_count: 3,
              parse_status: "PARSED",
              parse_error: null,
              created_at: "2026-06-08T00:00:00.000Z",
              fields: [],
            },
          ],
          total: 1,
        },
      });
    });
    await page.route(`**/raw-data/datasets/${datasetId}/fields`, async (route) => {
      await route.fulfill({
        json: ["USUBJID", "AGE", "SEX"].map((columnName, index) => ({
          id: `e2e-field-${index}`,
          organization_id: "e2e-org",
          study_id: studyId!,
          raw_dataset_id: datasetId,
          column_name: columnName,
          column_index: index,
          inferred_type: columnName === "AGE" ? "number" : "string",
          sample_values: columnName === "AGE" ? ["44", "51"] : [`${columnName}-1`, `${columnName}-2`],
          missing_count: 0,
          distinct_count: 2,
          min_value: null,
          max_value: null,
          mapped_ecrf_field_id: null,
          mapped_sdtm_variable_id: null,
          mapping_status: "UNMAPPED",
          mapping_version: 1,
          created_at: "2026-06-08T00:00:00.000Z",
          updated_at: "2026-06-08T00:00:00.000Z",
        })),
      });
    });
    await page.route(`**/raw-data/datasets/${datasetId}/validate`, async (route) => {
      await route.fulfill({
        json: {
          total_fields: 3,
          mapped_fields: 0,
          approved_fields: 0,
          pending_fields: 0,
          unmapped_fields: 3,
          coverage_pct: 0,
          issues: [],
        },
      });
    });

    await page.locator('input[type="file"]').setInputFiles({
      name: csvName,
      mimeType: "text/csv",
      buffer: Buffer.from("USUBJID,AGE,SEX\nSUBJ-001,44,F\nSUBJ-002,51,M\n"),
    });

    await expect(page.getByText(csvName)).toBeVisible();
    await page.getByRole("link", { name: /View/ }).first().click();

    await expect(page.getByRole("heading", { name: csvName })).toBeVisible();
    await expect(page.getByText(/columns/i)).toBeVisible();
    await expect(page.getByRole("cell", { name: "USUBJID" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "AGE" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "SEX" })).toBeVisible();
  });
});
