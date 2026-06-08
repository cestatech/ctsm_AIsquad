# ADR-0008: Phase 4+ Data Pipeline Scope and Product Decisions

**Date:** 2026-06-05
**Status:** Accepted
**Authors:** product-owner (eshaanraj), architect-agent
**Reviewers:** architect-agent, backend-agent, validation-intelligence-agent

---

## Context

Phases 0–3 (intake, generation, raw data upload/mapping, context graph events) are complete. Before building Phases 4–8 (SDTM → ADaM → TLF → CSR), the product owner must lock scope decisions that affect schema design, AI agent contracts, validation integration, and regulatory posture.

This ADR records those decisions as the authoritative input for all subsequent phase work.

---

## Decision

### Standards and validation

- **SDTM Implementation Guide:** SDTM IG **3.3** (not 3.4/3.5).
- **Conformance engine:** **Pinnacle 21** for CDISC validation runs and evidence capture.
- **Study scope:** **Full study** — all domains required for a complete submission dataset, not a single-domain pilot.

### Ingestion formats

- **Supported upload formats:** **CSV and Excel** (`.csv`, `.xlsx`, `.xls`).
- SAS transport and Define-XML are out of scope for Phase 4 ingestion (may be added later).

### AI-first workflow

- **All transformation steps are AI-assisted by default:**
  - Raw field profiling and mapping suggestions (existing Phase 2)
  - Raw → SDTM domain mapping and derivation (Phase 4)
  - SDTM → ADaM variable derivation (Phase 5)
  - ADaM → TLF specification and generation (Phase 6)
  - TLF + study artifacts → CSR section assembly (Phase 7–8)
- Every AI step must:
  1. Call `AIDecisionService.begin_decision()` before inference
  2. Register entities and edges in the Context Graph
  3. Record field-level lineage via `DataLineageService`
  4. Surface outputs as `PENDING_REVIEW` until a Reviewer or Admin accepts
  5. Capture human corrections as `HumanOverride` with mandatory reason

### Data types

- **Both synthetic and real patient data** will be used.
- Synthetic data runs must remain labeled `SYNTHETIC` with documented `random_seed`.
- Real patient data requires PHI handling per `backend/app/core/phi_masking.py` and tenant legal agreements (BAA/DPA) — operational responsibility of the deploying organization.

### End-to-end pipeline

The mandatory artifact chain for every study:

```
Raw (CSV/Excel) → SDTM → ADaM → TLF → CSR
```

Traceability must remain intact at each hop via Context Graph edges and Data Lineage records. Gaps detected by `/intelligence/traceability` must be resolvable before submission packaging.

---

## Consequences

### Positive

- Unambiguous target for SDTM agent prompts, P21 rule packs, and CDISC CT versioning (IG 3.3).
- Full-study scope prevents rework from partial-domain prototypes.
- AI-first + human-review model aligns with CIP regulatory posture.
- CSV/Excel covers the most common sponsor data delivery format.

### Negative

- SDTM IG 3.3 is older than current FDA preference (3.4+); migration path to newer IG must be planned before regulatory submission.
- Pinnacle 21 requires a commercial license and API/integration work — not a pure open-source path.
- Full-study AI mapping at scale increases API cost and review queue volume.
- Real PHI introduces legal, security, and operational overhead beyond code (BAA, de-identification SOPs, breach response).

### Neutral

- Excel parsing adds `openpyxl`/`xlrd` dependency and MIME validation work in upload service.
- Docker-only development is mandatory; Postgres is exposed on host port **5433** (see `docs/DOCKER_DEV.md`).

---

## Alternatives Considered

### SDTM IG 3.4 or 3.5
**Why rejected:** Product owner specified IG 3.3 for current build target. Can supersede this ADR when upgrading IG version.

### OpenCDISC instead of Pinnacle 21
**Why rejected:** Product owner specified Pinnacle 21 as the conformance authority.

### Single-domain pilot (DM only)
**Why rejected:** Product owner requires full-study coverage from the start.

### Human-only mapping with AI as optional assist
**Why rejected:** Product owner requires AI-based workflow throughout with human review gates, not manual-first.

---

## References

- ADR-0003: Context Graph Intelligence
- ADR-0004: AI Decision Logging
- ADR-0005: Human Override Framework
- ADR-0006: Data Lineage Engine
- ADR-0007: Validation Intelligence
- CDISC SDTM Implementation Guide v3.3
- Pinnacle 21 Enterprise (CDISC conformance)
