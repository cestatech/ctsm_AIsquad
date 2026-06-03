# ADR-0005: Human Override Framework — Immutable Correction Records

**Date:** 2026-06-03
**Status:** Accepted
**Deciders:** architect-agent, audit-compliance-agent, rbac-agent

---

## Context

AI agents in Celerius generate mappings, derivations, and clinical conclusions that humans must be able to correct. Without a structured correction mechanism, corrections are lost in database updates and the audit trail shows only the final value — not what the AI originally produced, why it was wrong, or who corrected it.

For regulatory submissions (FDA, EMA), it is not sufficient to show that the final dataset is correct. Reviewers may ask: *"Was this value AI-generated? Was it corrected? Why?"* These questions must be answerable from the system.

---

## Decision

Every time a human corrects an AI-generated value, an immutable `HumanOverride` record is created capturing:

- `original_value` — what the AI produced (JSONB)
- `new_value` — what the human set it to (JSONB)
- `reason` — mandatory justification, minimum 1 character (enforced in service layer)
- `field_path` — the specific field that was corrected (dot-path notation)
- `context_type` — what kind of entity was corrected (e.g., `ai_decision`, `sdtm_mapping`)
- `ai_decision_id` — FK to the originating AI decision, if applicable
- `actor_user_id` — who made the correction (from JWT, not from request body)
- `override_type` — classification: CORRECTION, REFINEMENT, UNIT_CORRECTION, ADDITION, etc.

`HumanOverride` records are append-only. There is no update or delete endpoint. The table's database role has INSERT only.

---

## Consequences

**Positive:**
- Complete correction history for any AI-generated value
- Regulators can see the full before/after for any field
- Patterns in AI errors become visible (same field corrected repeatedly → agent needs retraining)
- Mandatory justification creates accountability

**Negative:**
- Frontend must call the override endpoint every time a user edits an AI-generated field — requires UI instrumentation
- Storage grows with every correction (accepted; audit records are cheap)

---

## Implementation

- Model: `backend/app/models/intelligence.py` — `HumanOverride`
- Service: `backend/app/services/intelligence_service.py` — `HumanOverrideService.record_override()`
- Repository: `backend/app/repositories/intelligence_repository.py` — `HumanOverrideRepository`
- API: `POST /api/v1/intelligence/overrides`, `GET /api/v1/intelligence/overrides`
- Frontend: `/intelligence/overrides` — immutable log view
