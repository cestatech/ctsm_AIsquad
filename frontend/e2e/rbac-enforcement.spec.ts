import { expect, type Page, test } from "@playwright/test";

type Role = "ADMIN" | "CONTRIBUTOR" | "REVIEWER";
type ArtifactStatus = "DRAFT" | "IN_REVIEW" | "APPROVED";

const PASSWORD = "DevPass123!";
const EMAIL_BY_ROLE: Record<Role, string> = {
  ADMIN: "admin@demo.dev",
  CONTRIBUTOR: "contrib@demo.dev",
  REVIEWER: "reviewer@demo.dev",
};

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

async function mockArtifactDetail(page: Page, artifactId: string, status: ArtifactStatus) {
  const studyId = "e2e-rbac-study";
  const versionId = `${artifactId}-version`;
  const artifact = {
    id: artifactId,
    organization_id: "e2e-org",
    study_id: studyId,
    artifact_type: "SAP",
    name: `E2E ${status} Artifact`,
    description: "Mocked artifact for frontend RBAC assertions",
    status,
    current_version_id: versionId,
    current_version_number: 1,
    locked_at: null,
    tags: null,
    created_by_id: "e2e-user",
    created_at: "2026-06-08T00:00:00.000Z",
    updated_at: "2026-06-08T00:00:00.000Z",
  };

  await page.route(`**/api/v1/artifacts/${artifactId}`, async (route) => {
    await route.fulfill({ json: artifact });
  });
  await page.route(`**/api/v1/artifacts/${artifactId}/versions`, async (route) => {
    await route.fulfill({
      json: [
        {
          id: versionId,
          artifact_id: artifactId,
          version_number: 1,
          is_current: true,
          content: { title: artifact.name },
          content_hash: "e2e-hash",
          content_diff: null,
          file_path: null,
          file_size_bytes: null,
          file_mime_type: null,
          change_summary: "E2E setup",
          status_at_creation: status,
          created_by_id: "e2e-user",
          creator: null,
          created_at: "2026-06-08T00:00:00.000Z",
        },
      ],
    });
  });
  await page.route("**/api/v1/comments**", async (route) => {
    await route.fulfill({
      json: { items: [], total: 0, page: 1, page_size: 25, has_next: false, has_prev: false },
    });
  });
  await page.route("**/api/v1/graph/by-entity**", async (route) => {
    await route.fulfill({ json: { node: null, incoming: [], outgoing: [] } });
  });
  await page.route("**/api/v1/statistical-qc/runs**", async (route) => {
    await route.fulfill({
      json: { items: [], total: 0, page: 1, page_size: 5, has_next: false, has_prev: false },
    });
  });
}

test.describe("role-based UI enforcement", () => {
  const studyId = "e2e-rbac-study";
  const draftArtifactId = "e2e-draft-artifact";
  const inReviewArtifactId = "e2e-in-review-artifact";
  const approvedArtifactId = "e2e-approved-artifact";

  test("contributor cannot see approve action", async ({ page }) => {
    await loginUi(page, "CONTRIBUTOR");
    await mockArtifactDetail(page, inReviewArtifactId, "IN_REVIEW");
    await page.goto(`/studies/${studyId}/artifacts/${inReviewArtifactId}`);

    await expect(page.getByText("IN REVIEW").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Approve" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Reject" })).toHaveCount(0);
  });

  test("reviewer cannot create studies or lock artifacts", async ({ page }) => {
    await loginUi(page, "REVIEWER");
    await page.goto("/studies");
    await expect(page.getByRole("link", { name: "New study" })).toHaveCount(0);

    await mockArtifactDetail(page, approvedArtifactId, "APPROVED");
    await page.goto(`/studies/${studyId}/artifacts/${approvedArtifactId}`);
    await expect(page.getByText("APPROVED").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Lock" })).toHaveCount(0);
  });

  test("admin can see privileged study and artifact actions", async ({ page }) => {
    await loginUi(page, "ADMIN");
    await page.goto("/studies");
    await expect(page.getByRole("link", { name: "New study" })).toBeVisible();

    await mockArtifactDetail(page, draftArtifactId, "DRAFT");
    await page.goto(`/studies/${studyId}/artifacts/${draftArtifactId}`);
    await expect(page.getByRole("button", { name: "Submit for Review" })).toBeVisible();

    await mockArtifactDetail(page, inReviewArtifactId, "IN_REVIEW");
    await page.goto(`/studies/${studyId}/artifacts/${inReviewArtifactId}`);
    await expect(page.getByRole("button", { name: "Approve" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Reject" })).toBeVisible();

    await mockArtifactDetail(page, approvedArtifactId, "APPROVED");
    await page.goto(`/studies/${studyId}/artifacts/${approvedArtifactId}`);
    await expect(page.getByRole("button", { name: "Lock" })).toBeVisible();
  });
});
