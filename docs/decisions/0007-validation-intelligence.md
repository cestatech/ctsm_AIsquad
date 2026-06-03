# ADR-0007: Validation Intelligence — Per-Rule CDISC Evidence with Waiver Workflow

**Date:** 2026-06-03
**Status:** Accepted
**Deciders:** architect-agent, validation-intelligence-agent, audit-compliance-agent

---

## Context

CDISC conformance checking (Pinnacle 21, OpenCDISC) produces pass/fail results per rule. In the current industry standard, these results are stored as static reports — a PDF or CSV that a data manager reviews manually. There is no structured way to:

1. Store the evidence for each rule check alongside the data it checked
2. Record a waiver with a regulatory-grade justification when a rule cannot be fixed
3. Link a validation finding to the AI decision that produced the data being checked

For FDA submission readiness, waivers must be documented in the Reviewer's Guide with justification. Without structured waiver records, this documentation is assembled manually from emails and meeting notes — a compliance risk.

---

## Decision

A `ValidationEvidence` record is created per rule check, capturing:

- `rule_id` / `rule_name` / `rule_category` — the specific CDISC rule (e.g., SD0083)
- `cdisc_standard` — SDTM-IG-3.3, ADaM-IG-1.1, etc.
- `subject_type` / `subject_field` — what was checked (e.g., `DM.RFSTDTC`)
- `status` — PENDING / PASS / FAIL / WARNING / WAIVED
- `finding_severity` — ERROR / WARNING (null for PASS)
- `finding_message` / `finding_details` — structured finding with affected record counts
- `is_ai_evaluated` + `ai_decision_id` — whether AI ran this check
- `waived_by_id` / `waiver_reason` / `waived_at` — waiver audit trail

**Waiver rule:** A waiver requires a non-empty `waiver_reason` stored on the evidence record AND a corresponding `HumanOverride` record (per ADR-0005). Both are mandatory. The service layer enforces this — an empty reason raises HTTP 422.

Waivers require REVIEWER or ADMIN role. The waiver reason flows directly into the regulatory submission package.

---

## Consequences

**Positive:**
- Every CDISC finding has a structured, queryable record — not just a report file
- Waivers are auditable and linked to the person who granted them
- AI-generated validation can be reviewed like any other AI decision (linked via `ai_decision_id`)
- Waiver reasons are machine-readable — can be auto-populated into define.xml reviewer notes

**Negative:**
- Validation engines (Pinnacle 21 integration) must be instrumented to write `ValidationEvidence` records instead of just producing reports
- More storage than flat report files (accepted; structured data is the point)

---

## Implementation

- Model: `backend/app/models/intelligence.py` — `ValidationEvidence`
- Service: `backend/app/services/intelligence_service.py` — `ValidationIntelligenceService`
- Repository: `backend/app/repositories/intelligence_repository.py` — `ValidationEvidenceRepository`
- API: `GET /api/v1/intelligence/validation-evidence`, `POST /api/v1/intelligence/validation-evidence/{id}/waive`
- Frontend: `/intelligence/validation` — findings dashboard with waiver modal
