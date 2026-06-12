# Codebase Audit — Issues & Improvement Backlog

**Date:** 2026-06-12
**Scope:** Full repository (backend, frontend, database, CI, docs) at `main`
**Out of scope by team decision:** AI/local model selection and implementation, Azure rollout (no go-ahead), Pinnacle 21 integration (no license yet). Nothing below depends on any of those.

All findings below have been filed as GitHub issues ([#24–#48](https://github.com/cestatech/ctsm_AIsquad/issues)).

---

## 1. Security & Auth

| # | Issue | Severity | Summary |
|---|-------|----------|---------|
| [#24](https://github.com/cestatech/ctsm_AIsquad/issues/24) | Per-IP login rate limiting missing | **High** | Only per-account lockout exists (`auth_service.py:88-94`). The documented "5 attempts / 15 min per IP" rule (CLAUDE.md) is unenforced, and the account lockout enables targeted lockout-DoS against any known email. |
| [#25](https://github.com/cestatech/ctsm_AIsquad/issues/25) | Audit IP capture ignores proxies | **High** | All ~30 call sites use `request.client.host`; behind Nginx every audit record stores the proxy IP, weakening the regulatory audit trail. CLAUDE.md requires proxy-aware capture. |
| [#26](https://github.com/cestatech/ctsm_AIsquad/issues/26) | Invite returns temp password in API response | **High** | `UserService.invite()` returns plaintext credentials. SMTP config + `fastapi-mail` + email templates all exist but nothing sends email. Also: `APP_URL` is read via `getattr` but never defined in `Settings`. |
| [#27](https://github.com/cestatech/ctsm_AIsquad/issues/27) | No password reset flow | Medium | Only authenticated change-password exists; a forgotten password means admin re-invite. |
| [#28](https://github.com/cestatech/ctsm_AIsquad/issues/28) | Email verification never happens | Medium | `email_verified` is set `False` at registration and never checked or flipped anywhere. |
| [#29](https://github.com/cestatech/ctsm_AIsquad/issues/29) | Submission list/readiness endpoints lack RBAC | **High** | `SubmissionService.list_for_study` and `get_readiness` have no permission check (known debt P4-15); comment resolve role gate (P4-16) also still open. |
| [#30](https://github.com/cestatech/ctsm_AIsquad/issues/30) | Upload validation trusts client Content-Type | Medium | `upload_service.py:101` validates the client-supplied MIME header; no magic-byte sniffing. |
| [#31](https://github.com/cestatech/ctsm_AIsquad/issues/31) | Part 11 e-signature lacks re-authentication | **High (compliance)** | Approvals store a signature blob (name/time/role/meaning) but never require the signer's password at signing time — 21 CFR Part 11 §11.200(a) gap. |

## 2. Architecture & CIP Integrity

| # | Issue | Severity | Summary |
|---|-------|----------|---------|
| [#32](https://github.com/cestatech/ctsm_AIsquad/issues/32) | Dual generation architectures | High (debt) | SDTM/ADaM/TLF/CSR exist in both the `BaseGenerator` job queue and the pipeline `*GenerationService` paths with diverging CIP instrumentation; eval harness duplicates the generator map. Needs an ADR + consolidation. |
| [#33](https://github.com/cestatech/ctsm_AIsquad/issues/33) | Manual artifacts skip Context Graph | **High (CIP)** | `ArtifactService.create_artifact()` never registers a graph node — manually created artifacts are invisible to traceability/lineage/impact analysis, the product's core USP. Includes related graph/lineage gaps (QC outputs, mapping suggestions, manual edits). |
| [#34](https://github.com/cestatech/ctsm_AIsquad/issues/34) | Business logic in route handlers | Medium | `csr.py`, `adam.py`, `approvals.py`, `users.py`, `statistical_qc.py` violate the Route→Service→Repository mandate. |
| [#35](https://github.com/cestatech/ctsm_AIsquad/issues/35) | Orphan `TraceabilityLink` model | Low | No migration, no usage; graph is canonical. Remove via ADR or migrate. |
| [#36](https://github.com/cestatech/ctsm_AIsquad/issues/36) | Redis provisioned but unused; jobs not durable | High | Redis is in requirements/compose/CI yet no code touches it. Generation jobs run via in-process `BackgroundTasks`; multi-worker deployments would double-execute recovered jobs; `AI_MAX_CONCURRENT_JOBS` is per-process only. |
| [#37](https://github.com/cestatech/ctsm_AIsquad/issues/37) | CIP decision quality | Medium | EDC generator logs a false `ARTIFACT_GENERATION` decision type for rule-based output; pipeline reasoning is thin; `BaseGenerator` hardcodes `confidence=0.9`. |

## 3. Regulatory Output Depth (no P21/Azure/model dependency)

| # | Issue | Severity | Summary |
|---|-------|----------|---------|
| [#38](https://github.com/cestatech/ctsm_AIsquad/issues/38) | SDTM/ADaM packaged as CSV, not XPT v5 | **High (regulatory)** | FDA requires SAS XPT v5 in eCTD M5. `xpt_export_service.py` is implemented and tested but wired into nothing — packaging uses `_render_domain_csv`. |
| [#39](https://github.com/cestatech/ctsm_AIsquad/issues/39) | CSR PDF & Reviewer's Guide are stub bytes | **High (regulatory)** | The submission ZIP contains fake `%PDF` placeholders while `csr_ich_e3_pdf_renderer.py`, `reviewers_guide_generator.py`, and `adrg_generation_service.py` sit unwired. |
| [#40](https://github.com/cestatech/ctsm_AIsquad/issues/40) | define.xml lacks codelists/origins/methods | Medium | Current export is structurally minimal; reuse `DataLineage` transformation logic for `MethodDef`s and bind CT codelists. |

## 4. Frontend

| # | Issue | Severity | Summary |
|---|-------|----------|---------|
| [#41](https://github.com/cestatech/ctsm_AIsquad/issues/41) | Zero component tests, masked by CI | High | CLAUDE.md mandates component tests for forms/approvals; RTL was removed in the dep cleanup; `--passWithNoTests` flags mean CI stays green with an empty suite. |
| [#42](https://github.com/cestatech/ctsm_AIsquad/issues/42) | Error states, shared job table, mega-pages | Medium | ~25 pages lack `QueryState` error UI; generation job table duplicated; `studies/[id]` (~1,047 lines) and `artifacts/[artifactId]` (~954 lines) need splitting. |
| [#43](https://github.com/cestatech/ctsm_AIsquad/issues/43) | Branding drift TrialGenesis vs Celerius | Low | 19 occurrences including `APP_NAME`, OpenAPI title, and `SMTP_FROM` default. |

## 5. CI, Dependencies, Docs, Ops

| # | Issue | Severity | Summary |
|---|-------|----------|---------|
| [#44](https://github.com/cestatech/ctsm_AIsquad/issues/44) | CI hardening | Medium | mypy installed but never executed; `--cov-fail-under=0`; E2E only on push to main; ad-hoc `pytest-timeout` install; lint tools not pinned for local use. |
| [#45](https://github.com/cestatech/ctsm_AIsquad/issues/45) | Backend dependency cleanup | Low | `passlib` and `fastapi-mail` unused; `httpx` pinned twice; `openpyxl` unpinned. |
| [#46](https://github.com/cestatech/ctsm_AIsquad/issues/46) | Stale phase docs | Low | `phase_completion_status.md` lists bulk reject, impact analysis, listing/figure catalog, CSR prose, and idempotency hardening as "remaining" though all have shipped. |
| [#47](https://github.com/cestatech/ctsm_AIsquad/issues/47) | No readiness probe | Low | `/health` returns `ok` unconditionally — never touches the DB. |

## 6. Feature Proposals

| # | Issue | Summary |
|---|-------|---------|
| [#48](https://github.com/cestatech/ctsm_AIsquad/issues/48) | Dedicated dataset review UI + CSR section editor | Reviewers currently approve SDTM/ADaM through the generic artifact page; medical writers have no section-level CSR editor (with CIP override-reason capture). Pure frontend + existing-API work. |

### Additional improvement ideas (not yet filed — raise when prioritized)

- **N+1 query audit** on list endpoints with eager-loading review (cleanup report P4-17).
- **Multi-sheet Excel naming conventions** for regulatory submissions (Phase 2 leftover).
- **Per-tenant storage quotas** on uploads (noted in #30).
- **E2E generation UI polish** (Phase 1 leftover).
- **MFA support** — would strengthen the Part 11 signing story beyond password re-entry (#31).
- **Production deployment definition** — there is only `docker-compose.dev.yml`; the Nginx layer that CLAUDE.md assigns security headers (CSP/HSTS/X-Frame-Options) to does not exist in the repo yet. Provider-agnostic, so not blocked by the Azure decision.
- **React Query Devtools** wired behind `NODE_ENV === 'development'` (dep-report recommendation).

---

## What's in good shape

Worth stating so this document isn't read as all-negative:

- **Frontend type discipline:** strict mode on, zero `any`, zero stray `console.log`.
- **Append-only enforcement is real:** DB triggers block UPDATE/DELETE on `audit_logs` and `artifact_versions`.
- **RBAC test culture:** explicit 403 assertions; prior sprint closed upload/intake/approvals-queue RBAC gaps.
- **Refresh tokens:** random (non-JWT), stored hashed (SHA-256), rotated — matches the documented design.
- **Test base:** ~370 backend unit tests + integration + 6 Playwright E2E specs; CI runs lint, format, unit, integration on real Postgres.
- **Governance docs:** CLAUDE.md, ADRs, and cleanup reports made this audit largely a matter of verifying claims against code — most claims held.

## Suggested priority order

1. **#29, #24, #25** — small, well-bounded security/RBAC fixes (days).
2. **#26 → #27/#28** — email delivery unlocks invite, reset, and verification (one workstream).
3. **#38, #39** — large regulatory credibility win for low effort: the services already exist, they just need wiring.
4. **#33, #31** — CIP/Part 11 compliance gaps that get more expensive to backfill as data accumulates.
5. **#41, #44** — test/CI integrity so the rest of the work lands safely.
6. **#32, #36** — architectural consolidation, best done before more pipeline features stack on top.
