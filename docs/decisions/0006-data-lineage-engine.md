# ADR-0006: Data Lineage Engine — Field-Level and Artifact-Level Provenance

**Date:** 2026-06-03
**Status:** Accepted
**Deciders:** architect-agent, data-lineage-agent, audit-compliance-agent

---

## Context

CDISC submissions require that every derived variable can be traced to its source. FDA reviewers routinely ask: *"Where does ADTTE.AVAL come from?"* or *"Which eCRF field sourced DM.DTHFL?"* Without explicit lineage records, answering these questions requires manual inspection of mapping specifications, SDTM programming, and ADaM specs — a process that takes days and is error-prone.

The Context Graph (ADR-0003) tracks entities and relationships at the graph level. Lineage is a complementary, more detailed layer that captures the specific transformation logic between fields, not just the fact that a relationship exists.

---

## Decision

Two lineage models:

**`DataLineage` (field-level):** Records the transformation from one specific field to another.
- `source_type` / `source_field` / `source_domain` — where data came from (e.g., eCRF form field)
- `target_type` / `target_field` / `target_domain` — where data went (e.g., SDTM variable)
- `transformation_logic` — the actual code, formula, or rule as a string
- `is_ai_generated` + `ai_decision_id` — whether AI produced this mapping

**`ArtifactLineage` (document-level):** Records the derivation from one artifact to another.
- `source_artifact_id` → `target_artifact_id` (e.g., Protocol → SAP)
- `relationship_type` — DERIVED_FROM, REFERENCES, SUPERSEDES, etc.
- `derivation_notes` — human-readable description

Both are append-only. The "Show Your Work" endpoint (`GET /api/v1/intelligence/lineage/chain`) returns the full upstream + downstream chain for any entity via service-layer BFS.

---

## Consequences

**Positive:**
- Any derived variable can be traced to its raw source in one API call
- Transformation logic is stored as code — executable, diffable, reviewable
- Supports automated regulatory package generation (define.xml derivation notes)

**Negative:**
- Agents must explicitly record lineage — it doesn't happen automatically from graph edges
- Transformation logic strings require discipline (agents must write real formulas, not placeholders)

---

## Implementation

- Models: `backend/app/models/intelligence.py` — `DataLineage`, `ArtifactLineage`
- Service: `backend/app/services/intelligence_service.py` — `DataLineageService`
- Repository: `backend/app/repositories/intelligence_repository.py` — `DataLineageRepository`
- API: `GET /api/v1/intelligence/lineage/chain`
- Frontend: `/intelligence/lineage` — upstream/downstream explorer
