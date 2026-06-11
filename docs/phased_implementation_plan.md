# Celerius — Phased Implementation Plan

**Created:** 2026-06-10  
**Source:** `cleaned_claude_plan.md` (codebase scan, June 2026) + verification against current repo state  
**Audience:** Engineering team planning incremental PRs

---

## Maturity taxonomy

Use this language consistently in code, UI, and docs:

| Tier | Meaning |
|------|---------|
| **Demonstrable** | End-to-end workflow works on synthetic data; some outputs may be placeholders |
| **Functionally complete** | Real outputs for all artifacts; still synthetic-data only |
| **Regulatory-ready** | Validated, compliant, capable of real-data submission workflows |

Most of the platform is **Demonstrable** or **Functionally complete (partial)** today. Nothing in submission packaging is **Regulatory-ready**.

---

## Current snapshot (verified 2026-06-10)

### Already built (do not re-implement)

- Full clinical pipeline backend: intake → protocol/SAP/eCRF → raw data → SDTM → ADaM → TLF → CSR
- CIP layer: context graph, AI decisions, overrides, lineage, validation intelligence, synthetic data
- **Submission packaging backend** (`backend/app/services/submission_service.py`): readiness checks, async assembly, SHA-256 manifest, RBAC, audit, graph links, ZIP download — with unit + integration tests
- Artifact lifecycle, RBAC, audit logging, multi-tenancy
- CI pipeline (backend pytest, frontend type-check/lint/vitest, Playwright on main)

### Critical gaps blocking the headline demo

| Gap | Evidence |
|-----|----------|
| Frontend submission flow is a dead end | `frontend/src/app/(dashboard)/studies/[id]/submission/page.tsx` — button disabled, `"Backend coming soon"` |
| No frontend submission API client | `frontend/src/lib/api/submissions.ts` does not exist |
| Type-check baseline broken | `frontend/src/hooks/useArtifactDownload.ts` — `Pick` missing `current_version_number` |
| Vitest collects Playwright specs | No `frontend/vitest.config.ts`; E2E specs error under `pnpm test` |
| Backend API missing client-facing fields | `backend/app/schemas/submission.py` — no `error_message`, file `grade`, or `data_classification` |
| Demo seed cannot reach readiness | `database/seeds/demo_program_seed.py` — all artifacts seeded as DRAFT |
| Docs contradict code | `README.md` marks submission "Planned"; `docs/phase_completion_status.md` marks Phase 8 "100%" while frontend is unbuilt |
| Package contents are mixed-grade | Real CSVs + define.xml; placeholder TLF RTF, CSR PDF, Reviewer's Guide |

---

## Phase 0 — Baseline repair

**Goal:** Restore a trustworthy green baseline before product work.  
**Effort:** S (~1 PR)  
**Classification:** Bugs / baseline repairs

| Work package | Objective | Key files | Acceptance criteria |
|--------------|-----------|-----------|---------------------|
| **WP0** | Green type-check, working vitest, clean git | `frontend/src/hooks/useArtifactDownload.ts`, `frontend/src/app/(dashboard)/intelligence/synthetic/page.tsx`, new `frontend/vitest.config.ts`, `frontend/.gitignore` | `tsc --noEmit` clean; `pnpm test` runs only `src/**/*.test.*`; backend submission pytest green; git status clean |

**Dependencies:** None  
**Out of scope:** Feature work, refactors

---

## Phase 1 — Trustworthy end-to-end submission demo

**Goal:** Wire the existing submission backend into a complete, role-aware frontend workflow with honest labeling of placeholder outputs. After this phase, submission packaging is **Demonstrable** — not regulatory-ready.  
**Effort:** S/M (~6–9 PRs)  
**Classification:** Product completion  
**Recommended next milestone** (beats regulatory depth, production readiness, and pipeline polish for near-term demo value)

### Demo narrative (Definition of Done)

An **Admin** opens a seeded study, sees backend-authoritative readiness (with named blockers if not ready), clicks **Package Submission**, watches status `DRAFT → PACKAGING → READY`, opens the manifest (checksums, placeholder badges, SYNTHETIC banner), and downloads the ZIP. A **Reviewer** inspects the manifest but cannot create or download. A **Contributor** sees read-only status with a role explanation. Failures show a clear error banner.

### Personas & RBAC (frontend must mirror backend)

| Role | Create package | View manifest | Download ZIP | View readiness / status |
|------|----------------|---------------|--------------|-------------------------|
| Admin | ✓ | ✓ | ✓ | ✓ |
| Reviewer | ✗ | ✓ | ✗ | ✓ |
| Contributor | ✗ | ✗ | ✗ | ✓ (read-only) |

### Work packages (sequenced)

```
WP0 → WP1 → WP2 → WP3 → WP4 → WP5
              ├── WP6 (parallel with WP3–5)
              └── WP8 (stretch, parallel) → WP7 (docs, last)
```

| WP | Name | Effort | Objective | Key files | Depends on |
|----|------|--------|-----------|-----------|------------|
| **WP1** | Backend additive API surface | S/M | Expose `error_message`, per-file `grade`, `data_classification: SYNTHETIC_DEMO`, fix APPROVED/LOCKED readiness mismatch | `backend/app/schemas/submission.py`, `backend/app/services/submission_service.py`, submission tests | WP0 |
| **WP2** | Frontend API client + permissions | S | Typed client + permission flags matching backend RBAC | New `frontend/src/lib/api/submissions.ts`, `frontend/src/types/index.ts`, `frontend/src/hooks/usePermissions.ts` | WP1 |
| **WP3** | Wire submission page | M | Replace dead button; poll status; failure states; backend readiness as sole create gate | `frontend/src/app/(dashboard)/studies/[id]/submission/page.tsx`, new `PackagePanel.tsx`, `frontend/src/lib/submissionStatus.ts` | WP2 |
| **WP4** | Manifest viewer + download | M | Checksums, placeholder badges, SYNTHETIC banner, role-gated actions | New `ManifestTable.tsx`, updates to `PackagePanel.tsx` | WP1–WP3 |
| **WP5** | Playwright E2E | M | Role-based coverage: Admin happy path, blocked readiness, failure, Contributor, Reviewer | New `frontend/e2e/submission-packaging.spec.ts` | WP3–WP4 |
| **WP6** | Live-demo enablement | S | `--approve-artifacts` seed flag + runbook | `database/seeds/demo_program_seed.py`, new `docs/runbooks/submission_demo.md` | WP1 |
| **WP8** | Real TLF RTF in package *(stretch)* | S | Swap `_build_tlf_placeholder` for `TLFRenderer.render_to_rtf()` | `backend/app/services/submission_service.py`, `test_submission_service.py` | WP1 |
| **WP7** | Docs truth-up | S | Maturity taxonomy in README and phase status doc | `README.md`, `docs/phase_completion_status.md` | All prior WPs |

### Phase 1 acceptance criteria (measurable)

1. `tsc --noEmit` zero errors; vitest passes; backend pytest green locally and in CI
2. Admin happy path live: create → poll → READY → manifest → ZIP with real CSVs + define.xml
3. Manifest shows exactly three placeholder-badged files (TLF, CSR, Reviewer's Guide) unless WP8 lands
4. SYNTHETIC banner always visible on manifest view
5. Backend readiness endpoint is the sole gate for create; UI checklist is explanatory only
6. Failed packages show `error_message`; 422 `SUBMISSION_NOT_READY` renders backend `issues[]`
7. E2E spec covers all three roles + blocked + failure paths
8. `demo_program_seed.py --approve-artifacts` ⇒ `ready: true` with audit records
9. Docs use Demonstrable / Functionally complete / Regulatory-ready taxonomy consistently

### Explicitly out of scope for Phase 1

- Real CSR PDF rendering and Reviewer's Guide authoring (PDF library decision required)
- eCTD XML backbone and define.xml 2.1 conformance validation
- Pinnacle 21 integration
- S3/Azure storage, durable job queue (Celery), production email
- Removing placeholders by mislabeling them as real

---

## Phase 2 — Regulatory output depth

**Goal:** Replace placeholder submission outputs with real rendered artifacts; move toward **Functionally complete** on synthetic data.  
**Effort:** L  
**Classification:** Regulatory-grade hardening  
**Priority after Phase 1**

| Initiative | Description | Key areas | External blockers |
|------------|-------------|-----------|-------------------|
| **2.1 CSR PDF rendering** | Real PDF output from CSR content (not fake-PDF bytes) | `submission_service.py`, new PDF library, CSR generator | PDF library product decision |
| **2.2 Reviewer's Guide / ADRG** | Authoring pipeline for regulatory review documents | New service or CSR extension | Content/template decisions |
| **2.3 eCTD XML backbone** | Module structure as valid eCTD XML, not folder preview only | New export service, schema validation | eCTD spec expertise |
| **2.4 define.xml conformance** | Full regulatory define.xml (codelists, origins, computational derivations) | `sdtm_define_service.py` | Pinnacle 21 optional |
| **2.5 Pinnacle 21 integration** | Production validation evidence via P21 adapter | `Pinnacle21Service`, env config | Pinnacle 21 license |
| **2.6 Full TLF rendering** | RTF/PDF for all tables, listings, figures | `tlf_renderer.py`, `TLFGenerationService` | — |
| **2.7 CSR prose generation** | Final medical writing, not section shells | `CSRGenerationService` | Live AI keys for quality |

**Evidence that would reprioritize:** Scheduled regulator/partner review; Pinnacle 21 license acquisition.

### Per-phase pipeline gaps (from phase status doc)

These overlap Phase 2 and Phase 5:

- Phase 4 (~5%): Full regulatory define.xml; dedicated SDTM review UI
- Phase 5 (~5%): ADaM define.xml / ADRG export; P21 ADaM rules
- Phase 6 (~5%): Full TLF rendering; listing/figure catalog from SAP traceability
- Phase 7 (~5%): Full CSR prose; eCTD XML export; dedicated CSR section editor

---

## Phase 3 — Submission API hardening & security

**Goal:** Close security and API hygiene gaps surfaced during Phase 1.  
**Effort:** S/M  
**Classification:** Security / API hygiene  
**Priority:** When external pilot or security review is scheduled

| Initiative | Description |
|------------|-------------|
| Remove `local_path` leak | `SubmissionPackageResponse` exposes server filesystem path to all roles — deprecate per API versioning rules |
| Scope package list endpoint | Document or role-gate the ungated list endpoint deliberately |
| Stuck PACKAGING recovery | Stall/retry semantics for packages left in PACKAGING |
| `data_classification` policy | Define when a package can ever be classified non-synthetic (regulatory/operator decision) |

---

## Phase 4 — Production readiness

**Goal:** Operate Celerius outside local Docker with durable jobs, cloud storage, and observability.  
**Effort:** L  
**Classification:** Infrastructure / ops  
**Priority:** When deployment date or BAA/DPA is signed

| Initiative | Description | Notes |
|------------|-------------|-------|
| **4.1 Cloud storage** | S3 or Azure Blob for packages and artifacts | Model already has `s3_key` field |
| **4.2 Durable background jobs** | Replace FastAPI `BackgroundTasks` with Celery/Redis queue | Submission + generation executors |
| **4.3 Production email** | Invites, notifications, approval alerts | Blocks Phase 1 polish item |
| **4.4 Observability** | Structured logging, metrics, alerting | — |
| **4.5 Security hardening** | CSP, rate limits audit, secrets rotation | Nginx + app layer |
| **4.6 BAA/DPA compliance** | Real PHI handling policies | Currently synthetic-only |

**External blockers:** BAA/DPA, production SMTP, cloud credentials.

---

## Phase 5 — Pipeline breadth & polish

**Goal:** Improve reviewer workflows and traceability UX across the lifecycle.  
**Effort:** M  
**Classification:** Product polish  
**Priority:** After demo feedback identifies specific gaps

| Initiative | Phase | Description |
|------------|-------|-------------|
| Dedicated SDTM review UI | 4 | Today uses generic artifact + `/intelligence/decisions` |
| Dedicated CSR section editor | 7 | Section-by-section editing with audit trail |
| Bulk reject (mappings) | 2 | Complement existing bulk approve |
| Multi-sheet Excel naming conventions | 2 | Regulatory submission naming |
| Traceability impact-report polish | 3 | Impact analysis on gap report; idempotency key hardening |
| E2E generation UI polish | 1 | Generation workflow UX |
| Graph explorer enhancements | 3 | Remaining ~5% context graph items |

---

## Phase 6 — Frontend test depth

**Goal:** Reduce regression risk as the UI surface grows.  
**Effort:** M  
**Classification:** Test infrastructure  
**Priority:** When regressions escape to demos

| Initiative | Description |
|------------|-------------|
| jsdom + @testing-library | Component tests for forms, approval flows, submission panels |
| Live-backend E2E profile | Playwright smoke against real API using `--approve-artifacts` seed |
| Expand RBAC E2E coverage | Beyond mocked routes |

---

## Cross-cutting: already partial, finish incrementally

These items span multiple phases and can be pulled forward when a specific demo or pilot requires them:

| Area | Status | Remaining |
|------|--------|-----------|
| Dual-programmer R QC | Built (Phases 4–6) | Manual execution when `Rscript` unavailable in Docker |
| CIP review queue | Built | Bulk accept/reject; richer decision diff UI |
| Internal CDISC validation | Built | P21 production credentials |
| Synthetic data labeling | Partial | Phase 1 WP1 adds package-level; ensure all layers label SYNTHETIC |
| AI generation | Built with fallbacks | Production `ANTHROPIC_API_KEY`; quality tuning |

---

## Recommended execution order

| Order | Phase | Rationale |
|-------|-------|-----------|
| **Now** | Phase 0 (WP0) | Unblocks CI and all subsequent PRs |
| **Next** | Phase 1 (WP1–WP7, optional WP8) | Highest demo value; backend already done; low engineering risk |
| **Then** | Phase 2.6 + WP8 | Cheap win: wire existing `TLFRenderer` before heavy PDF/eCTD work |
| **Then** | Phase 2 (remaining) | Regulatory depth before production deploy |
| **Parallel track** | Phase 3 | When pilot customers appear |
| **Pre-deploy** | Phase 4 | Required for any non-dev environment |
| **Ongoing** | Phase 5 + 6 | Driven by user feedback and regression patterns |

---

## Open decisions (require product / regulatory input)

| # | Decision | Recommended default |
|---|----------|---------------------|
| 1 | Should LOCKED artifacts satisfy submission readiness? | **Yes** — LOCKED is post-approval and immutable |
| 2 | Include WP8 (real TLF RTF) in Phase 1? | **Yes** — ~1-day swap of existing dead code |
| 3 | Contributor visibility into package status? | **Keep** — transparency; create/manifest/download remain gated server-side |
| 4 | When can `data_classification` be non-synthetic? | **Defer** to Phase 2 / regulatory milestone |

---

## Verification checklist

| Phase | How to verify |
|-------|---------------|
| Phase 0 | `cd frontend && npx tsc --noEmit && pnpm test`; `cd backend && .venv/bin/pytest tests/unit/test_submission_service.py tests/integration/test_submission_endpoints.py` |
| Phase 1 WP1 | Backend pytest; inspect manifest JSON for `grade` + `data_classification` |
| Phase 1 WP3–4 | Docker up → seeds → Admin create/poll/manifest/download; repeat as Reviewer and Contributor |
| Phase 1 WP5 | `pnpm test:e2e` locally and in CI |
| Phase 1 full | Run `docs/runbooks/submission_demo.md` end-to-end on fresh database |

---

## Summary

**Immediate work:** Phase 0 baseline repair, then Phase 1 (Trustworthy End-to-End Submission Demo) — nine small PRs that connect an already-complete backend to the frontend, add E2E coverage, and truth-up documentation.

**Medium-term:** Phase 2 regulatory output depth (real CSR PDF, Reviewer's Guide, eCTD XML, full define.xml).

**Pre-production:** Phase 4 (S3, durable jobs, email, observability).

**Continuous:** Phase 5 pipeline polish and Phase 6 frontend test depth, prioritized by demo and pilot feedback.
