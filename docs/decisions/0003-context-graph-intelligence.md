# ADR-0003: Context Graph as the Intelligence Substrate

**Date:** 2026-06-03
**Status:** Accepted
**Deciders:** architect-agent, context-graph-agent, audit-compliance-agent

---

## Context

The Celerius platform needs to answer the regulatory question: *"How did you reach this conclusion?"* for every AI-generated artifact, every data transformation, and every mapping decision. The clinical trial lifecycle involves dozens of entities (objectives, endpoints, ECR fields, SDTM variables, ADaM variables, TLFs, CSR sections) connected by traceable relationships across the Objective → Endpoint → ECR → SDTM → ADaM → TLF → CSR chain.

Without an explicit traceability structure, answering provenance questions requires joining multiple domain tables in complex ad-hoc queries. This is not scalable and does not provide the narrative explainability required for regulatory submissions.

---

## Decision

We introduce a **Context Graph** — a PostgreSQL-backed, org-scoped, append-only graph of nodes and edges that indexes every entity and relationship in the clinical trial lifecycle.

**Architecture:**

- `graph_nodes`: lightweight index entries that point back to domain records via `external_id` / `external_type`. The graph node is NOT the system of record — the domain table is. The node exists only to enable graph traversal and display.
- `graph_edges`: directed relationships between nodes, with `edge_type`, optional `confidence`, and optional `ai_decision_id`. AI-generated edges must reference a decision record.
- `graph_events`: append-only audit log of every graph mutation. Provides a time-ordered view of how the graph evolved.

**Node types** cover the full clinical trial lifecycle (35 types in the initial schema).
**Edge types** cover the lineage chain, provenance relationships, and governance relationships (29 types in the initial schema).

**ContextGraphService** is the single entry point. Domain services and AI agents never write to `graph_nodes` or `graph_edges` directly — they call `ContextGraphService.register_domain_record()` and `ContextGraphService.create_relationship()`.

---

## Alternatives Considered

1. **Neo4j / dedicated graph database**: Provides richer traversal but adds infrastructure complexity. PostgreSQL recursive CTEs and the current traversal depth (max 20 hops) are sufficient for the MVP. This decision is revisitable at scale.

2. **Derived views from domain joins**: Simpler initially but produces ad-hoc provenance on demand rather than a persistent, queryable record. Cannot support "who changed this, when, and why" narrative queries.

3. **Event sourcing**: Captures changes but not the semantic relationship graph. Would require reconstructing the graph from events on every query.

---

## Consequences

**Positive:**
- Every entity can be traced from creation to CSR in a single graph traversal
- AI agents have a clear protocol for registering their outputs
- Regulatory submissions can include a machine-readable traceability map
- Human reviewers can navigate the "Context Graph Explorer" UI to understand any data point's full history
- The graph is tenant-isolated (organization_id on every node and edge)

**Negative:**
- Domain services must call ContextGraphService after every significant write (additional coordination)
- The graph can diverge from domain tables if a write succeeds but the graph registration fails (mitigated by always using the same transaction)
- Graph traversal for very deep lineage chains may require optimization (recursive CTEs or future Neo4j migration)

---

## Implementation

- Models: `backend/app/models/graph.py`
- Service: `backend/app/services/context_graph_service.py`
- Repository: `backend/app/repositories/graph_repository.py`
- API: `backend/app/api/v1/endpoints/graph.py`
- Migration: `backend/alembic/versions/20260603_0002_context_graph_intelligence.py`
- Agents: `context-graph-agent.md`
