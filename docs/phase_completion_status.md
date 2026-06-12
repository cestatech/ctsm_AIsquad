# Phase Completion Status

**Last updated:** 2026-06-12 (verified against main at HEAD; see issue #46)
**Basis:** TrialGenesis phased workflow (ADR-0008 pipeline phases 0–8)

Percentages reflect **functional completeness** toward each phase Definition of Done, not regulatory validation readiness.

> **Maintenance convention:** any PR that completes an item listed under a
> "Remaining" section below must update this document in the same PR. The PR
> template includes a checklist item for this. Stale status docs mislead
> contributors and auditors — see issue #46.

---

## Summary

| Phase | Name | Completion | Status |
|-------|------|------------|--------|
| **0** | Platform baseline | **100%** | Complete |
| **1** | Sponsor intake + AI generation | **95%** | Complete |
| **2** | Raw data upload + mapping | **98%** | Complete |
| **3** | Context graph event contract | **100%** | Complete |
| **4** | Raw → SDTM pipeline | **95%** | Complete (no P21) |
| **5** | SDTM → ADaM | **98%** | Complete (no P21) |
| **6** | ADaM → TLF | **95%** | Complete (no P21) |
| **7** | TLF → CSR | **98%** | Complete |
| **8** | Submission packaging | **Demonstrable+** | eCTD backbone + SDRG shipped; package wiring gaps remain |

**Overall pipeline (Phases 0–8): ~97%**

---

## Phase 0 — Platform Baseline (100%)

- Multi-tenant auth, RBAC, audit log, artifact lifecycle
- Docker dev environment, migrations, seed data
- 541 tests passing; CI gates: ruff lint/format, mypy, 55% coverage floor, E2E on PRs
- Security hardening: per-IP login rate limiting (#24), proxy-aware audit IP capture (#25), content-based upload validation (#30)

---

## Phase 1 — Sponsor Intake + AI Generation (95%)

**Done:** Intake chat, study brief compile, Protocol/ICF/SAP generators, brief→prompt wiring, graph edges on generation, model evaluation harness for generator prompts (`backend/eval/`).

**Remaining (~5%):** E2E generation UI polish; production email for invites (fastapi-mail adopted; see the credential-lifecycle issue).

---

## Phase 2 — Raw Data Upload + Mapping (98%)

**Done:** CSV/Excel upload, column profiling, manual + AI mapping suggestions, approval workflow, PHI masking, data lineage, audit actions, bulk approve, **bulk reject (#12)**, CSV mapping export, Excel sheet name sanitization, content-based MIME validation on upload (#30).

**Remaining (~2%):** Multi-sheet Excel naming conventions for regulatory submissions.

---

## Phase 3 — Context Graph Events (100%)

**Done:** GraphEventWriter, idempotency, study summary, entity drilldowns, events viewer, artifact/study panels, downstream impact analysis UI (graph explorer + entity panels), audit+graph dual-write integration tests, **impact analysis on traceability gap report (#16)**, **idempotency key hardening via SHA-256 hash column for long edge types (#10, migration `20260611_0014`)**.

**Remaining:** none.

---

## Phase 4 — Raw → SDTM (95%)

**Done:**

- `SDTMGenerationService` — AI derivation from approved mappings (per-dataset + full-study merge)
- `POST /raw-data/datasets/{id}/generate-sdtm`
- `GET /raw-data/studies/{id}/sdtm-readiness`
- `POST /raw-data/studies/{id}/generate-sdtm` — merges all study datasets
- `GET /artifacts/{id}/define-xml` — minimal CDISC define.xml 2.1 export
- SDTM_DATASET artifact creation (DRAFT, review-required)
- Context graph: RAW_DATASET → SDTM, field MAPS_TO variable, eCRF → SDTM edges
- Study/protocol traceability links (SDTM PART_OF study, DERIVED_FROM protocol)
- Field-level lineage (raw → SDTM)
- Internal CDISC validation + `ValidationEvidence` per rule finding
- Frontend: per-dataset + study-level SDTM generation; define.xml download
- **Dedicated SDTM review UI (#14)**
- Pinnacle 21 stub ready (`PINNACLE21_*` env vars)
- Dual-programmer R QC (`RAW_TO_SDTM`) on every generation

**Remaining (~5%):**

- Pinnacle 21 production credentials (adapter implemented; `PINNACLE21_ENABLED=false` by default)
- Full regulatory define.xml (codelists, origins, computational derivations)
- SAS XPT transport export: `xpt_export_service.py` is implemented but has **no call sites** — wire to an endpoint and/or submission packaging (see its dedicated issue)

---

## Phase 5 — SDTM → ADaM (98%)

**Done:**

- `ADAMGenerationService` — AI derivation from SDTM artifact content (per-artifact + study merge)
- `GET /adam/studies/{id}/adam-readiness`
- `POST /adam/studies/{id}/generate-adam`
- `POST /adam/artifacts/{id}/generate-adam`
- ADAM_DATASET artifact with ADSL (+ ADAE when AE domain present)
- Context graph: SDTM → ADaM edges, variable-level lineage
- Internal CDISC ADaM validation + ValidationEvidence
- Frontend: study ADaM panel + SDTM artifact "Generate ADaM" action
- Deterministic fallback when no Anthropic API key
- **ADaM define.xml and ADRG export endpoints (#13)**
- Dual-programmer R QC (`SDTM_TO_ADAM`) on every generation

**Remaining (~2%):**

- Pinnacle 21 ADaM rule set integration

---

## Phase 6 — ADaM → TLF (95%)

**Done:**

- `TLFGenerationService` — derive TLF package from ADAM_DATASET artifact
- `POST /tlf/artifacts/{id}/generate-tlf`
- TLF artifact with demography / disposition table specs
- TLF render endpoint outputs **PDF** (`/render` returns `application/pdf`)
- **Listing/Figure catalog from SAP traceability (#15)**
- Dual-programmer R QC (`ADAM_TO_TLF`) on every generation
- Internal ICH-E3-TLF validation trigger
- Frontend: "Generate TLF" on ADaM artifacts + QC panel on artifact detail

**Remaining (~5%):**

- Pinnacle 21 TLF rule set integration
- Submission package assembly still embeds TLF as RTF (`TLFRenderer.render_to_rtf`); align with the PDF render path

---

## Phase 7 — TLF → CSR (98%)

**Done:**

- `CSRGenerationService` — AI-assisted + deterministic ICH E3 CSR assembly from TLF packages
- **Full CSR prose generation (#17)** — sections are generated prose, no longer outlines/shells
- `GET /csr/studies/{id}/csr-readiness`
- `POST /csr/studies/{id}/generate-csr` — merge all study TLF artifacts
- `POST /csr/artifacts/{id}/generate-csr` — assemble from single TLF artifact
- CSR artifact with ICH E3 sections (1, 2, 9–15), synopsis, TLF integration map
- Protocol/SAP context pulled into synopsis and objectives when available
- Context graph: TLF → CSR edges, Protocol DERIVED_FROM links, section lineage
- Internal ICH E3 CSR validation (`ICH-E3-CSR` rule set)
- **Study Data Reviewer's Guide (SDRG) PDF generation (#21)** — wired at CSR endpoints
- eCTD Module 5 folder structure preview in CSR content
- Frontend: study CSR panel + TLF artifact "Generate CSR" action

**Remaining (~2%):**

- Dedicated CSR section editor UI

---

## Phase 8 — Submission Packaging (Demonstrable+)

**Done:**

- `SubmissionService` — readiness validation, eCTD m5 folder assembly, manifest checksums
- **eCTD 3.2.2 XML backbone export with honest checksums (#18)** — wired at submission endpoints
- Async assembly via `submission_executor` (DRAFT → PACKAGING → READY)
- REST API: readiness, create, list, manifest, ZIP download, eCTD XML ZIP
- Frontend: submission page wired to backend (create, poll, manifest, download)
- Manifest: per-file `grade`, `data_classification: SYNTHETIC_DEMO`, placeholder badges
- **Pluggable storage backend: local filesystem + Azure Blob (#20)**
- RBAC: Admin create/download; Reviewer manifest; Contributor read-only status
- E2E: `frontend/e2e/submission-packaging.spec.ts`
- Demo seed: `demo_program_seed.py --approve-artifacts`
- Runbook: `docs/runbooks/submission_demo.md`

**Real vs placeholder in the package ZIP** (verified in `submission_service.py`):

| Output | Grade |
|--------|-------|
| SDTM/ADaM CSVs, define.xml, TLF RTF, manifest.json, eCTD XML backbone | Generated |
| CSR PDF, Reviewer's Guide PDF | **Placeholder in package assembly** — real generators exist (`pdf_exporter.py`, `reviewers_guide_generator.py`) and are wired at standalone endpoints, but `SubmissionService` still emits placeholder bytes |

**Not regulatory-ready (planned):**

- Wire real CSR PDF and SDRG generators into package assembly (currently placeholders in the ZIP)
- Wire `xpt_export_service.py` so datasets ship as SAS XPT instead of CSV
- Pinnacle 21 production validation

---

## External dependencies

| Item | Blocks | Workaround |
|------|--------|------------|
| Pinnacle 21 license | P21 validation evidence | `engine=internal` |
| BAA/DPA | Real PHI in production | Synthetic data for dev |
| `ANTHROPIC_API_KEY` in root `.env` | AI features in Docker | Required for live AI |

---

## Cross-cutting: Dual-Programmer R QC

All data pipeline steps (Phases 4–6) run **independent primary + QC statistical programmer** R programs on artifact generation. See ADR-0009.

- `statistical_program_qc_runs` — append-only QC run records
- `GET /statistical-qc/runs` — list/filter by study or output artifact
- Frontend `StatisticalQCPanel` on artifact detail pages

When `Rscript` is not installed (typical dev Docker), programs are stored with status `R_UNAVAILABLE` for manual execution.

---

## Recommended next step

**Close the package-assembly gaps** — wire the real CSR PDF, SDRG, and XPT exports into `SubmissionService` so the ZIP contains no placeholders (see `docs/phased_implementation_plan.md` Phase 2).
