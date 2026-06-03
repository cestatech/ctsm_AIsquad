# ADR-0004: Mandatory AI Decision Logging and Human Override Framework

**Date:** 2026-06-03
**Status:** Accepted
**Deciders:** architect-agent, rbac-agent, audit-compliance-agent

---

## Context

The platform uses AI agents to automate clinical trial tasks: SDTM mapping, ADaM derivation, protocol analysis, eligibility checking, and more. Regulatory agencies (FDA, EMA) require that every AI-assisted decision be explainable, reviewable, and — where human experts disagree with the AI — overridable with a documented justification.

Without a formal AI decision logging system:
- AI actions are invisible to auditors
- There is no way to prove an AI output was reviewed by a qualified human
- Corrections to AI outputs have no audit trail
- The "explain this conclusion" question cannot be answered structurally

---

## Decision

Every AI agent action MUST create an `AIDecision` record BEFORE executing any downstream effect. Every human correction to an AI-generated value MUST create a `HumanOverride` record. Both record types are immutable and append-only.

**AIDecision records** capture:
- Which agent produced the decision (agent_name, agent_version)
- Which model was used (model_id, model_provider, prompt_hash)
- The full input context (input_context JSONB)
- The agent's reasoning (reasoning text)
- The output (output JSONB)
- Confidence score (0–1)
- Review status lifecycle: PENDING_REVIEW → ACCEPTED / REJECTED / OVERRIDDEN
- Who reviewed it and when

**HumanOverride records** capture:
- Which AI decision is being overridden (ai_decision_id — nullable for manual corrections)
- The original value and the corrected value
- A mandatory textual justification (reason field, cannot be empty)
- Who made the correction (actor_user_id)
- Context: what entity and field was changed

**Lifecycle rule:**
- AI agents set their own decisions to PENDING_REVIEW
- Humans accept or reject via the AI Decision Review screen
- Acceptance transitions to ACCEPTED
- Rejection requires notes and transitions to REJECTED
- If a human accepts but then manually changes a value, a HumanOverride is created and the decision transitions to OVERRIDDEN

---

## Enforcement

- `AIDecisionService.begin_decision()` must be called at the START of every AI operation
- `AIDecisionService.complete_decision()` must be called with the output BEFORE the transaction commits
- Any AI agent that writes data without calling these methods is in violation of this ADR
- The `audit-compliance-agent` audits all AI agent code for compliance with this pattern

---

## Alternatives Considered

1. **Post-hoc logging**: Log AI actions after the fact via database triggers or event subscriptions. Rejected because it cannot capture the reasoning and prompt hash that are available only at the time of generation.

2. **Append to audit_log table**: Reuse the existing `AuditLog` table. Rejected because AI decisions have a fundamentally different schema (confidence, reasoning, prompt hash, model ID, review lifecycle) that would pollute the audit log structure.

3. **External observability system (LangSmith, Helicone)**: Useful for LLM observability but not for regulatory evidence. External systems are out of our control and cannot be included in a submission package. In-database records are authoritative.

---

## Consequences

**Positive:**
- Every AI output is visible, reviewable, and traceable
- Human corrections are never lost — the full correction chain is preserved
- The "explain this conclusion" question has a structured, queryable answer
- Regulatory submissions can include a machine-readable AI decision log
- Waivers, overrides, and rejections are all documented with mandatory justifications

**Negative:**
- Every AI agent call has overhead (one DB write before execution)
- AI agents must be structured to thread the `decision_id` through downstream writes
- The `PENDING_REVIEW` queue can grow if reviewers don't process decisions regularly (mitigated by the AI Decision Review screen and alerts)

---

## Implementation

- Models: `backend/app/models/intelligence.py` (AIDecision, HumanOverride)
- Services: `backend/app/services/intelligence_service.py` (AIDecisionService, HumanOverrideService)
- Repository: `backend/app/repositories/intelligence_repository.py`
- API: `backend/app/api/v1/endpoints/intelligence.py`
- Migration: `backend/alembic/versions/20260603_0002_context_graph_intelligence.py`
- Agents: context-graph-agent.md, data-lineage-agent.md
