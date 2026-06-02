# Celerius Development Roadmap

This roadmap is owned by `product-manager-agent` and reviewed by `architect-agent`.

---

## Phase 1: Authentication + RBAC
**Goal:** Secure, multi-tenant user management foundation

**Deliverables:**
- User registration with organization creation
- Email/password authentication with JWT + refresh tokens
- Refresh token rotation with httpOnly cookie storage
- Login rate limiting (5 attempts / 15 min per IP)
- User invite flow (Admin invites users with assigned role)
- User deactivation (revokes active tokens)
- Password change endpoint
- `GET /users/me` profile endpoint
- Full test coverage for all auth flows including adversarial cases

**Definition of Done:**
- All auth endpoints implemented and tested
- RBAC enforcement tested for all three roles
- Audit log entries created for: login, logout, failed login, user created, user deactivated
- Refresh token rotation verified (old token invalid after refresh)

---

## Phase 2: Study Workspace
**Goal:** Container for all study work with member management

**Deliverables:**
- Study CRUD (create, read, update, archive)
- Protocol number uniqueness per organization
- Study member assignment (add/remove/change role)
- Study status lifecycle (DRAFT → ACTIVE → COMPLETED/ARCHIVED)
- Study list + detail pages (frontend)
- Member management UI (Admin only)
- Study overview dashboard card

**Definition of Done:**
- Archived studies cannot have new artifacts
- Admin-only operations return 403 for other roles
- Audit log entries for all study and membership changes

---

## Phase 3: Artifact Management
**Goal:** Create, version, and manage clinical trial documents

**Deliverables:**
- Artifact CRUD for all supported artifact types
- Automatic version 1 creation on artifact creation
- Content update creates new version (no in-place updates)
- Version history list endpoint
- Version comparison endpoint (JSON Patch diff)
- File attachment upload (binary artifacts)
- Artifact list page with status badges
- Artifact detail page with version history
- Version comparison UI

**Definition of Done:**
- Content changes always produce new version records
- Version records are immutable (trigger tested)
- Locked artifacts reject all content edits
- Version comparison returns correct diff for known inputs

---

## Phase 4: Approval Workflow
**Goal:** Controlled review, approval, and locking of artifacts

**Deliverables:**
- Submit for review transition (Contributor/Admin)
- Approve transition with electronic signature capture (Reviewer/Admin)
- Reject transition with required comment (Reviewer/Admin)
- Lock transition (Admin only)
- Amend locked artifact (creates new DRAFT version, marks old as AMENDED)
- Approval history list
- Pending reviews dashboard
- Status badge components for all statuses
- Approve/reject modal with comment field

**Definition of Done:**
- All valid transitions work
- All invalid transitions return 409 with clear error
- Approval records are immutable once created
- Electronic signature fields populated on every approval record
- Audit entries for every transition

---

## Phase 5: Audit Logging
**Goal:** Searchable, exportable audit trail for regulatory compliance

**Deliverables:**
- Audit log search endpoint with filters (action, user, date, resource)
- Audit log detail endpoint
- Audit log export (JSON, CSV)
- Audit log viewer UI with filters and pagination
- Audit log detail modal (before/after state diff)
- Export button with download

**Definition of Done:**
- All data-modifying operations produce audit entries (verified by audit-compliance-agent review)
- Audit records cannot be modified (verified by DB trigger test)
- Search returns correct results for all filter combinations
- Export generates complete, correctly-formatted file

---

## Phase 6: AI Module Placeholders
**Goal:** Generation infrastructure ready for real AI modules

**Deliverables:**
- `GenerationJob` data model and API
- Placeholder services for: Protocol, ICF, SAP, SDTM, ADaM, TLF, CSR
- Each placeholder returns a realistic mock DRAFT artifact within 2 seconds
- Generation job polling endpoint
- Job cancellation endpoint
- Generation input/output fully logged for reproducibility
- "Generate Draft" button in artifact creation UI
- Job status indicator (pending / running / complete / failed)

**Definition of Done:**
- All placeholder endpoints functional
- Generated artifacts always created as DRAFT
- All generation inputs captured in `generation_jobs` table
- Audit log entries: ai.generation_started, ai.generation_completed

---

## Phase 7: Protocol Generator
**Goal:** AI-assisted protocol drafting from study concept

**Deliverables:**
- Replace Protocol placeholder with real LLM-powered generator
- Context assembly: study metadata, indication, regulatory region, therapeutic area
- ICH E6(R3) section structure
- Protocol template versioning
- Structured output with editable sections
- Protocol-specific diff viewer (section-level comparison)

**Definition of Done:**
- Generated protocols follow ICH E6 structure
- Generation is reproducible given same inputs + model version
- Protocol enters workflow as DRAFT requiring approval

---

## Phase 8: SAP Generator
**Goal:** SAP generation from approved protocol

**Deliverables:**
- SAP generator using approved Protocol as primary context
- Statistical methodology configuration
- Analysis population definitions from protocol endpoints
- Table/figure shell list generation
- SAP-protocol traceability links created automatically

**Dependencies:** Phase 7 (approved Protocol artifact)

---

## Phase 9: SDTM Automation
**Goal:** CDISC SDTM dataset generation from raw data + eCRF

**Deliverables:**
- CDASH → SDTM mapping engine
- Core domains: DM, AE, CM, EX, LB, VS, MH, DS
- define.xml generation
- SDTM-eCRF traceability links

**Dependencies:** Phase 6 (EDC/eCRF artifact type), Phase 3 (file attachment uploads)

---

## Phase 10: ADaM Automation
**Goal:** ADaM analysis dataset generation from SDTM

**Deliverables:**
- ADSL, ADAE, ADLB, ADTTE derivations
- ADaM specifications document generation
- SDTM → ADaM traceability links
- Analysis population derivation from SAP specifications

**Dependencies:** Phase 8 (SAP), Phase 9 (SDTM)

---

## Phase 11: TLF Automation
**Goal:** Tables, Listings, Figures from ADaM + SAP shells

**Deliverables:**
- TLF shell parsing from SAP
- Statistical output generation (RTF/PDF)
- TLF package assembly
- ADaM → TLF traceability links

**Dependencies:** Phase 8 (SAP), Phase 10 (ADaM)

---

## Phase 12: Validation Engine
**Goal:** CDISC validation with Pinnacle 21 integration

**Deliverables:**
- Internal CDISC rule engine (basic)
- Pinnacle 21 API integration
- Validation report viewer with issue categorization
- Issue resolution workflow
- Validation evidence package for submission

**Dependencies:** Phase 9 (SDTM), Phase 10 (ADaM)

---

## Phase 13: CSR Generation
**Goal:** AI-assisted Clinical Study Report from all upstream artifacts

**Deliverables:**
- ICH E3 section structure
- Context assembly from Protocol + SAP + TLFs + Narratives
- CSR draft generation
- Cross-reference linking to approved artifacts
- Full traceability chain: Protocol → ... → CSR

**Dependencies:** All upstream phases complete with approved artifacts

---

## Milestone Summary

| Milestone | Phases | Target |
|-----------|--------|--------|
| Platform Foundation | 1–6 | MVP |
| Document Automation | 7–8 | Beta |
| Data Standards Automation | 9–12 | GA |
| Full Submission Package | 13 | Regulatory Release |
