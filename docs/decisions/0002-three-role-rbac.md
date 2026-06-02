# ADR-0002: Three-Role RBAC Model (Admin, Contributor, Reviewer)

**Date:** 2026-06-02
**Status:** Accepted
**Authors:** architect-agent, rbac-agent
**Reviewers:** product-manager-agent, audit-compliance-agent

---

## Context

Clinical trial platforms require controlled access because mistakes in artifacts can affect patient safety and regulatory submissions. We need an access control model that is simple enough to be understood by non-technical clinical users, but secure enough to enforce the review-and-approval chain required by GxP and 21 CFR Part 11.

---

## Decision

We will implement exactly three roles: **Admin**, **Contributor**, and **Reviewer**. These roles are fixed for MVP and beyond. New roles require an ADR and architecture review.

Role assignments are **study-scoped**: a user can be Contributor on Study A and Reviewer on Study B. Organization-level Admin supersedes all study-level roles within the organization.

---

## Consequences

### Positive
- Simple enough for clinical operations users to understand without training
- Enforces the regulatory requirement that approvers are separate from creators
- Study-scoped roles allow flexible team composition
- Minimal attack surface — fewer permission combinations to audit

### Negative
- Cannot model fine-grained permissions within a role (e.g., a Contributor who can only edit SAPs)
- Adding a fourth role in the future requires careful migration of existing role data and permission matrix changes

---

## Alternatives Considered

### Alternative A: ABAC (Attribute-Based Access Control)
**Why rejected:** Overly complex for initial MVP. Clinical users need predictable role behavior. ABAC models are hard to audit.

### Alternative B: 5-role model (Owner, Author, Reviewer, Approver, Auditor)
**Why rejected:** Adds complexity without clear user value at MVP stage. The three-role model handles all regulatory-required separations. Can revisit in a future ADR.

---

## References

- ICH E6(R3) — roles in clinical trial document management
- 21 CFR Part 11 — separation of duties requirement
- CLAUDE.md — RBAC rules section
