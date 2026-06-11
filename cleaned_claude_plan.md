# Cleaned Claude Code Output

## 1. Terminal Session Metadata

```text
eshaanraj@Eshaans-MacBook-Air-6 ctsm_AIsquad % claude
 ▐▛███▜▌   Claude Code v2.1.170
▝▜█████▛▘  Sonnet 4.6 · Claude Pro
  ▘▘ ▝▝    ~/ctsm_AIsquad
 ▐▛███▜▌   Claude Code v2.1.170
▝▜█████▛▘  Fable 5 · Claude Pro
  ▘▘ ▝▝    ~/ctsm_AIsquad
 ▎ Fable 5 is here! Our newest model for complex, long-running work
 ▎ Included in your plan limits until Jun 22, then switch to usage credits to continue.
❯ /plan
  ⎿  Enabled plan mode
❯ /model
  ⎿  Set model to Fable 5 and saved as your default for new sessions
```

## 2. Original Prompt Sent to Claude

# Scan my codebase and help me plan what we should build next with Fable.

## Context

This repository is for Celerius, an AI-native clinical trial lifecycle platform. The product goal is to support an auditable workflow from sponsor intake through protocol/SAP/eCRF generation, raw data handling, SDTM, ADaM, TLFs, CSR, and submission packaging.

Do not rely only on the README or roadmap, because they may be outdated. Inspect the actual backend, frontend, tests, infrastructure, and documentation before making recommendations.

Focus on answering this:

What should the team build next to maximize near-term product value and reduce delivery risk?

Use these current hypotheses as starting points, but verify them in the codebase:

- The backend appears to implement submission packaging, including readiness checks, async package creation, manifests, checksums, RBAC, audit records, graph links, and ZIP downloads.
- The frontend submission-readiness page exists, but the “Package Submission” button still appears disabled with a stale “Backend coming soon” message.
- Submission packages may still contain placeholder TLF, CSR, and Reviewer’s Guide files, so the package may be demonstrable but not regulatory-grade.
- Some docs may be stale and may understate what has already been implemented.
- The frontend test setup may be unreliable because Vitest appears to collect Playwright E2E specs.
- Frontend type-check may currently fail because of active graph UI work and artifact download type issues.
- Backend tests may not be locally reproducible without the correct virtual environment and test settings.
- The local branch may be behind origin/main and may contain uncommitted work that should not be overwritten.
- The repo appears to have more backend coverage than frontend coverage, and there may be no full browser E2E test for submission readiness, package creation, polling, manifest review, and download.

Evaluate this proposed next milestone:

“Trustworthy End-to-End Submission Demo”

First restore a reproducible green baseline and reconcile active work. Then wire the existing submission backend into a complete role-aware frontend workflow: backend readiness as the source of truth, Admin package creation, async status polling, Reviewer/Admin manifest viewing, Admin ZIP download, clear failure states, and an E2E test using the full demo seed. Finally, update the product docs so they reflect what the system actually does and clearly label placeholder outputs versus regulatory-grade outputs.

Compare that milestone against these alternatives:

1. Regulatory output depth:
- Real TLF, CSR, and Reviewer’s Guide rendering
- Full define.xml, ADRG, eCTD XML
- Removal of placeholder submission outputs

2. Production readiness:
- S3 or Azure storage
- Durable background jobs
- Production email
- Security/compliance hardening
- Operational observability

3. Pipeline breadth and polish:
- Dedicated SDTM/CSR review UIs
- Bulk reject
- Multi-sheet naming conventions
- Traceability impact-report polish

## Required analysis

1. Inspect relevant backend, frontend, test, infrastructure, and documentation files.
2. Cite concrete repository paths and code evidence.
3. Reconcile stale docs with the actual implementation.
4. Identify anything incorrectly marked complete.
5. Identify active or uncommitted work that must be integrated or protected before starting.
6. Rank the proposed milestone and alternatives using:
- stakeholder/demo value
- user workflow completeness
- regulatory and data-integrity risk reduction
- engineering risk and dependencies
- testability
- estimated effort
7. Separate:
- bugs/baseline repairs
- product-completion work
- regulatory-grade hardening
- external blockers such as Pinnacle 21 licensing, BAA/DPA, and live AI keys
8. Challenge completion claims. A placeholder PDF, RTF, or generated file should not be described as regulatory-ready.

## Required output format

### 1. Executive Recommendation

- Recommend one next milestone.
- Explain why it beats the alternatives right now.
- Define what is explicitly out of scope.

### 2. Current-State Findings

- List the most important verified findings, ordered by severity or value.
- Cite repository paths.
- Call out stale or conflicting documentation.

### 3. Milestone Definition

- Describe the user outcome and demo narrative.
- Define personas and RBAC behavior for Admin, Reviewer, and Contributor.
- Provide a Definition of Done with measurable acceptance criteria.
- Include regulatory-language guardrails for placeholder and nonvalidated outputs.

### 4. Sequenced Work Plan

Break the milestone into small, mergeable work packages.

For each work package, include:

- objective
- likely files/modules
- dependencies
- acceptance criteria
- required unit/integration/E2E tests
- risk notes
- rough effort: S, M, or L

The sequence must begin with branch/worktree reconciliation and a trustworthy test baseline. Avoid broad refactors.

### 5. Backlog After This Milestone

- Rank the next 5 follow-on initiatives.
- Explain what new evidence would change the ranking.

### 6. Open Decisions

- List only decisions that genuinely require product, regulatory, or operator input.
- Recommend a default for each.

## Constraints

- Do not simplify regulatory or audit requirements to make the demo easier.
- Do not overwrite or discard uncommitted work.
- Keep backend routes thin; business logic belongs in services and database access belongs in repositories.
- Prefer existing patterns and APIs over new abstractions.
- Treat synthetic data as synthetic at every layer.
- Distinguish between “demonstrable,” “functionally complete,” and “regulatory-ready.”
- Make the plan executable by a small engineering team in incremental pull requests.

## 3. Claude Activity Log

```text
⏺ I'll start by checking the git/repo state myself, then launch parallel Explore agents to verify each hypothesis area.

⏺ Bash(git -C /Users/eshaanraj/ctsm_AIsquad status --short && echo "---BRANCH---" && git -C /Users/eshaanraj/ctsm_AIsquad branch -vv &&
      echo "---REMOTE---" && git -C /…)
  ⎿   M frontend/tsconfig.tsbuildinfo
     ---BRANCH---
     * main df37897 [origin/main] Add study termination and harden intake progression and SDTM generation.
     … +6 lines (ctrl+o to expand)

⏺ Bash(git -C /Users/eshaanraj/ctsm_AIsquad stash list && echo "---DIFF STAT---" && git -C /Users/eshaanraj/ctsm_AIsquad diff --stat &&
      echo "---UNTRACKED---" && git -…)
  ⎿  ---DIFF STAT---
      frontend/tsconfig.tsbuildinfo | 2 +-
      1 file changed, 1 insertion(+), 1 deletion(-)
     ---UNTRACKED---

⏺ 3 Explore agents finished (ctrl+o to expand)
   ├ Explore backend submission packaging · 43 tool uses · 57.2k tokens
   │ ⎿  Done
   ├ Explore frontend submission UI/tests · 42 tool uses · 56.4k tokens
   │ ⎿  Done
   └ Explore docs, infra, CI state · 43 tool uses · 54.4k tokens
     ⎿  Done

⏺ Bash(cd /Users/eshaanraj/ctsm_AIsquad/frontend && cat package.json | head -40 && ls vitest.config.* vite.config.* 2>/dev/null; echo
      "---VITEST LIST---"; npx vitest l…)
  ⎿  {
       "name": "celerius-frontend",
       "version": "0.1.0",
     … +69 lines (ctrl+o to expand)
  ⎿  Allowed by auto mode classifier

  Plan(Design submission demo milestone plan)
  ⎿  Bash(sed -n '55,110p' /Users/eshaanraj/ctsm_AIsquad/frontend/src/lib/api/artifacts.ts)
     Runnigrep -n "playwright\|Playwright" -B3 -A15 /Users/eshaanraj/ctsm_AIsquad/.github/workflows/ci.yml | head -60; echo ===; head

⏺ Plan(Design submission demo milestone plan)
  ⎿  Done (28 tool uses · 77.7k tokens · 6m 29s)
  (ctrl+o to expand)

⏺ Updated plan
  ⎿  /plan to preview

───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
```

## 4. Claude Plan Output

```text
Ready to code?
Here is Claude's plan:
```

# Plan: Trustworthy End-to-End Submission Demo

## Context

Celerius needs its next milestone chosen. The submission-packaging backend turned out to be fully implemented and tested (readiness checks, async assembly, manifests with SHA-256 checksums, RBAC, audit records, graph links, ZIP download), but the frontend "Package Submission" button is still hard-disabled with a stale "Backend coming soon" tooltip, no frontend API client exists for submissions, the frontend test/type-check baseline is broken, and the docs both understate (README) and overstate (phase status doc) reality. This plan verifies the current state, ranks the proposed milestone against three alternatives, and sequences the recommended milestone into small mergeable PRs.

All findings below were verified directly in the codebase (not from docs).

---

## 1. Executive Recommendation

Build the "Trustworthy End-to-End Submission Demo" milestone — restore a green baseline, wire the existing submission backend into a role-aware frontend workflow, add an E2E test, and truth-up the docs with a maturity taxonomy.

Why it beats the alternatives right now (ranking):

Rank: 1
Option: E2E Submission Demo
Demo value: High — completes the headline narrative (intake → submission ZIP)
Workflow completeness: High — closes the only dead-end in the lifecycle
Risk reduction: Medium-high (honest labeling fixes a data-integrity misrepresentation risk)
Eng. risk: Low — backend done & tested; frontend reuses proven patterns
Testability: High — pure helpers + Playwright
Effort: S/M (~6-9 PRs)

---

Rank: 2
Option: Regulatory output depth
Demo value: Medium (better files, same flow)
Workflow completeness: Low (no new user workflow)
Risk reduction: High long-term
Eng. risk: Medium-high (PDF rendering = new deps; eCTD XML = spec-heavy; Pinnacle 21 = external blocker)
Testability: Medium
Effort: L

---

Rank: 3
Option: Production readiness
Demo value: Low for demos
Workflow completeness: None
Risk reduction: High for ops, not for product
Eng. risk: Medium (S3, durable jobs, email = infra churn)
Testability: Medium
Effort: L

---

Rank: 4
Option: Pipeline breadth & polish
Demo value: Low-medium
Workflow completeness: Medium (incremental)
Risk reduction: Low
Eng. risk: Low
Testability: Medium
Effort: M

The deciding facts: the backend work for the milestone is already done (backend/app/services/submission_service.py, 588 lines, with
unit + integration tests), so the milestone is mostly low-risk frontend wiring against verified APIs; and it converts an invisible asset into the single most valuable demo moment. Alternatives 1–3 all build on top of a flow nobody can currently see or exercise. Alternative 1 (regulatory depth) is the right next milestone after this one — and one cheap piece of it (real TLF RTF via the existing, dead-code TLFRenderer) is pulled in here as a stretch WP.

Explicitly out of scope: real CSR PDF rendering and Reviewer's Guide authoring (needs a PDF library decision), eCTD XML backbone,
define.xml 2.1 conformance validation, Pinnacle 21 integration, S3/Azure storage, durable job queue (Celery), production email, removing placeholders by faking them as real. Placeholders stay — but get honestly labeled.

Maturity language used throughout: Demonstrable (works end-to-end on synthetic data; some outputs placeholder) → Functionally complete (real outputs, synthetic data) → Regulatory-ready (validated, compliant, real-data capable). After this milestone, submission packaging is Demonstrable, not regulatory-ready.

---

## 2. Current-State Findings (verified, by severity/value)

Hypothesis scorecard: 7 of 9 user hypotheses confirmed; 2 false (git reconciliation not needed; "active graph UI work" type errors
don't exist — there is exactly one TS error, in artifact download).

1. Backend submission packaging is complete and tested — backend/app/services/submission_service.py: get_readiness() (4 artifact types APPROVED + no pending AI decisions + no CDISC FAILs), create_submission_package() (Admin-only), async assembly via FastAPI BackgroundTasks (submission_executor.py) with DRAFT→PACKAGING→READY transitions, manifest with per-file SHA-256 + package checksum, audit actions (SUBMISSION_PACKAGE_CREATED/STATUS_CHANGED/EXPORTED), graph node + INCLUDES edges, ZIP download. Endpoints in backend/app/api/v1/endpoints/submissions.py. Tests: backend/tests/unit/test_submission_service.py, backend/tests/integration/test_submission_endpoints.py (incl. RBAC 403 cases).
2. Frontend dead-ends the flow — frontend/src/app/(dashboard)/studies/[id]/submission/page.tsx ~lines 273–281: button hard disabled, title="Backend coming soon", comment TODO: wire to Phase 8 API. No frontend/src/lib/api/submissions.ts client exists at all.
3. Package contents are mixed-grade — real: SDTM/ADaM CSVs from artifact content, real CDISC Define-XML 2.1 (sdtm_define_service.build_define_xml), checksummed manifest. Placeholder: TLF RTF stub (_build_tlf_placeholder, "RTF output pending full rendering"), CSR fake-PDF bytes (_build_csr_placeholder), reviewers-guide.pdf stub. Phase 8 is "demonstrable," not "100% complete."
4. Vitest collects Playwright specs (confirmed by running it) — no vitest.config.ts exists; npx vitest list errors on e2e/approval-workflow.spec.ts / e2e/auth.spec.ts ("Playwright Test did not expect test.describe()"). --passWithNoTests has been masking this.
5. Type-check fails with exactly one error — frontend/src/hooks/useArtifactDownload.ts:41 TS2345: Pick missing current_version_number expected by artifactsApi.exportArtifact (frontend/src/lib/api/artifacts.ts:~69). A second caller (intelligence/synthetic/page.tsx:~277) must be updated with the fix. No graph-UI type errors exist.
6. Git is clean — main in sync with origin/main; only frontend/tsconfig.tsbuildinfo (build cache, should be gitignored) is modified. No stashes, no untracked files. No reconciliation work needed.
7. Demo seed can't reach readiness — database/seeds/demo_program_seed.py creates all artifacts as DRAFT, so backend readiness fails on a fresh seed. A live (non-mocked) demo needs an opt-in --approve-artifacts flag.
8. error_message is invisible to clients — exists on the model (backend/app/models/submission.py:69) but absent from SubmissionPackageResponse/SubmissionManifestResponse (backend/app/schemas/submission.py). Frontend cannot show failure states today. Also: executor failure handling can leave a failed package in DRAFT or PACKAGING with error_message set — polling must treat non-null error_message as terminal.
9. APPROVED vs LOCKED mismatch — backend readiness matches APPROVED only (submission_service.py:342–360); frontend checklist counts APPROVED || LOCKED (submission/page.tsx:19). A LOCKED artifact makes the UI say ready while the backend refuses.
10. No SYNTHETIC labeling in the package — violates the CLAUDE.md invariant "Synthetic data output is always labeled SYNTHETIC." Manifest/ZIP carry no marker.
11. Docs conflict in both directions — README.md (~line 115) claims domain endpoints are "placeholders only" (false — 22 functional endpoint files) and marks submission packaging "Planned" (~line 421); docs/phase_completion_status.md marks Phase 8 "100% complete" (overstated per finding 3).
12. RBAC matrix confirmed in backend/app/core/permissions.py — create/download: Admin only (require_admin → USER_MANAGE=[ADMIN]); manifest: AUDIT_READ=[ADMIN, REVIEWER]; package list endpoint has no role gate (any authenticated org member can poll status — this is what enables Contributor read-only tracking without touching governed files). Minor follow-up (not this milestone): SubmissionPackageResponse leaks local_path (server filesystem path) to all roles.
13. CI is healthy (.github/workflows/ci.yml: backend pytest w/ Postgres+Redis, frontend type-check/lint/vitest, Playwright on main) — but type-check and vitest jobs would fail today per findings 4–5. Backend tests are reproducible: backend/.venv, Postgres on :5433 (docker), test DB celerius_test derived from DATABASE_URL.

---

## 3. Milestone Definition

User outcome / demo narrative: An Admin opens a fully seeded study, sees backend-authoritative readiness (with named blockers if not ready), clicks Package Submission, watches live status DRAFT→PACKAGING→READY, opens the manifest (file tree, sizes, SHA-256 checksums, honest "PLACEHOLDER — not regulatory-grade" badges on TLF/CSR/Reviewer's Guide, a SYNTHETIC-data banner), and downloads the ZIP. A Reviewer can inspect the manifest but not create/download. A Contributor sees status read-only with an explanation. Failures surface a clear error banner.

Personas & RBAC (frontend must mirror backend exactly):
- Admin — create package, view manifest, download ZIP, see readiness blockers.
- Reviewer — view manifest + statuses; no create, no download.
- Contributor — see readiness + package statuses (ungated list endpoint); no create/manifest/download controls; sees "Submission packaging requires the Admin role."

Definition of Done (measurable):
1. tsc --noEmit zero errors; pnpm test runs only src/**/*.test.* (no Playwright collection) and passes; backend pytest green locally (documented invocation) and in CI.
2. Admin happy path works live against the backend: create → poll → READY → manifest → ZIP downloads and opens with real CSVs + define.xml.
3. Manifest UI shows per-file grade with exactly the placeholder files badged; SYNTHETIC banner always visible on manifest view.
4. Backend readiness endpoint is the sole gate for the create button; UI checklist is explanatory only; APPROVED/LOCKED mismatch resolved.
5. Failure state: a package with error_message shows a red banner with the message and a re-create path; 422 SUBMISSION_NOT_READY renders the backend issues[].
6. Playwright spec e2e/submission-packaging.spec.ts covers all three roles + blocked + failure paths, green in CI.
7. Fresh DB + dev_seed.py + demo_program_seed.py --approve-artifacts ⇒ readiness ready:true (with audit records for the seeded status changes).
8. Docs use the Demonstrable / Functionally complete / Regulatory-ready taxonomy; no doc claim contradicts code; placeholder inventory listed explicitly.

Regulatory-language guardrails: never describe placeholder RTF/PDF as "generated" or "complete"; every manifest/package view carries the synthetic-data disclaimer; docs and demo runbook state verbatim that the package is "demonstrable on synthetic data — not for regulatory submission"; grade field values are generated vs placeholder, assigned in backend code (source of truth), not inferred in UI except as fallback for pre-existing packages.

---

## 4. Sequenced Work Plan

One WP = one PR. Every PR keeps type-check, vitest, backend pytest (and from WP5, Playwright) green. No governed files (core/security.py, core/permissions.py, api/deps.py, models/audit.py, services/audit_service.py) are touched — verified per-WP.

### WP0 ─> WP1 ─> WP2 ─> WP3 ─> WP4 ─> WP5

├──> WP6 (parallel w/ WP3–5)
└──> WP8 (stretch, parallel) ──> WP7 (docs, last)

### WP0 — Baseline repair (S) — bugs/baseline

- Objective: green type-check, working vitest, verified backend test baseline, clean git.
- Files: frontend/src/hooks/useArtifactDownload.ts (add "current_version_number" to the Pick, line 18); frontend/src/app/(dashboard)/intelligence/synthetic/page.tsx (~277, add current_version_number: 1 to the inline call); new frontend/vitest.config.ts (include: ["src/**/*.test.{ts,tsx}"], exclude e2e/**, @→./src alias); frontend/.gitignore (+tsconfig.tsbuildinfo, restore the file).
- Deps: none. Acceptance: tsc --noEmit clean; pnpm test runs only src/lib/artifactDownload.test.ts; backend/.venv pytest run of submission tests green vs Postgres :5433; git status clean.
- Tests: existing only. Risk: none — purely corrective.

### WP1 — Backend additive API surface (S/M) — product completion

- Objective: expose error_message, per-file grade, SYNTHETIC labeling, and fix LOCKED readiness — all additive, no governed files.
- Files: backend/app/schemas/submission.py (add error_message: str | None to package + manifest responses); backend/app/services/submission_service.py (_file_entry() gains grade: "generated"|"placeholder" — define.xml/CSVs/manifest = generated, TLF/CSR/reviewers-guide = placeholder; manifest top-level data_classification: "SYNTHETIC_DEMO" + grading legend; _find_required_artifacts/_collect_readiness_issues accept APPROVED or LOCKED); extend both submission test files.
- Deps: WP0. Acceptance: manifest entries carry grade; responses carry error_message; LOCKED satisfies readiness; backend tests green.
- Tests: unit asserts per-entry grade + classification; integration asserts response fields; new LOCKED-readiness case.
- Risk: LOCKED semantics change is deliberate — call out in PR description (additive schemas/+services/ changes are in the "may modify" list; no tri-agent-review files touched).

### WP2 — Frontend submission API client + types + permission flags (S) — product completion

- Objective: typed client matching backend exactly.
- Files: new frontend/src/lib/api/submissions.ts (getReadiness, createPackage, listForStudy [the role-agnostic poll target], getManifest, downloadZip as blob w/ Content-Disposition filename — model on lib/api/generation.ts + artifacts.ts:exportArtifact); frontend/src/types/index.ts (SubmissionPackageStatus, SubmissionPackage incl. error_message, SubmissionReadiness, SubmissionManifest, SubmissionManifestFile w/ grade?); frontend/src/hooks/usePermissions.ts (add canCreateSubmissionPackage [Admin], canViewSubmissionManifest [Admin+Reviewer — mirrors AUDIT_READ], canDownloadSubmissionPackage [Admin] — frontend-only file, allowed).
- Deps: WP1 (response shapes). Acceptance: type-check clean; flags exactly mirror backend PERMISSION_MATRIX. Risk: low.

### WP3 — Wire the submission page: create, poll, failure states (M) — product completion

- Objective: replace the dead button; full status lifecycle visible per role; backend readiness authoritative.
- Files: frontend/src/app/(dashboard)/studies/[id]/submission/page.tsx (add useStudyPermissions; useQuery on getReadiness as the gate, keep existing checklist as explanatory UI; listForStudy with the generation/page.tsx:127–131 refetchInterval callback — 5s while PACKAGING or fresh-DRAFT-without-error, else stop; stall timeout message; useMutation(createPackage) + invalidate; Contributor explanation text; error banners for error_message and 422 issues[]); new frontend/src/components/submission/PackagePanel.tsx (status card: pill, checksum, timestamps, role-gated actions); new frontend/src/lib/submissionStatus.ts (pure helpers derivePackageDisplayState, shouldPoll — unit-testable without DOM, since no jsdom/@testing-library is installed).
- Deps: WP2. Acceptance: Admin creates and watches DRAFT→PACKAGING→READY live; Contributor read-only w/ explanation; Reviewer sees statuses; failed package shows error_message; not-ready shows backend issues + disabled button.
- Tests: new frontend/src/lib/submissionStatus.test.ts covering all branches incl. error-while-PACKAGING and READY-on-first-fetch.
- Risk: fast assembly may skip visible PACKAGING — treat READY-on-first-poll as success.

### WP4 — Manifest viewer, download, placeholder + SYNTHETIC labeling (M) — product completion

- Objective: transparency: checksums, honest placeholder badges, synthetic banner.
- Files: new frontend/src/components/submission/ManifestTable.tsx (path, size, truncated sha256 + copy, grade badge; amber "PLACEHOLDER — not regulatory-grade" for grade==="placeholder", path-based fallback inference for pre-WP1 packages in a pure helper); PackagePanel.tsx ("View manifest" lazily fetched + gated by canViewSubmissionManifest to avoid Contributor 403s; "Download ZIP" gated by canDownloadSubmissionPackage, reuse triggerBlobDownload from lib/artifactDownload.ts; SYNTHETIC banner from manifest.data_classification); lib/submissionStatus.ts (+deriveFileGrade).
- Deps: WP1–WP3. Acceptance: Reviewer/Admin see manifest with exactly three placeholder-badged entries; Contributor never triggers the manifest call; Admin downloads a valid ZIP; banner always visible; frontend gating === backend gating.
- Tests: vitest for deriveFileGrade; E2E in WP5.

### WP5 — Playwright E2E spec (M) — product completion / testability

- Objective: CI-deterministic role-based coverage of the full flow.
- Files: new frontend/e2e/submission-packaging.spec.ts — reuse approval-workflow.spec.ts patterns: real UI login (extend role map with admin@demo.dev from dev_seed.py), page.route() mocks for **/api/v1/submissions/**. Scenarios: (1) Admin happy path with stateful PACKAGING→READY mock, manifest badges + SYNTHETIC banner, download event asserted; (2) blocked readiness → disabled button + issues; (3) failure → error_message banner; (4) Contributor → no create, explanation visible; (5) Reviewer → manifest yes, download no.
- Deps: WP3–WP4. Acceptance: pnpm test:e2e green locally + CI; independent of demo_program_seed.
- Risk: mocked-blob download assertion is fiddly — assert the download event, not ZIP contents.

### WP6 — Live-demo enablement: seed flag + runbook (S) — product completion (parallel with WP3–5)

- Objective: make the real, non-mocked demo possible: seed → ready → package → download.
- Files: database/seeds/demo_program_seed.py (opt-in --approve-artifacts: set SDTM/ADaM/TLF/CSR artifacts to APPROVED, consistent version history, AuditLog rows for each status change per CLAUDE.md); new docs/runbooks/submission_demo.md (docker up → seeds → admin walkthrough → placeholder disclosure script for the audience).
- Deps: WP1. Acceptance: fresh DB + two seed commands ⇒ ready:true; live packaging yields a READY package whose ZIP opens with real CSVs + define.xml.
- Risk: keep flag opt-in so approval-workflow demos (which need DRAFT artifacts) still work.

### WP8 (stretch, recommended) — Wire real TLFRenderer into packaging (S) — regulatory-grade hardening, pulled forward

- Objective: replace the TLF RTF stub with the existing, unit-tested, currently-dead TLFRenderer.render_to_rtf() (backend/app/services/tlf_renderer.py) — same content dict, verified cheap swap.
- Files: backend/app/services/submission_service.py (TLF branch ~420–428: write_bytes(TLFRenderer().render_to_rtf(content)), flip manifest grade to generated, delete _build_tlf_placeholder); update test_submission_service.py TLF assertions.
- Deps: WP1; land before WP7 if taken. Risk: figures inside RTF remain in-document placeholders — say so in docs; file-level grade stays honest because tables/listings are real.

### WP7 — Docs truth-up with maturity taxonomy (S) — last

- Files: README.md (fix "placeholders only" claim ~line 115; roadmap ~417–421 → Submission Package = "Demonstrable"; add three-tier legend); docs/phase_completion_status.md (Phase 8 "100%" → "Demonstrable" + explicit placeholder inventory vs what's real, adjusted for WP8 outcome).
- Deps: all prior WPs. Acceptance: no doc contradicts code; taxonomy used consistently.

Work classification: baseline repairs = WP0; product completion = WP1–WP6; regulatory-grade hardening = WP8 (plus the deferred items
below); external blockers (none block this milestone): Pinnacle 21 license (PINNACLE21_ENABLED=false, internal validator fallback exists), live ANTHROPIC_API_KEY (deterministic fallbacks exist), BAA/DPA + production SMTP/S3 (production-readiness milestone only).

---

## 5. Backlog After This Milestone (ranked)

1. Regulatory output depth — real CSR PDF (PDF library decision required), Reviewer's Guide/ADRG content, eCTD XML backbone, define.xml conformance checking. Evidence that would change ranking: a scheduled regulator/partner review, or Pinnacle 21 license acquisition (would pull validation integration forward).
2. Submission API hardening — remove local_path leak from SubmissionPackageResponse (needs deprecation note per API-versioning rules), role-gate or scope the package list endpoint deliberately, stall/retry semantics for stuck PACKAGING. Changes ranking if: a security review or external pilot starts.
3. Production readiness — S3/Azure storage (model already has s3_key), durable jobs (BackgroundTasks → queue), production email, observability. Changes ranking if: a real deployment date or BAA/DPA is signed.
4. Pipeline breadth/polish — dedicated SDTM/CSR review UIs, bulk reject, multi-sheet naming, traceability impact-report polish. Changes ranking if: demo feedback identifies a specific reviewer-workflow gap.
5. Frontend test depth — add jsdom + @testing-library component tests (currently absent), expand E2E beyond mocked routes to a live-backend smoke profile using the WP6 seed flag. Changes ranking if: regressions start escaping to demos.

---

## 6. Open Decisions (defaults recommended)

1. Should LOCKED artifacts satisfy submission readiness? Backend currently says no, frontend says yes. Default: yes (LOCKED is post-approval and immutable per the lifecycle — arguably more submission-worthy than APPROVED). Implemented in WP1 with explicit tests; needs product sign-off because it changes readiness semantics.
2. Include WP8 (real TLF RTF in the package)? Default: yes — verified ~1-day swap of dead code into the assembly path; materially upgrades the demo. Defer only if the milestone deadline is tight.
3. Contributor visibility into package status. The ungated list endpoint means Contributors can poll status. Default: keep (transparency within the org; create/manifest/download remain gated). If product wants manifest-level secrecy from Contributors, that's already enforced server-side.
4. data_classification value. Default: SYNTHETIC_DEMO on all packages assembled from synthetic seeds. Deciding when/how a package could ever be classified otherwise is a regulatory/operator decision deferred to the regulatory-depth milestone.

---

## Verification

- WP0: cd frontend && npx tsc --noEmit && pnpm test (must run only src tests); cd backend && .venv/bin/pytest tests/unit/test_submission_service.py tests/integration/test_submission_endpoints.py with docker Postgres on :5433.
- WP1: backend pytest; manually inspect a generated manifest.json for grade + data_classification.
- WP3–WP4 (live): docker compose up; seed dev_seed.py + demo_program_seed.py --approve-artifacts (after WP6); login as admin → create package → observe polling → manifest badges → download ZIP and open it; repeat as reviewer (no create/download) and contributor (read-only).
- WP5: pnpm test:e2e locally and in CI.
- Full milestone: run the docs/runbooks/submission_demo.md script end-to-end on a fresh database.

---

## 5. Claude Proceed Options

```text
Claude has written up a plan and is ready to execute. Would you like to proceed?
❯ 1. Yes, and use auto mode
2. Yes, manually approve edits
3. No, refine with Ultraplan on Claude Code on the web
4. Tell Claude what to change
shift+tab to approve with this feedback
ctrl+g to edit in  VS Code  · ~/.claude/plans/scan-my-codebase-and-delightful-nygaard.md
```
