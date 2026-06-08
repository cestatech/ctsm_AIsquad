import { expect, type Page, test } from "@playwright/test";

type Role = "CONTRIBUTOR" | "REVIEWER";
type ArtifactStatus = "DRAFT" | "IN_REVIEW" | "APPROVED" | "REJECTED";

interface MockArtifact {
  id: string;
  organization_id: string;
  study_id: string;
  artifact_type: "SAP";
  name: string;
  description: string;
  status: ArtifactStatus;
  current_version_id: string;
  current_version_number: number;
  locked_at: string | null;
  tags: string[] | null;
  created_by_id: string;
  created_at: string;
  updated_at: string;
}

function buildArtifact(studyId: string, id: string, name: string): MockArtifact {
  return {
    id,
    organization_id: "e2e-org",
    study_id: studyId,
    artifact_type: "SAP",
    name,
    description: "Mocked artifact for approval workflow assertions",
    status: "DRAFT",
    current_version_id: `${id}-version`,
    current_version_number: 1,
    locked_at: null,
    tags: null,
    created_by_id: "e2e-user",
    created_at: "2026-06-08T00:00:00.000Z",
    updated_at: "2026-06-08T00:00:00.000Z",
  };
}

const PASSWORD = "DevPass123!";
const EMAIL_BY_ROLE: Record<Role, string> = {
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

async function mockWorkflowApis(page: Page, artifacts: MockArtifact[]) {
  const byId = new Map(artifacts.map((artifact) => [artifact.id, artifact]));

  for (const artifact of artifacts) {
    await page.route(`**/${artifact.id}/submit`, async (route) => {
      const current = byId.get(artifact.id);
      if (current) current.status = "IN_REVIEW";
      await route.fulfill({ json: current });
    });
    await page.route(`**/api/v1/artifacts/${artifact.id}/submit`, async (route) => {
      const current = byId.get(artifact.id);
      if (current) current.status = "IN_REVIEW";
      await route.fulfill({ json: current });
    });
    await page.route(`**/api/v1/artifacts/${artifact.id}/versions`, async (route) => {
      await route.fulfill({
        json: [
          {
            id: artifact.current_version_id,
            artifact_id: artifact.id,
            version_number: 1,
            is_current: true,
            content: { title: artifact.name },
            content_hash: "e2e-hash",
            content_diff: null,
            file_path: null,
            file_size_bytes: null,
            file_mime_type: null,
            change_summary: "E2E setup",
            status_at_creation: artifact.status,
            created_by_id: "e2e-user",
            creator: null,
            created_at: "2026-06-08T00:00:00.000Z",
          },
        ],
      });
    });
    await page.route(`**/api/v1/artifacts/${artifact.id}`, async (route) => {
      await route.fulfill({ json: byId.get(artifact.id) });
    });
  }

  await page.route("**/api/v1/approvals", async (route) => {
    const body = route.request().postDataJSON() as {
      artifact_id: string;
      artifact_version_id: string;
      decision: "APPROVED" | "REJECTED";
      comments?: string;
    };
    const artifact = byId.get(body.artifact_id);
    if (artifact) artifact.status = body.decision;
    await route.fulfill({
      json: {
        id: "e2e-approval",
        artifact_id: body.artifact_id,
        artifact_version_id: body.artifact_version_id,
        approver_id: "e2e-reviewer",
        approver: null,
        decision: body.decision,
        comments: body.comments ?? null,
        created_at: "2026-06-08T00:00:00.000Z",
      },
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

test.describe.serial("approval workflow", () => {
  test("contributor submits and reviewer approves or rejects artifacts", async ({ page }) => {
    const studyId = "e2e-approval-study";
    const approveArtifact = buildArtifact(studyId, "e2e-approve-artifact", "E2E Approval Artifact");
    const rejectArtifact = buildArtifact(studyId, "e2e-reject-artifact", "E2E Rejection Artifact");
    await mockWorkflowApis(page, [approveArtifact, rejectArtifact]);

    await loginUi(page, "CONTRIBUTOR");
    await page.goto(`/studies/${studyId}/artifacts/${approveArtifact.id}`);
    await expect(page.getByRole("button", { name: "Submit for Review" })).toBeVisible();
    await Promise.all([
      page.waitForResponse((response) => response.url().includes(`${approveArtifact.id}/submit`)),
      page.getByRole("button", { name: "Submit for Review" }).click({ force: true }),
    ]);
    await expect(page.getByText("IN REVIEW").first()).toBeVisible();

    await page.goto(`/studies/${studyId}/artifacts/${rejectArtifact.id}`);
    await expect(page.getByRole("button", { name: "Submit for Review" })).toBeVisible();
    await Promise.all([
      page.waitForResponse((response) => response.url().includes(`${rejectArtifact.id}/submit`)),
      page.getByRole("button", { name: "Submit for Review" }).click({ force: true }),
    ]);
    await expect(page.getByText("IN REVIEW").first()).toBeVisible();

    await loginUi(page, "REVIEWER");
    await page.goto(`/studies/${studyId}/artifacts/${approveArtifact.id}`);
    await page.getByRole("button", { name: "Approve" }).click({ force: true });
    await expect(page.getByRole("heading", { name: "Approve Artifact" })).toBeVisible();
    await page.getByRole("button", { name: "Confirm Approval" }).click({ force: true });
    await expect(page.getByText("APPROVED").first()).toBeVisible();

    await page.goto(`/studies/${studyId}/artifacts/${rejectArtifact.id}`);
    await page.getByRole("button", { name: "Reject" }).click({ force: true });
    await expect(page.getByRole("heading", { name: "Reject Artifact" })).toBeVisible();
    await expect(page.getByText("Rejection reason (required)")).toBeVisible();
    await expect(page.getByRole("button", { name: "Confirm Rejection" })).toBeDisabled();
    await page.getByRole("textbox").last().fill("E2E rejection note");
    await expect(page.getByRole("button", { name: "Confirm Rejection" })).toBeEnabled();
    await Promise.all([
      page.waitForResponse((response) => response.url().includes("/approvals")),
      page.getByRole("button", { name: "Confirm Rejection" }).click({ force: true }),
    ]);
    await expect(page.getByText("REJECTED").first()).toBeVisible();
  });
});
