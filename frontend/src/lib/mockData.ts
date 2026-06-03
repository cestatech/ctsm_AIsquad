import type { Artifact, ArtifactVersion, AuditLog, Study, StudyMember, User } from "@/types";

const NOW = new Date().toISOString();
const DAY_AGO = new Date(Date.now() - 86_400_000).toISOString();
const WEEK_AGO = new Date(Date.now() - 7 * 86_400_000).toISOString();
const MONTH_AGO = new Date(Date.now() - 30 * 86_400_000).toISOString();

const ORG_ID = "00000000-0000-0000-0000-000000000001";
const U1 = "00000000-0000-0000-0000-000000000010";
const U2 = "00000000-0000-0000-0000-000000000011";
const U3 = "00000000-0000-0000-0000-000000000012";
const U4 = "00000000-0000-0000-0000-000000000013";

export const MOCK_USERS: User[] = [
  {
    id: U1, organization_id: ORG_ID, email: "sarah.chen@pharmaco.com",
    full_name: "Dr. Sarah Chen", title: "Principal Investigator",
    is_active: true, is_system_admin: false, last_login_at: NOW, created_at: MONTH_AGO,
  },
  {
    id: U2, organization_id: ORG_ID, email: "james.rodriguez@pharmaco.com",
    full_name: "James Rodriguez", title: "Clinical Data Manager",
    is_active: true, is_system_admin: false, last_login_at: DAY_AGO, created_at: MONTH_AGO,
  },
  {
    id: U3, organization_id: ORG_ID, email: "priya.patel@pharmaco.com",
    full_name: "Dr. Priya Patel", title: "Medical Monitor",
    is_active: true, is_system_admin: false, last_login_at: WEEK_AGO, created_at: MONTH_AGO,
  },
  {
    id: U4, organization_id: ORG_ID, email: "michael.torres@pharmaco.com",
    full_name: "Michael Torres", title: "Biostatistician",
    is_active: false, is_system_admin: false, last_login_at: DAY_AGO, created_at: MONTH_AGO,
  },
];

export const MOCK_STUDIES: Study[] = [
  {
    id: "study-001", organization_id: ORG_ID, protocol_number: "CTG-2024-001",
    name: "NOVA-1: Phase 2 Study of NVX-001 in Advanced NSCLC",
    short_name: "NOVA-1",
    description: "A multicenter, open-label Phase 2 study evaluating the efficacy and safety of NVX-001 in patients with advanced non-small cell lung cancer who have failed prior platinum-based therapy.",
    indication: "Non-Small Cell Lung Cancer", therapeutic_area: "Oncology",
    phase: "PHASE_2", status: "ACTIVE", sponsor: "PharmaCo Therapeutics",
    regulatory_region: ["FDA", "EMA"], start_date: "2024-02-01", end_date: "2026-08-31",
    created_by_id: U1, created_at: MONTH_AGO, updated_at: DAY_AGO,
  },
  {
    id: "study-002", organization_id: ORG_ID, protocol_number: "CTG-2024-002",
    name: "AURORA: Phase 3 Cardiovascular Outcomes Trial",
    short_name: "AURORA",
    description: "A double-blind, placebo-controlled Phase 3 study evaluating the cardiovascular outcomes of AUR-200 in high-risk patients with established coronary artery disease.",
    indication: "Cardiovascular Disease", therapeutic_area: "Cardiology",
    phase: "PHASE_3", status: "ACTIVE", sponsor: "PharmaCo Therapeutics",
    regulatory_region: ["FDA"], start_date: "2024-05-15", end_date: "2027-05-15",
    created_by_id: U1, created_at: MONTH_AGO, updated_at: WEEK_AGO,
  },
  {
    id: "study-003", organization_id: ORG_ID, protocol_number: "CTG-2024-003",
    name: "BRIDGE-HF: Heart Failure Bridging Protocol",
    short_name: "BRIDGE-HF",
    description: "A Phase 2/3 bridging study evaluating BRG-100 in patients with heart failure with reduced ejection fraction (HFrEF) across three regulatory regions.",
    indication: "Heart Failure", therapeutic_area: "Cardiology",
    phase: "PHASE_2_3", status: "DRAFT", sponsor: "PharmaCo Therapeutics",
    regulatory_region: ["FDA", "EMA", "PMDA"], start_date: "2024-09-01", end_date: null,
    created_by_id: U2, created_at: WEEK_AGO, updated_at: WEEK_AGO,
  },
  {
    id: "study-004", organization_id: ORG_ID, protocol_number: "CTG-2023-004",
    name: "CLARITY-RMS: Phase 3 Multiple Sclerosis Trial",
    short_name: "CLARITY",
    description: "A Phase 3 randomized, double-blind study of CLR-500 versus standard of care in adult patients with relapsing-remitting multiple sclerosis.",
    indication: "Multiple Sclerosis", therapeutic_area: "Neurology",
    phase: "PHASE_3", status: "COMPLETED", sponsor: "PharmaCo Therapeutics",
    regulatory_region: ["FDA", "EMA"], start_date: "2023-01-01", end_date: "2024-12-31",
    created_by_id: U1, created_at: "2023-01-15T10:00:00Z", updated_at: MONTH_AGO,
  },
];

export const MOCK_ARTIFACTS: Artifact[] = [
  {
    id: "art-001", organization_id: ORG_ID, study_id: "study-001",
    artifact_type: "PROTOCOL", name: "NVX-001 Study Protocol v3.0",
    description: "Master protocol document for the NOVA-1 study",
    status: "APPROVED", current_version_id: "ver-003", current_version_number: 3,
    locked_at: null, tags: ["protocol", "master"], created_by_id: U2,
    created_at: MONTH_AGO, updated_at: WEEK_AGO,
  },
  {
    id: "art-002", organization_id: ORG_ID, study_id: "study-001",
    artifact_type: "ICF", name: "Informed Consent Form — Main Study",
    description: "Patient-facing informed consent document for the NOVA-1 main study cohort",
    status: "IN_REVIEW", current_version_id: "ver-002", current_version_number: 2,
    locked_at: null, tags: ["icf", "patient-facing"], created_by_id: U2,
    created_at: MONTH_AGO, updated_at: DAY_AGO,
  },
  {
    id: "art-003", organization_id: ORG_ID, study_id: "study-001",
    artifact_type: "SAP", name: "Statistical Analysis Plan v1.0",
    description: "Pre-specified statistical analysis plan for the primary and key secondary endpoints",
    status: "DRAFT", current_version_id: "ver-001", current_version_number: 1,
    locked_at: null, tags: ["sap", "statistics"], created_by_id: U4,
    created_at: WEEK_AGO, updated_at: DAY_AGO,
  },
  {
    id: "art-004", organization_id: ORG_ID, study_id: "study-001",
    artifact_type: "EDC_CRF", name: "eCRF — Screening Visit",
    description: "Electronic case report form capturing screening assessments",
    status: "LOCKED", current_version_id: "ver-002", current_version_number: 2,
    locked_at: WEEK_AGO, tags: ["edc", "crf", "screening"], created_by_id: U2,
    created_at: MONTH_AGO, updated_at: WEEK_AGO,
  },
  {
    id: "art-005", organization_id: ORG_ID, study_id: "study-002",
    artifact_type: "PROTOCOL", name: "AUR-200 Study Protocol v1.0",
    description: "Master protocol document for the AURORA Phase 3 study",
    status: "IN_REVIEW", current_version_id: "ver-001", current_version_number: 1,
    locked_at: null, tags: ["protocol"], created_by_id: U2,
    created_at: WEEK_AGO, updated_at: DAY_AGO,
  },
];

export const MOCK_PENDING_APPROVALS = [
  {
    artifact_id: "art-002",
    artifact_version_id: "ver-002",
    artifact_name: "Informed Consent Form — Main Study",
    artifact_type: "ICF",
    study_id: "study-001",
    study_name: "NOVA-1",
    protocol_number: "CTG-2024-001",
    submitted_by: MOCK_USERS[1],
    submitted_at: DAY_AGO,
    version_number: 2,
  },
  {
    artifact_id: "art-005",
    artifact_version_id: "ver-001",
    artifact_name: "AUR-200 Study Protocol v1.0",
    artifact_type: "PROTOCOL",
    study_id: "study-002",
    study_name: "AURORA",
    protocol_number: "CTG-2024-002",
    submitted_by: MOCK_USERS[1],
    submitted_at: WEEK_AGO,
    version_number: 1,
  },
];

export const MOCK_AUDIT_LOGS: AuditLog[] = [
  {
    id: "log-001", organization_id: ORG_ID, actor_user_id: U3, actor: MOCK_USERS[2],
    action: "ARTIFACT_APPROVED", resource_type: "artifact", resource_id: "art-001",
    before_state: { status: "IN_REVIEW" }, after_state: { status: "APPROVED" },
    ip_address: "192.168.1.45", created_at: DAY_AGO,
  },
  {
    id: "log-002", organization_id: ORG_ID, actor_user_id: U2, actor: MOCK_USERS[1],
    action: "ARTIFACT_SUBMITTED", resource_type: "artifact", resource_id: "art-002",
    before_state: { status: "DRAFT" }, after_state: { status: "IN_REVIEW" },
    ip_address: "192.168.1.22", created_at: DAY_AGO,
  },
  {
    id: "log-003", organization_id: ORG_ID, actor_user_id: U1, actor: MOCK_USERS[0],
    action: "USER_LOGIN", resource_type: "user", resource_id: U1,
    before_state: null, after_state: null,
    ip_address: "192.168.1.10", created_at: NOW,
  },
  {
    id: "log-004", organization_id: ORG_ID, actor_user_id: U2, actor: MOCK_USERS[1],
    action: "STUDY_CREATED", resource_type: "study", resource_id: "study-003",
    before_state: null, after_state: { name: "BRIDGE-HF" },
    ip_address: "192.168.1.22", created_at: WEEK_AGO,
  },
  {
    id: "log-005", organization_id: ORG_ID, actor_user_id: U4, actor: MOCK_USERS[3],
    action: "ARTIFACT_CREATED", resource_type: "artifact", resource_id: "art-003",
    before_state: null, after_state: { name: "Statistical Analysis Plan v1.0" },
    ip_address: "192.168.1.55", created_at: WEEK_AGO,
  },
  {
    id: "log-006", organization_id: ORG_ID, actor_user_id: U3, actor: MOCK_USERS[2],
    action: "ARTIFACT_REJECTED", resource_type: "artifact", resource_id: "art-005",
    before_state: { status: "IN_REVIEW" }, after_state: { status: "REJECTED" },
    ip_address: "192.168.1.45", created_at: WEEK_AGO,
  },
  {
    id: "log-007", organization_id: ORG_ID, actor_user_id: U1, actor: MOCK_USERS[0],
    action: "STUDY_UPDATED", resource_type: "study", resource_id: "study-001",
    before_state: { status: "DRAFT" }, after_state: { status: "ACTIVE" },
    ip_address: "192.168.1.10", created_at: MONTH_AGO,
  },
  {
    id: "log-008", organization_id: ORG_ID, actor_user_id: U1, actor: MOCK_USERS[0],
    action: "ARTIFACT_LOCKED", resource_type: "artifact", resource_id: "art-004",
    before_state: { status: "APPROVED" }, after_state: { status: "LOCKED" },
    ip_address: "192.168.1.10", created_at: WEEK_AGO,
  },
];

export const MOCK_ARTIFACT_VERSIONS: ArtifactVersion[] = [
  {
    id: "ver-001", artifact_id: "art-001", version_number: 1, is_current: false,
    content: { title: "NVX-001 Study Protocol", version: "1.0", sections: ["Background", "Objectives"] },
    content_hash: "sha256:a1b2c3d4e5f6", file_path: null, file_size_bytes: null,
    file_mime_type: null, change_summary: "Initial draft",
    status_at_creation: "DRAFT", created_by_id: U2, created_at: MONTH_AGO,
  },
  {
    id: "ver-002", artifact_id: "art-001", version_number: 2, is_current: false,
    content: { title: "NVX-001 Study Protocol", version: "2.0", sections: ["Background", "Objectives", "Study Design"] },
    content_hash: "sha256:b2c3d4e5f6a7", file_path: null, file_size_bytes: null,
    file_mime_type: null, change_summary: "Updated inclusion/exclusion criteria per IRB feedback. Added biomarker substudy section.",
    status_at_creation: "IN_REVIEW", created_by_id: U2, created_at: WEEK_AGO,
  },
  {
    id: "ver-003", artifact_id: "art-001", version_number: 3, is_current: true,
    content: { title: "NVX-001 Study Protocol", version: "3.0", sections: ["Background", "Objectives", "Study Design", "Statistical Methods"] },
    content_hash: "sha256:c3d4e5f6a7b8", file_path: null, file_size_bytes: null,
    file_mime_type: null, change_summary: "Final approved version with dosing amendments and updated safety monitoring plan.",
    status_at_creation: "APPROVED", created_by_id: U2, created_at: DAY_AGO,
  },
];

export const MOCK_STUDY_MEMBERS: StudyMember[] = [
  { id: "mem-001", study_id: "study-001", user_id: U1, role: "ADMIN", user: MOCK_USERS[0], joined_at: MONTH_AGO, created_at: MONTH_AGO },
  { id: "mem-002", study_id: "study-001", user_id: U2, role: "CONTRIBUTOR", user: MOCK_USERS[1], joined_at: MONTH_AGO, created_at: MONTH_AGO },
  { id: "mem-003", study_id: "study-001", user_id: U3, role: "REVIEWER", user: MOCK_USERS[2], joined_at: MONTH_AGO, created_at: MONTH_AGO },
  { id: "mem-004", study_id: "study-001", user_id: U4, role: "CONTRIBUTOR", user: MOCK_USERS[3], joined_at: WEEK_AGO, created_at: WEEK_AGO },
];
