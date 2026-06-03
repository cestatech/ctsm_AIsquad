import type {
  AIDecision,
  Artifact,
  ArtifactVersion,
  AuditLog,
  DataLineage,
  GraphEdge,
  GraphNode,
  HumanOverride,
  Study,
  StudyMember,
  SyntheticDataRun,
  User,
  ValidationEvidence,
} from "@/types";

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

// ─── Intelligence Platform mock data ─────────────────────────────────────────

const D1 = "00000000-0000-0000-0001-000000000001";
const D2 = "00000000-0000-0000-0001-000000000002";
const D3 = "00000000-0000-0000-0001-000000000003";
const D4 = "00000000-0000-0000-0001-000000000004";
const D5 = "00000000-0000-0000-0001-000000000005";

export const MOCK_AI_DECISIONS: AIDecision[] = [
  {
    id: D1,
    organization_id: ORG_ID,
    study_id: "study-001",
    agent_name: "sdtm-mapping-agent",
    agent_version: "1.2.0",
    decision_type: "FIELD_MAPPING",
    module: "SDTM",
    model_id: "claude-opus-4-7",
    model_provider: "anthropic",
    prompt_hash: "sha256:a1b2c3d4",
    confidence: 0.94,
    input_context: { ecr_field: "VSTESTCD", domain: "VS", visit: "SCREENING" },
    reasoning: "The eCRF field VSTESTCD maps directly to the SDTM VS domain variable VSTESTCD based on CDISC IG v3.3 mapping rules. Confidence is high due to exact name match and domain alignment.",
    output: { sdtm_variable: "VSTESTCD", sdtm_domain: "VS", mapping_type: "direct" },
    status: "PENDING_REVIEW",
    reviewed_by_id: null,
    reviewed_at: null,
    review_notes: null,
    created_at: DAY_AGO,
  },
  {
    id: D2,
    organization_id: ORG_ID,
    study_id: "study-001",
    agent_name: "sdtm-mapping-agent",
    agent_version: "1.2.0",
    decision_type: "FIELD_MAPPING",
    module: "SDTM",
    model_id: "claude-opus-4-7",
    model_provider: "anthropic",
    prompt_hash: "sha256:b2c3d4e5",
    confidence: 0.78,
    input_context: { ecr_field: "AETERM", domain: "AE", verbatim: "headache" },
    reasoning: "Verbatim term 'headache' maps to MedDRA PT 'Headache' (10019211) with high confidence. AETERM populated with verbatim; AEDECOD with preferred term. Confidence reduced from 1.0 due to potential for more specific coding.",
    output: { sdtm_variable: "AETERM", aedecod: "Headache", meddra_pt_code: "10019211" },
    status: "PENDING_REVIEW",
    reviewed_by_id: null,
    reviewed_at: null,
    review_notes: null,
    created_at: DAY_AGO,
  },
  {
    id: D3,
    organization_id: ORG_ID,
    study_id: "study-001",
    agent_name: "adam-derivation-agent",
    agent_version: "1.0.1",
    decision_type: "VARIABLE_DERIVATION",
    module: "ADaM",
    model_id: "claude-opus-4-7",
    model_provider: "anthropic",
    prompt_hash: "sha256:c3d4e5f6",
    confidence: 0.91,
    input_context: { sdtm_variable: "VSRESN", adam_dataset: "ADVS", derivation_type: "change_from_baseline" },
    reasoning: "CHG = AVAL - BASE per ADaM IG derivation standard. BASE is the last non-missing AVAL with ABLFL='Y'. Applied standard change-from-baseline algorithm with no exceptions detected.",
    output: { adam_variable: "CHG", derivation_formula: "CHG = AVAL - BASE", ablfl_rule: "last_non_missing_before_first_dose" },
    status: "ACCEPTED",
    reviewed_by_id: U3,
    reviewed_at: WEEK_AGO,
    review_notes: "Derivation logic confirmed against SAP section 5.3.",
    created_at: WEEK_AGO,
  },
  {
    id: D4,
    organization_id: ORG_ID,
    study_id: "study-001",
    agent_name: "protocol-agent",
    agent_version: "0.9.0",
    decision_type: "ENDPOINT_EXTRACTION",
    module: "PROTOCOL",
    model_id: "claude-opus-4-7",
    model_provider: "anthropic",
    prompt_hash: "sha256:d4e5f6a7",
    confidence: 0.62,
    input_context: { protocol_section: "5.1", text: "The primary efficacy endpoint is overall survival (OS) defined as the time from randomization to death from any cause." },
    reasoning: "Primary endpoint identified as Overall Survival (OS). Time-to-event endpoint. Randomization as origin event. Death from any cause as event of interest. Confidence reduced due to ambiguity in censoring rules not explicitly stated in this section.",
    output: { endpoint_type: "PRIMARY", measure: "Overall Survival", definition: "Time from randomization to death from any cause", censoring_rule: "unspecified" },
    status: "REJECTED",
    reviewed_by_id: U3,
    reviewed_at: DAY_AGO,
    review_notes: "Censoring rule must be extracted from Section 8.2 (Statistical Methods). Rerun with full context window including both sections.",
    created_at: DAY_AGO,
  },
  {
    id: D5,
    organization_id: ORG_ID,
    study_id: "study-002",
    agent_name: "validation-agent",
    agent_version: "1.1.0",
    decision_type: "CDISC_VALIDATION",
    module: "VALIDATION",
    model_id: "claude-opus-4-7",
    model_provider: "anthropic",
    prompt_hash: "sha256:e5f6a7b8",
    confidence: 0.99,
    input_context: { dataset: "DM", variable: "RFSTDTC", standard: "SDTM-IG-3.3" },
    reasoning: "RFSTDTC is present in DM dataset with ISO 8601 format. Format conforms to CDISC requirement. No missing values for enrolled subjects. Rule SD0083 PASS.",
    output: { rule_id: "SD0083", status: "PASS", findings: [] },
    status: "ACCEPTED",
    reviewed_by_id: U1,
    reviewed_at: WEEK_AGO,
    review_notes: null,
    created_at: WEEK_AGO,
  },
];

const OV1 = "00000000-0000-0000-0002-000000000001";
const OV2 = "00000000-0000-0000-0002-000000000002";
const OV3 = "00000000-0000-0000-0002-000000000003";

export const MOCK_HUMAN_OVERRIDES: HumanOverride[] = [
  {
    id: OV1,
    organization_id: ORG_ID,
    study_id: "study-001",
    ai_decision_id: D4,
    context_type: "ai_decision",
    context_id: D4,
    field_path: "output.censoring_rule",
    original_value: { censoring_rule: "unspecified" },
    new_value: { censoring_rule: "last_known_alive_date" },
    reason: "Censoring rule explicitly defined in protocol Section 8.2.1 as last known alive date. AI did not have access to full protocol context.",
    override_type: "CORRECTION",
    actor_user_id: U3,
    created_at: DAY_AGO,
  },
  {
    id: OV2,
    organization_id: ORG_ID,
    study_id: "study-001",
    ai_decision_id: D2,
    context_type: "ai_decision",
    context_id: D2,
    field_path: "output.aedecod",
    original_value: { aedecod: "Headache" },
    new_value: { aedecod: "Tension headache" },
    reason: "Clinical reviewer determined more specific MedDRA preferred term 'Tension headache' (10043268) is appropriate based on the clinical narrative describing pressure-type bilateral headache.",
    override_type: "REFINEMENT",
    actor_user_id: U3,
    created_at: DAY_AGO,
  },
  {
    id: OV3,
    organization_id: ORG_ID,
    study_id: "study-001",
    ai_decision_id: null,
    context_type: "sdtm_mapping",
    context_id: null,
    field_path: "LBORRES",
    original_value: { value: "2.4", unit: "mmol/L" },
    new_value: { value: "2.4", unit: "mg/dL", conversion_factor: 18.02 },
    reason: "Source data units are mg/dL not mmol/L as assumed. Correcting unit assignment and flagging for recalculation of derived variables LBSTRESN and LBSTRESU.",
    override_type: "UNIT_CORRECTION",
    actor_user_id: U2,
    created_at: WEEK_AGO,
  },
];

const VE1 = "00000000-0000-0000-0003-000000000001";
const VE2 = "00000000-0000-0000-0003-000000000002";
const VE3 = "00000000-0000-0000-0003-000000000003";
const VE4 = "00000000-0000-0000-0003-000000000004";
const VE5 = "00000000-0000-0000-0003-000000000005";
const VE6 = "00000000-0000-0000-0003-000000000006";
const VE7 = "00000000-0000-0000-0003-000000000007";

export const MOCK_VALIDATION_EVIDENCE: ValidationEvidence[] = [
  {
    id: VE1, organization_id: ORG_ID, study_id: "study-001",
    validation_run_id: null, rule_id: "SD0083", rule_name: "RFSTDTC populated for enrolled subjects",
    rule_category: "DATE_FORMAT", cdisc_standard: "SDTM-IG-3.3",
    subject_type: "dataset", subject_field: "DM.RFSTDTC",
    status: "PASS", finding_severity: null, finding_message: null,
    finding_details: { subjects_checked: 142, passing: 142, failing: 0 },
    is_ai_evaluated: true, ai_decision_id: D5, waived_by_id: null, waiver_reason: null, waived_at: null,
    created_at: WEEK_AGO,
  },
  {
    id: VE2, organization_id: ORG_ID, study_id: "study-001",
    validation_run_id: null, rule_id: "SD0052", rule_name: "USUBJID format conformance",
    rule_category: "IDENTIFIER", cdisc_standard: "SDTM-IG-3.3",
    subject_type: "dataset", subject_field: "DM.USUBJID",
    status: "PASS", finding_severity: null, finding_message: null,
    finding_details: { subjects_checked: 142, passing: 142, format_pattern: "STUDYID-SITEID-SUBJID" },
    is_ai_evaluated: true, ai_decision_id: null, waived_by_id: null, waiver_reason: null, waived_at: null,
    created_at: WEEK_AGO,
  },
  {
    id: VE3, organization_id: ORG_ID, study_id: "study-001",
    validation_run_id: null, rule_id: "SD0097", rule_name: "EPOCH not in controlled terminology",
    rule_category: "CONTROLLED_TERMINOLOGY", cdisc_standard: "SDTM-IG-3.3",
    subject_type: "dataset", subject_field: "SE.EPOCH",
    status: "FAIL", finding_severity: "ERROR",
    finding_message: "3 records in SE.EPOCH contain value 'OPEN-LABEL EXTENSION' which is not in CDISC CT EPOCH codelist (C99079).",
    finding_details: { failing_records: 3, non_ct_values: ["OPEN-LABEL EXTENSION"], suggested_ct: "OPEN LABEL EXTENSION PERIOD" },
    is_ai_evaluated: true, ai_decision_id: null, waived_by_id: null, waiver_reason: null, waived_at: null,
    created_at: WEEK_AGO,
  },
  {
    id: VE4, organization_id: ORG_ID, study_id: "study-001",
    validation_run_id: null, rule_id: "AD0010", rule_name: "PARAMCD length exceeds 8 characters",
    rule_category: "VARIABLE_LENGTH", cdisc_standard: "ADaM-IG-1.1",
    subject_type: "dataset", subject_field: "ADAE.PARAMCD",
    status: "WARNING", finding_severity: "WARNING",
    finding_message: "PARAMCD value 'TRTEMFLG' (8 chars) is at maximum allowed length. Recommend review for FDA submission.",
    finding_details: { affected_paramcds: ["TRTEMFLG"], max_length: 8, current_length: 8 },
    is_ai_evaluated: true, ai_decision_id: null, waived_by_id: null, waiver_reason: null, waived_at: null,
    created_at: DAY_AGO,
  },
  {
    id: VE5, organization_id: ORG_ID, study_id: "study-001",
    validation_run_id: null, rule_id: "SD0120", rule_name: "Missing --SEQ variable",
    rule_category: "REQUIRED_VARIABLE", cdisc_standard: "SDTM-IG-3.3",
    subject_type: "dataset", subject_field: "LB.LBSEQ",
    status: "FAIL", finding_severity: "ERROR",
    finding_message: "Sequence variable LBSEQ is missing from LB dataset. Required per SDTM IG Section 4.1.2.",
    finding_details: { dataset: "LB", missing_variable: "LBSEQ", records_affected: 856 },
    is_ai_evaluated: false, ai_decision_id: null, waived_by_id: null, waiver_reason: null, waived_at: null,
    created_at: DAY_AGO,
  },
  {
    id: VE6, organization_id: ORG_ID, study_id: "study-001",
    validation_run_id: null, rule_id: "SD0003", rule_name: "Non-standard variable in dataset",
    rule_category: "NON_STANDARD_VARIABLE", cdisc_standard: "SDTM-IG-3.3",
    subject_type: "dataset", subject_field: "VS.VSSPID",
    status: "WAIVED", finding_severity: "WARNING",
    finding_message: "Non-standard sponsor variable VSSPID found in VS dataset.",
    finding_details: { variable: "VSSPID", dataset: "VS", reason: "sponsor_defined" },
    is_ai_evaluated: false, ai_decision_id: null,
    waived_by_id: U1,
    waiver_reason: "VSSPID is a pre-specified sponsor-defined variable documented in the define.xml. Required for linking to eDiary source data per data management plan.",
    waived_at: DAY_AGO,
    created_at: WEEK_AGO,
  },
  {
    id: VE7, organization_id: ORG_ID, study_id: "study-001",
    validation_run_id: null, rule_id: "AD0062", rule_name: "DTYPE values not in controlled terminology",
    rule_category: "CONTROLLED_TERMINOLOGY", cdisc_standard: "ADaM-IG-1.1",
    subject_type: "dataset", subject_field: "ADLB.DTYPE",
    status: "PASS", finding_severity: null, finding_message: null,
    finding_details: { records_checked: 2340, all_ct_conformant: true },
    is_ai_evaluated: true, ai_decision_id: null, waived_by_id: null, waiver_reason: null, waived_at: null,
    created_at: DAY_AGO,
  },
];

const N1 = "00000000-0000-0000-0004-000000000001";
const N2 = "00000000-0000-0000-0004-000000000002";
const N3 = "00000000-0000-0000-0004-000000000003";
const N4 = "00000000-0000-0000-0004-000000000004";
const N5 = "00000000-0000-0000-0004-000000000005";
const N6 = "00000000-0000-0000-0004-000000000006";
const N7 = "00000000-0000-0000-0004-000000000007";

export const MOCK_GRAPH_NODES: GraphNode[] = [
  {
    id: N1, organization_id: ORG_ID, study_id: "study-001",
    node_type: "STUDY_OBJECTIVE", external_id: null, external_type: null,
    label: "Primary Objective: Demonstrate OS benefit of NVX-001",
    description: "Demonstrate that NVX-001 improves overall survival vs. standard of care in advanced NSCLC",
    properties: { objective_type: "PRIMARY", endpoint_type: "EFFICACY" },
    is_active: true, created_at: MONTH_AGO,
  },
  {
    id: N2, organization_id: ORG_ID, study_id: "study-001",
    node_type: "STUDY_ENDPOINT", external_id: null, external_type: null,
    label: "Overall Survival (OS)",
    description: "Time from randomization to death from any cause",
    properties: { endpoint_class: "PRIMARY", measure_type: "TIME_TO_EVENT" },
    is_active: true, created_at: MONTH_AGO,
  },
  {
    id: N3, organization_id: ORG_ID, study_id: "study-001",
    node_type: "ECR_FIELD", external_id: null, external_type: null,
    label: "DTHFL — Death Flag (eCRF)",
    description: "Indicates whether subject died during study follow-up",
    properties: { ecr_form: "SURVIVAL_STATUS", field_type: "FLAG", codelist: "NY" },
    is_active: true, created_at: MONTH_AGO,
  },
  {
    id: N4, organization_id: ORG_ID, study_id: "study-001",
    node_type: "SDTM_VARIABLE", external_id: null, external_type: null,
    label: "DS.DSSTDTC — Disposition Date",
    description: "Date of subject disposition event (death, withdrawal, completion)",
    properties: { domain: "DS", variable: "DSSTDTC", type: "Char", format: "ISO8601" },
    is_active: true, created_at: MONTH_AGO,
  },
  {
    id: N5, organization_id: ORG_ID, study_id: "study-001",
    node_type: "ADAM_VARIABLE", external_id: null, external_type: null,
    label: "ADTTE.AVAL — Analysis Value (OS)",
    description: "Time-to-event analysis value in days for Overall Survival",
    properties: { dataset: "ADTTE", variable: "AVAL", paramcd: "OS", unit: "days" },
    is_active: true, created_at: MONTH_AGO,
  },
  {
    id: N6, organization_id: ORG_ID, study_id: "study-001",
    node_type: "TLF_OUTPUT", external_id: "art-003", external_type: "artifact",
    label: "Figure 14.1 — KM Plot: Overall Survival",
    description: "Kaplan-Meier survival curve comparing NVX-001 vs. placebo",
    properties: { tlf_type: "FIGURE", number: "14.1", dataset_source: "ADTTE" },
    is_active: true, created_at: WEEK_AGO,
  },
  {
    id: N7, organization_id: ORG_ID, study_id: "study-001",
    node_type: "CSR_SECTION", external_id: null, external_type: null,
    label: "CSR Section 11.4 — Overall Survival Results",
    description: "Clinical Study Report section presenting primary OS analysis results",
    properties: { section_number: "11.4", section_title: "Overall Survival" },
    is_active: true, created_at: WEEK_AGO,
  },
];

export const MOCK_GRAPH_EDGES: GraphEdge[] = [
  {
    id: "00000000-0000-0000-0005-000000000001",
    organization_id: ORG_ID, study_id: "study-001",
    source_node_id: N1, target_node_id: N2,
    edge_type: "OBJECTIVE_TO_ENDPOINT", label: "measured_by",
    properties: {}, confidence: null, is_ai_generated: false, ai_decision_id: null,
    created_at: MONTH_AGO,
  },
  {
    id: "00000000-0000-0000-0005-000000000002",
    organization_id: ORG_ID, study_id: "study-001",
    source_node_id: N2, target_node_id: N3,
    edge_type: "ENDPOINT_TO_ECR", label: "captured_in",
    properties: {}, confidence: null, is_ai_generated: false, ai_decision_id: null,
    created_at: MONTH_AGO,
  },
  {
    id: "00000000-0000-0000-0005-000000000003",
    organization_id: ORG_ID, study_id: "study-001",
    source_node_id: N3, target_node_id: N4,
    edge_type: "ECR_TO_SDTM", label: "maps_to",
    properties: { mapping_type: "direct" }, confidence: 0.94, is_ai_generated: true, ai_decision_id: D1,
    created_at: DAY_AGO,
  },
  {
    id: "00000000-0000-0000-0005-000000000004",
    organization_id: ORG_ID, study_id: "study-001",
    source_node_id: N4, target_node_id: N5,
    edge_type: "SDTM_TO_ADAM", label: "derives",
    properties: { derivation: "AVAL = days(DSSTDTC - RANDDT)" }, confidence: 0.91, is_ai_generated: true, ai_decision_id: D3,
    created_at: DAY_AGO,
  },
  {
    id: "00000000-0000-0000-0005-000000000005",
    organization_id: ORG_ID, study_id: "study-001",
    source_node_id: N5, target_node_id: N6,
    edge_type: "ADAM_TO_TLF", label: "produces",
    properties: { analysis_type: "KM_CURVE" }, confidence: null, is_ai_generated: false, ai_decision_id: null,
    created_at: WEEK_AGO,
  },
  {
    id: "00000000-0000-0000-0005-000000000006",
    organization_id: ORG_ID, study_id: "study-001",
    source_node_id: N6, target_node_id: N7,
    edge_type: "TLF_TO_CSR", label: "included_in",
    properties: {}, confidence: null, is_ai_generated: false, ai_decision_id: null,
    created_at: WEEK_AGO,
  },
];

export const MOCK_DATA_LINEAGE: DataLineage[] = [
  {
    id: "00000000-0000-0000-0006-000000000001",
    organization_id: ORG_ID, study_id: "study-001",
    lineage_type: "FIELD_LEVEL",
    source_type: "ecr_field", source_id: null, source_field: "DTHFL", source_domain: "SURVIVAL_STATUS",
    target_type: "sdtm_variable", target_id: null, target_field: "DTHFL", target_domain: "DM",
    transformation_logic: "Direct copy. DM.DTHFL = eCRF SURVIVAL_STATUS.DTHFL where value in ('Y','N')",
    is_ai_generated: true, ai_decision_id: D1, created_at: DAY_AGO,
  },
  {
    id: "00000000-0000-0000-0006-000000000002",
    organization_id: ORG_ID, study_id: "study-001",
    lineage_type: "FIELD_LEVEL",
    source_type: "sdtm_variable", source_id: null, source_field: "DSSTDTC", source_domain: "DS",
    target_type: "adam_variable", target_id: null, target_field: "AVAL", target_domain: "ADTTE",
    transformation_logic: "AVAL = INTCK('DAY', input(RANDDT, yymmdd10.), input(DSSTDTC, yymmdd10.)) + 1 where PARAMCD='OS'",
    is_ai_generated: true, ai_decision_id: D3, created_at: DAY_AGO,
  },
  {
    id: "00000000-0000-0000-0006-000000000003",
    organization_id: ORG_ID, study_id: "study-001",
    lineage_type: "ARTIFACT_LEVEL",
    source_type: "artifact", source_id: "art-001", source_field: null, source_domain: null,
    target_type: "artifact", target_id: "art-003", target_field: null, target_domain: null,
    transformation_logic: "SAP primary endpoint definition derived from protocol Section 5.1 objectives",
    is_ai_generated: false, ai_decision_id: null, created_at: MONTH_AGO,
  },
];

export const MOCK_SYNTHETIC_RUNS: SyntheticDataRun[] = [
  {
    id: "00000000-0000-0000-0007-000000000001",
    organization_id: ORG_ID, study_id: "study-001",
    run_name: "NOVA-1 Phase 2 Safety Population — Baseline",
    description: "Synthetic patient cohort for DM and VS domains, N=150, matching phase 2 NSCLC demographics",
    target_n: 150,
    configuration: {
      domains: ["DM", "VS", "LB"],
      age_distribution: { mean: 62.4, sd: 9.8, min: 18, max: 84 },
      sex_ratio: { M: 0.58, F: 0.42 },
      reference_study: "CHECKMATE-057",
    },
    random_seed: 42601,
    status: "COMPLETED",
    records_generated: 8934,
    started_at: WEEK_AGO,
    completed_at: WEEK_AGO,
    error_message: null,
    ai_decision_id: null,
    output_artifact_id: null,
    created_at: WEEK_AGO,
  },
  {
    id: "00000000-0000-0000-0007-000000000002",
    organization_id: ORG_ID, study_id: "study-001",
    run_name: "NOVA-1 Adverse Event Simulation — Cycle 1",
    description: "Synthetic AE data for cycle 1 safety review, based on NVX-001 Phase 1 observed rates",
    target_n: 150,
    configuration: {
      domains: ["AE"],
      ae_incidence_reference: "NVX-001-Phase1-FinalReport",
      grade_3_plus_rate: 0.18,
      discontinuation_rate: 0.06,
    },
    random_seed: 99312,
    status: "COMPLETED",
    records_generated: 423,
    started_at: DAY_AGO,
    completed_at: DAY_AGO,
    error_message: null,
    ai_decision_id: null,
    output_artifact_id: null,
    created_at: DAY_AGO,
  },
  {
    id: "00000000-0000-0000-0007-000000000003",
    organization_id: ORG_ID, study_id: "study-002",
    run_name: "AURORA Interim Analysis Dataset",
    description: "Simulated interim dataset for IDMC review preparation",
    target_n: 800,
    configuration: { domains: ["DM", "AE", "EX", "DS"], interim_fraction: 0.5 },
    random_seed: 20240601,
    status: "RUNNING",
    records_generated: null,
    started_at: NOW,
    completed_at: null,
    error_message: null,
    ai_decision_id: null,
    output_artifact_id: null,
    created_at: NOW,
  },
];
