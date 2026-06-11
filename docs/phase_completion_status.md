# Phase Completion Status

**Last updated:** 2026-06-08  
**Basis:** TrialGenesis phased workflow (ADR-0008 pipeline phases 0–8)

Percentages reflect **functional completeness** toward each phase Definition of Done, not regulatory validation readiness.

---

## Summary

| Phase | Name | Completion | Status |
|-------|------|------------|--------|
| **0** | Platform baseline | **100%** | Complete |
| **1** | Sponsor intake + AI generation | **95%** | Complete |
| **2** | Raw data upload + mapping | **95%** | Complete |
| **3** | Context graph event contract | **95%** | Complete |
| **4** | Raw → SDTM pipeline | **95%** | Complete (no P21) |
| **5** | SDTM → ADaM | **95%** | Complete (ADLB/ADVS/ADTTE auto-derivation) |
| **6** | ADaM → TLF | **95%** | Complete (no P21) |
| **7** | TLF → CSR | **95%** | Complete |
| **8** | Submission packaging | **Demonstrable** | Backend + frontend E2E (Phase 1) |

**Overall pipeline (Phases 0–8): ~95%**

---

## Phase 0 — Platform Baseline (100%)

- Multi-tenant auth, RBAC, audit log, artifact lifecycle
- Docker dev environment, migrations, seed data
- 316+ tests passing, smoke checklist green

---

## Phase 1 — Sponsor Intake + AI Generation (95%)

**Done:** Intake chat, study brief compile, Protocol/ICF/SAP generators, brief→prompt wiring, graph edges on generation.

**Remaining (~5%):** E2E generation UI polish; production email for invites.

---

## Phase 2 — Raw Data Upload + Mapping (95%)

**Done:** CSV/Excel upload, column profiling, manual + AI mapping suggestions, approval workflow, PHI masking, data lineage, audit actions, bulk approve, CSV mapping export, Excel sheet name sanitization.

**Remaining (~5%):** Multi-sheet Excel naming conventions for regulatory submissions; bulk reject.

---

## Phase 3 — Context Graph Events (95%)

**Done:** GraphEventWriter, idempotency, study summary, entity drilldowns, events viewer, artifact/study panels, downstream impact analysis UI (graph explorer + entity panels), audit+graph dual-write integration tests.

**Remaining (~5%):** Impact analysis on traceability gap report; idempotency key length hardening for long edge types.

---

## Phase 4 — Raw → SDTM (95%)

**Done (this release):**

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
- Pinnacle 21 stub ready (`PINNACLE21_*` env vars)
- Dual-programmer R QC (`RAW_TO_SDTM`) on every generation — primary + independent QC R programs, output comparison when R available

**Remaining (~5%):**

- Pinnacle 21 production credentials (adapter implemented; `PINNACLE21_ENABLED=false` by default)
- Dedicated SDTM review UI (uses generic artifact + `/intelligence/decisions` today)
- Full regulatory define.xml (codelists, origins, computational derivations)

---

## Phase 5 — SDTM → ADaM (95%)

**Done:**

- `ADAMGenerationService` — AI derivation from SDTM artifact content (per-artifact + study merge)
- `GET /adam/studies/{id}/adam-readiness`
- `POST /adam/studies/{id}/generate-adam`
- `POST /adam/artifacts/{id}/generate-adam`
- ADAM_DATASET artifact with ADSL (+ ADAE when AE domain present)
- Context graph: SDTM → ADaM edges, variable-level lineage
- Internal CDISC ADaM validation + ValidationEvidence
- Frontend: study ADaM panel + SDTM artifact “Generate ADaM” action
- Deterministic fallback when no Anthropic API key
- Dual-programmer R QC (`SDTM_TO_ADAM`) on every generation

**Remaining (~5%):**

- Pinnacle 21 ADaM rule set integration
- ADaM define.xml / ADRG export

---

## Phase 6 — ADaM → TLF (95%)

**Done:**

- `TLFGenerationService` — derive TLF package from ADAM_DATASET artifact
- `POST /tlf/artifacts/{id}/generate-tlf`
- TLF artifact with demography / disposition table specs
- Dual-programmer R QC (`ADAM_TO_TLF`) on every generation
- Internal ICH-E3-TLF validation trigger
- Frontend: “Generate TLF” on ADaM artifacts + QC panel on artifact detail

**Remaining (~5%):**

- Full TLF rendering (RTF/PDF output)
- Pinnacle 21 TLF rule set integration
- Listing/Figure catalog from SAP traceability

---

## Phase 7 — TLF → CSR (95%)

**Done:**

- `CSRGenerationService` — AI-assisted + deterministic ICH E3 CSR assembly from TLF packages
- `GET /csr/studies/{id}/csr-readiness`
- `POST /csr/studies/{id}/generate-csr` — merge all study TLF artifacts
- `POST /csr/artifacts/{id}/generate-csr` — assemble from single TLF artifact
- CSR artifact with ICH E3 sections (1, 2, 9–15), synopsis, TLF integration map
- Protocol/SAP context pulled into synopsis and objectives when available
- Context graph: TLF → CSR edges, Protocol DERIVED_FROM links, section lineage
- Internal ICH E3 CSR validation (`ICH-E3-CSR` rule set)
- eCTD Module 5 folder structure preview in CSR content
- Frontend: study CSR panel + TLF artifact “Generate CSR” action

**Remaining (~5%):**

- Full CSR prose generation (sections are outlines/shells, not final medical writing)
- eCTD XML export and regulatory submission bundle (Phase 8)
- Dedicated CSR section editor UI

---

## Phase 8 — Submission Packaging (Demonstrable)

**Done:**

- `SubmissionService` — readiness validation, eCTD m5 folder assembly, manifest checksums
- Async assembly via `submission_executor` (DRAFT → PACKAGING → READY)
- REST API: readiness, create, list, manifest, ZIP download
- Frontend: submission page wired to backend (create, poll, manifest, download)
- Manifest: per-file `grade`, `data_classification: SYNTHETIC_DEMO`, placeholder badges
- TLF RTF via `TLFRenderer` in package assembly
- RBAC: Admin create/download; Reviewer manifest; Contributor read-only status
- E2E: `frontend/e2e/submission-packaging.spec.ts`
- Demo seed: `demo_program_seed.py --approve-artifacts`
- Runbook: `docs/runbooks/submission_demo.md`

**Real vs placeholder in ZIP:**

| Output | Grade |
|--------|-------|
| SDTM/ADaM CSVs, define.xml, TLF RTF, manifest.json | Generated |
| CSR PDF, Reviewer's Guide PDF | Placeholder (labeled in UI) |

**Not regulatory-ready (planned):**

- Real CSR PDF and Reviewer's Guide authoring
- Full eCTD XML export
- S3/Azure storage backend
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

**Regulatory output depth** — real CSR PDF, Reviewer's Guide, eCTD XML (see `docs/phased_implementation_plan.md` Phase 2).
