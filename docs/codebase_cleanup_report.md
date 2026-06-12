# Codebase Cleanup Report

**Date:** 2026-06-12  
**Scope:** Full-repository quality, maintainability, reliability, and technical debt reduction sprint  
**Goal:** Cleaner, smaller, more consistent codebase without removing working functionality

---

## Executive Summary

This sprint audited the entire Celerius repository (backend, frontend, database, generators, CIP layer, tests, docs) and implemented safe, high-impact fixes. No features were added. All preserved domains remain intact: Auth, RBAC, Studies, Artifacts, Approvals, Audit Logs, Context Graph, AI Decisions, Human Overrides, Data Lineage, Study Intake, Generators, Validation, and Intelligence Pages.

**Verification status:**
- Backend unit tests: **370 passed**
- Key integration tests (RBAC, upload, generation): **42 passed**
- Frontend typecheck, lint, unit tests: **passed**

---

## Cleanup Plan by Severity

### Critical (addressed or documented)

| Issue | Status | Action |
|-------|--------|--------|
| Double AI decision logging on generation jobs | **Fixed** | Removed pre-execution `begin_decision`/`complete_decision` from `GenerationService.create_job()`; `BaseGenerator.run()` owns the decision lifecycle |
| Upload endpoint missing RBAC | **Fixed** | Added `check_permission(actor, Permission.ARTIFACT_CREATE)` in `UploadService.upload_file()` |
| Broken Intelligence hub link to `/generated-data` | **Fixed** | Study-scoped card disabled until study selected; no 404 link |
| Approvals queue visible to Contributors | **Fixed** | `GET /approvals/queue` now requires `Permission.ARTIFACT_APPROVE` |
| Manual artifact creation skips graph registration | **Documented** | Remaining debt — see §Remaining Technical Debt |
| Orphan `TraceabilityLink` model | **Documented** | Legacy model with no migration; graph is canonical |

### High (addressed or documented)

| Issue | Status | Action |
|-------|--------|--------|
| Duplicated `_link_study_traceability()` (~50 lines × 4) | **Fixed** | Extracted to `ContextGraphService.link_pipeline_artifact_to_study()` |
| Duplicate blob download logic (frontend) | **Fixed** | Centralized in `lib/download.ts` → `downloadAuthenticatedBlob()` |
| Unused npm dependencies (8 packages) | **Fixed** | Removed from `package.json` — see `dependency_cleanup_report.md` |
| Intake service missing RBAC | **Fixed** | `ARTIFACT_CREATE` check on `start_session`, `respond`, `compile_brief` |
| Dual generation architectures (job queue vs pipeline) | **Documented** | Architectural decision required |
| Thin AI reasoning in pipeline services | **Documented** | Extend `reasoning_builder.py` |
| Business logic in route handlers | **Documented** | `csr.py`, `adam.py`, `approvals.py`, `users.py` need service extraction |
| EDC generator logs AI decision without LLM inference | **Documented** | Use `RULE_BASED_GENERATION` decision type |

### Medium

| Issue | Status |
|-------|--------|
| Missing query error UI on most pages | **Partial** — added `QueryState` component; adoption on remaining pages is debt |
| Duplicate generation job UI | **Partial** — shared `generationLabels.ts`; full table extraction deferred |
| Confusing dual Validation routes | **Fixed** — sidebar renamed to "Conformance Runs" vs "CIP Validation" |
| Context graph gaps (QC, mapping suggestions, artifact CRUD) | **Documented** |
| Data lineage gaps (suggestions, manual edits) | **Documented** |
| `BaseGenerator` hardcoded confidence=0.9 | **Documented** |
| Mega-pages (study workspace, artifact detail) | **Documented** — split deferred |

### Low

| Issue | Status |
|-------|--------|
| Unwired `csr_ich_e3_pdf_renderer.py`, `xpt_export_service.py` | **Kept** — tested, not wired; wire or document as future |
| Eval harness duplicates generator map | **Documented** |
| Branding drift (TrialGenesis vs Celerius) | **Documented** |
| EDC demo page with mock data | **Kept** — linked from study workspace |

---

## Removed

### Dependencies (frontend)
- `@hookform/resolvers`, `clsx`, `react-hook-form`, `tailwind-merge`, `zod`
- `@tanstack/react-query-devtools`, `@testing-library/react`, `@testing-library/user-event`

### Code (deduplicated, not deleted)
- `_link_study_traceability()` methods removed from 4 pipeline services (logic moved to `ContextGraphService`)
- Duplicate `downloadBinary()` removed from `lib/api/sdtm.ts`
- ~90 lines of duplicate fetch/error parsing removed from `lib/api/artifacts.ts`

### Files
No production files were deleted in this sprint. Unused services (`csr_ich_e3_pdf_renderer`, `xpt_export_service`) and orphan model (`TraceabilityLink`) were retained pending architectural decisions.

---

## Refactored

### Services
| Service | Change |
|---------|--------|
| `generation_service.py` | Removed duplicate AI decision logging on job creation |
| `upload_service.py` | Added RBAC enforcement |
| `intake_service.py` | Added RBAC on write operations |
| `context_graph_service.py` | Added `link_pipeline_artifact_to_study()` shared helper |
| `sdtm/adam/tlf/csr_generation_service.py` | Use shared graph helper instead of duplicated methods |

### APIs
| Endpoint | Change |
|----------|--------|
| `GET /approvals/queue` | RBAC: Reviewer/Admin only |

### Frontend
| Area | Change |
|------|--------|
| `lib/download.ts` | Centralized authenticated blob download |
| `lib/generationLabels.ts` | Shared status/type label constants |
| `lib/formatRelativeTime.ts` | Shared relative time formatter |
| `components/ui/QueryState.tsx` | Reusable loading/error/empty wrapper |
| `intelligence/page.tsx` | Fixed broken study-scoped navigation |
| `Sidebar.tsx` | Clarified Validation vs CIP Validation labels |
| `dashboard/page.tsx` | Approvals query gated by role; shared time formatter |
| Generation pages | Use shared label constants |

### Tests
| Test | Change |
|------|--------|
| `test_rbac_endpoints.py` | Added contributor cannot list approvals queue |
| `test_sdtm_generation_service.py` | Mock `list_by_study` for protocol lookup |
| `test_adam_generation_service.py` | Added data cut metadata to SDTM fixture |

---

## Fixed

### Bugs
- Intelligence hub 404 when no study selected for Generated Data card
- TypeScript errors in generation pages after label extraction

### Security
- Upload RBAC enforcement (Admin/Contributor only)
- Intake write RBAC enforcement
- Approvals queue RBAC enforcement (Reviewer/Admin only)
- Dashboard no longer fetches approvals queue for Contributors

### Performance
- Dashboard skips unnecessary approvals API call for non-reviewers

---

## Remaining Technical Debt (Prioritized)

### P1 — Architectural
1. **Consolidate dual generation paths** — job queue (`BaseGenerator`) vs pipeline (`*GenerationService`) for SDTM/ADaM/TLF/CSR
2. **Register artifacts in Context Graph on manual create** — `ArtifactService.create_artifact()`
3. **Move business logic out of routes** — `csr.py`, `adam.py`, `approvals.py`, `users.py`, `statistical_qc.py`
4. **Remove or migrate `TraceabilityLink` model** — superseded by Context Graph

### P2 — CIP Quality
5. **Enrich AI reasoning** for SDTM/ADaM/TLF/CSR pipeline services and dual-programmer QC
6. **Fix EDC generator** — honest `RULE_BASED_GENERATION` decision type vs false `ARTIFACT_GENERATION`
7. **Context graph instrumentation** for mapping suggestions, QC outputs, artifact lifecycle
8. **Data lineage** for mapping suggestions (pre-apply) and manual artifact edits

### P3 — Frontend
9. **Adopt `QueryState`** across all data pages (~25 pages lack error UI)
10. **Extract `GenerationJobTable`** shared component
11. **Split mega-pages** — `studies/[id]/page.tsx` (1,047 lines), `artifacts/[artifactId]/page.tsx` (954 lines)
12. **Wire or remove EDC demo page** mock data
13. **Unify branding** — TrialGenesis vs Celerius

### P4 — Infrastructure
14. **Wire `csr_ich_e3_pdf_renderer` and `xpt_export_service`** into export paths
15. **Submission list/readiness RBAC** — currently any authenticated user
16. **Comment resolve role gate**
17. **N+1 query review** in list endpoints with eager loading audit

---

## Architecture Health Score

| Area | Score | Notes |
|------|-------|-------|
| **Frontend** | 7/10 | No dead components; good strict typing; mega-pages and missing error states remain |
| **Backend** | 7/10 | Clean service/repo layering mostly; some fat routes; RBAC gaps closed this sprint |
| **Database** | 8/10 | Solid multi-tenant FKs; orphan `TraceabilityLink`; indexes generally adequate |
| **Generators** | 6/10 | `BaseGenerator` consistent for 7/8 types; EDC rule-based mismatch; dual paths |
| **Context Graph** | 7/10 | Strong in pipeline/upload/intake; gaps on artifact CRUD and QC |
| **Lineage** | 7/10 | Good upload→CSR pipeline chain; gaps on suggestions and manual edits |

**Overall:** 7/10 — Production-capable with clear, prioritized debt backlog

---

## Dead Code Audit Summary

| Category | Finding |
|----------|---------|
| Unused components | **0** / 22 |
| Unused hooks | **0** / 6 |
| Unused services (prod) | **2** — `csr_ich_e3_pdf_renderer`, `xpt_export_service` (test-only) |
| Unused endpoints | **0** — all 21 modules registered in router |
| Unused repositories | **0** / 14 |
| Unused models | **1** — `TraceabilityLink` |
| Frontend `any` types | **0** |
| Unused npm packages | **8 removed** |

---

## Duplicate Logic Identified

| Pattern | Locations | Status |
|---------|-----------|--------|
| `_link_study_traceability` | 4 pipeline services | **Extracted** |
| Blob download + error parse | artifacts, sdtm, rawData, submissions | **Centralized** |
| Generation status/type labels | 2 generation pages | **Shared constants** |
| `rel()` relative time | 8+ pages | **Partial** — utility created, full adoption pending |
| Export audit pattern | adam, csr, submissions routes | **Documented** |
| `_GENERATOR_MAP` | executor + eval harness | **Documented** |

---

## Security Review Summary

| Finding | Severity | Status |
|---------|----------|--------|
| Upload without RBAC | Critical | **Fixed** |
| Approvals queue to Contributors | High | **Fixed** |
| Intake without RBAC | High | **Fixed** |
| Tenant isolation | — | Generally good (org_id from JWT) |
| Submission list/readiness open | Medium | Documented |
| Comment resolve without reviewer gate | Medium | Documented |
| Graph/intelligence reads org-scoped | — | By design |

---

## Performance Review Summary

| Finding | Impact | Status |
|---------|--------|--------|
| Dashboard approvals fetch for all roles | Low | **Fixed** |
| Submission page 9 parallel queries | Medium | Documented — `useSubmissionReadiness` hook candidate |
| Study workspace 6+ queries inline | Medium | Documented |
| N+1 in artifact list with study names | Low | Documented — eager loading review |
| Large artifact payloads in list endpoints | Low | Documented |

---

## Test Coverage Notes

Critical workflows with integration test coverage:
- Login / auth: ✓
- RBAC: ✓ (expanded this sprint)
- Study creation: ✓
- Artifact generation: ✓
- Approvals: ✓
- Audit logs: ✓
- Context graph: ✓
- Synthetic data: partial
- Validation: ✓
- Downloads: ✓

---

## Files Changed This Sprint

### Backend
- `app/services/generation_service.py`
- `app/services/upload_service.py`
- `app/services/intake_service.py`
- `app/services/context_graph_service.py`
- `app/services/sdtm_generation_service.py`
- `app/services/adam_generation_service.py`
- `app/services/tlf_generation_service.py`
- `app/services/csr_generation_service.py`
- `app/api/v1/endpoints/approvals.py`
- `tests/integration/test_rbac_endpoints.py`
- `tests/unit/test_sdtm_generation_service.py`
- `tests/unit/test_adam_generation_service.py`

### Frontend
- `package.json`
- `src/lib/download.ts`
- `src/lib/generationLabels.ts`
- `src/lib/formatRelativeTime.ts`
- `src/lib/api/artifacts.ts`
- `src/lib/api/sdtm.ts`
- `src/lib/api/rawData.ts`
- `src/components/ui/QueryState.tsx`
- `src/components/layout/Sidebar.tsx`
- `src/app/(dashboard)/intelligence/page.tsx`
- `src/app/(dashboard)/dashboard/page.tsx`
- `src/app/(dashboard)/generation/page.tsx`
- `src/app/(dashboard)/studies/[id]/generation/page.tsx`
