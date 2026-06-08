// ─── Core domain types ───────────────────────────────────────────────────────

export type Role = "ADMIN" | "CONTRIBUTOR" | "REVIEWER";

export type ArtifactStatus =
  | "DRAFT"
  | "IN_REVIEW"
  | "APPROVED"
  | "REJECTED"
  | "LOCKED"
  | "AMENDED"
  | "SUPERSEDED";

export type ArtifactType =
  | "PROTOCOL"
  | "ICF"
  | "SAP"
  | "EDC_CRF"
  | "TRACEABILITY_MATRIX"
  | "SDTM_DATASET"
  | "ADAM_DATASET"
  | "TLF"
  | "VALIDATION_REPORT"
  | "CSR"
  | "SUBMISSION_PACKAGE"
  | "OTHER";

export type StudyPhase =
  | "PHASE_1"
  | "PHASE_1_2"
  | "PHASE_2"
  | "PHASE_2_3"
  | "PHASE_3"
  | "PHASE_3_4"
  | "PHASE_4"
  | "OBSERVATIONAL"
  | "OTHER";

export type StudyStatus =
  | "DRAFT"
  | "ACTIVE"
  | "ON_HOLD"
  | "COMPLETED"
  | "ARCHIVED"
  | "TERMINATED";

export type ApprovalDecision = "APPROVED" | "REJECTED";

// ─── API response models ─────────────────────────────────────────────────────

export interface Organization {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  logo_url: string | null;
  settings: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface User {
  id: string;
  organization_id: string;
  email: string;
  full_name: string;
  title: string | null;
  is_active: boolean;
  is_system_admin: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface Study {
  id: string;
  organization_id: string;
  protocol_number: string;
  name: string;
  short_name: string | null;
  description: string | null;
  indication: string | null;
  therapeutic_area: string | null;
  phase: StudyPhase | null;
  status: StudyStatus;
  sponsor: string | null;
  regulatory_region: string[] | null;
  start_date: string | null;
  end_date: string | null;
  created_by_id: string;
  created_at: string;
  updated_at: string;
}

export interface StudyMember {
  id: string;
  study_id: string;
  user_id: string;
  role: Role;
  user: User;
  joined_at: string | null;
  created_at: string;
}

export interface Artifact {
  id: string;
  organization_id: string;
  study_id: string;
  artifact_type: ArtifactType;
  name: string;
  description: string | null;
  status: ArtifactStatus;
  current_version_id: string | null;
  current_version_number: number;
  locked_at: string | null;
  tags: string[] | null;
  created_by_id: string;
  created_at: string;
  updated_at: string;
}

export interface ArtifactVersionCreator {
  id: string;
  full_name: string;
  email: string;
}

export interface ArtifactVersion {
  id: string;
  artifact_id: string;
  version_number: number;
  is_current: boolean;
  content: Record<string, unknown>;
  content_hash: string;
  content_diff: Record<string, unknown> | null;
  file_path: string | null;
  file_size_bytes: number | null;
  file_mime_type: string | null;
  change_summary: string | null;
  status_at_creation: ArtifactStatus;
  created_by_id: string;
  creator: ArtifactVersionCreator | null;
  created_at: string;
}

export interface Approval {
  id: string;
  artifact_id: string;
  artifact_version_id: string;
  approver_id: string;
  approver: User;
  decision: ApprovalDecision;
  comments: string | null;
  created_at: string;
}

export interface ApprovalQueueItem {
  artifact_id: string;
  artifact_version_id: string | null;
  artifact_name: string;
  artifact_type: ArtifactType;
  study_id: string;
  study_name: string;
  protocol_number: string;
  version_number: number;
  submitted_by: { id: string; full_name: string; email: string };
  submitted_at: string;
}

export interface Comment {
  id: string;
  artifact_id: string;
  artifact_version_id: string | null;
  parent_id: string | null;
  author: User;
  body: string;
  is_resolved: boolean;
  resolved_at: string | null;
  replies: Comment[];
  created_at: string;
  updated_at: string;
}

export interface AuditLog {
  id: string;
  organization_id: string;
  actor_user_id: string | null;
  actor: User | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  before_state: Record<string, unknown> | null;
  after_state: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface ValidationRun {
  id: string;
  artifact_id: string;
  artifact_version_id: string;
  engine: string;
  status: "PENDING" | "RUNNING" | "PASSED" | "FAILED" | "ERROR";
  rule_set_version: string | null;
  total_checks: number | null;
  passed_checks: number | null;
  failed_checks: number | null;
  warnings: number | null;
  started_at: string | null;
  completed_at: string | null;
  triggered_by_id: string;
  created_at: string;
}

export interface GenerationJob {
  id: string;
  study_id: string;
  artifact_type: ArtifactType;
  status: "PENDING" | "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";
  model_id: string;
  output_artifact_id: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export type NotificationType =
  | "ARTIFACT_SUBMITTED"
  | "ARTIFACT_APPROVED"
  | "ARTIFACT_REJECTED"
  | "ARTIFACT_LOCKED"
  | "COMMENT_ADDED"
  | "MENTION"
  | "VALIDATION_COMPLETE";

export interface Notification {
  id: string;
  organization_id: string;
  recipient_id: string;
  type: NotificationType;
  title: string;
  body: string;
  resource_type: string | null;
  resource_id: string | null;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface NotificationListResponse {
  items: Notification[];
  total: number;
  unread_count: number;
  page: number;
  page_size: number;
  has_next: boolean;
  has_prev: boolean;
}

// ─── Pagination ──────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
  has_prev: boolean;
}

// ─── Auth ────────────────────────────────────────────────────────────────────

export interface AuthTokens {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface AuthSession {
  user: User;
  organization: Organization;
  role: Role;
}

// ─── Error ───────────────────────────────────────────────────────────────────

export interface ApiErrorDetailObject {
  code?: string;
  message?: string;
  issues?: string[];
  field?: string;
}

export type ApiErrorDetail = string | ApiErrorDetailObject;

export interface ApiError {
  detail: ApiErrorDetail;
  code?: string;
  field?: string;
}

// ─── Intelligence Platform types ─────────────────────────────────────────────

export type AIDecisionStatus = "PENDING_REVIEW" | "ACCEPTED" | "REJECTED" | "OVERRIDDEN";

export interface AIDecision {
  id: string;
  organization_id: string;
  study_id: string | null;
  agent_name: string;
  agent_version: string | null;
  decision_type: string;
  module: string | null;
  model_id: string | null;
  model_provider: string | null;
  prompt_hash: string | null;
  confidence: number | null;
  input_context: Record<string, unknown>;
  reasoning: string | null;
  output: Record<string, unknown>;
  status: AIDecisionStatus;
  reviewed_by_id: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
  created_at: string;
}

export interface HumanOverride {
  id: string;
  organization_id: string;
  study_id: string | null;
  ai_decision_id: string | null;
  context_type: string;
  context_id: string | null;
  field_path: string | null;
  original_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  reason: string;
  override_type: string;
  actor_user_id: string;
  created_at: string;
}

export type DataLineageType = "FIELD_LEVEL" | "ARTIFACT_LEVEL";

export interface DataLineage {
  id: string;
  organization_id: string;
  study_id: string | null;
  lineage_type: DataLineageType;
  source_type: string;
  source_id: string | null;
  source_field: string | null;
  source_domain: string | null;
  target_type: string;
  target_id: string | null;
  target_field: string | null;
  target_domain: string | null;
  transformation_logic: string | null;
  is_ai_generated: boolean;
  ai_decision_id: string | null;
  created_at: string;
}

export type ValidationEvidenceStatus = "PENDING" | "PASS" | "FAIL" | "WARNING" | "WAIVED";

export interface ValidationEvidence {
  id: string;
  organization_id: string;
  study_id: string | null;
  validation_run_id: string | null;
  rule_id: string | null;
  rule_name: string | null;
  rule_category: string | null;
  cdisc_standard: string | null;
  subject_type: string;
  subject_field: string | null;
  status: ValidationEvidenceStatus;
  finding_severity: string | null;
  finding_message: string | null;
  finding_details: Record<string, unknown>;
  is_ai_evaluated: boolean;
  ai_decision_id: string | null;
  waived_by_id: string | null;
  waiver_reason: string | null;
  waived_at: string | null;
  created_at: string;
}

export interface SyntheticDataRun {
  id: string;
  organization_id: string;
  study_id: string;
  run_name: string;
  description: string | null;
  target_n: number | null;
  configuration: Record<string, unknown>;
  random_seed: number | null;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";
  records_generated: number | null;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  ai_decision_id: string | null;
  output_artifact_id: string | null;
  created_at: string;
}

export interface GraphNode {
  id: string;
  organization_id: string;
  study_id: string | null;
  node_type: string;
  external_id: string | null;
  external_type: string | null;
  label: string;
  description: string | null;
  properties: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
}

export interface GraphEdge {
  id: string;
  organization_id: string;
  study_id: string | null;
  source_node_id: string;
  target_node_id: string;
  edge_type: string;
  label: string | null;
  properties: Record<string, unknown>;
  confidence: number | null;
  is_ai_generated: boolean;
  ai_decision_id: string | null;
  created_at: string;
}

export interface GraphEvent {
  id: string;
  organization_id: string;
  study_id: string | null;
  event_type: string;
  node_id: string | null;
  edge_id: string | null;
  actor_user_id: string | null;
  actor_agent_id: string | null;
  ai_decision_id: string | null;
  idempotency_key: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

// ─── Sponsor Intake types ─────────────────────────────────────────────────────

export type IntakeStatus = "IN_PROGRESS" | "READY_TO_COMPILE" | "COMPILED";

export type IntakeDomain =
  | "STUDY_OVERVIEW"
  | "STUDY_DESIGN"
  | "POPULATION"
  | "ENDPOINTS"
  | "DRUG_TREATMENT"
  | "SAFETY"
  | "REGULATORY"
  | "STATISTICAL"
  | "SITES";

export const INTAKE_DOMAINS: { key: IntakeDomain; label: string }[] = [
  { key: "STUDY_OVERVIEW", label: "Study Overview" },
  { key: "STUDY_DESIGN", label: "Study Design" },
  { key: "POPULATION", label: "Population" },
  { key: "ENDPOINTS", label: "Endpoints" },
  { key: "DRUG_TREATMENT", label: "Drug & Treatment" },
  { key: "SAFETY", label: "Safety" },
  { key: "REGULATORY", label: "Regulatory" },
  { key: "STATISTICAL", label: "Statistical" },
  { key: "SITES", label: "Sites" },
];

export interface IntakeMessage {
  id: string;
  intake_id: string;
  role: "user" | "assistant";
  content: string;
  domain: IntakeDomain | null;
  created_at: string;
}

export interface SponsorIntake {
  id: string;
  organization_id: string;
  study_id: string;
  created_by_id: string;
  status: IntakeStatus;
  domains_completed: IntakeDomain[];
  ready_to_compile: boolean;
  messages: IntakeMessage[];
  created_at: string;
  updated_at: string;
}

export interface StudyBrief {
  id: string;
  intake_id: string;
  organization_id: string;
  study_id: string;
  compiled_by_id: string;
  content: Record<string, unknown>;
  created_at: string;
}

// ─── File Uploads ─────────────────────────────────────────────────────────────

export interface UploadedFile {
  id: string;
  organization_id: string;
  study_id: string;
  uploaded_by_id: string;
  original_filename: string;
  stored_filename: string;
  file_size_bytes: number;
  mime_type: string;
  description: string | null;
  extracted_metadata: Record<string, unknown>;
  file_hash: string | null;
  upload_status: "UPLOADED" | "PARSED" | "FAILED" | "MAPPED";
  created_at: string;
}

export interface RawDataset {
  id: string;
  organization_id: string;
  study_id: string;
  uploaded_file_id: string;
  dataset_name: string;
  row_count: number;
  column_count: number;
  parse_status: "PENDING" | "PARSED" | "FAILED";
  parse_error: string | null;
  created_at: string;
  fields: RawField[];
}

export interface RawField {
  id: string;
  organization_id: string;
  study_id: string;
  raw_dataset_id: string;
  column_name: string;
  column_index: number;
  inferred_type: "string" | "date" | "number" | "boolean" | "unknown";
  sample_values: string[];
  missing_count: number;
  distinct_count: number;
  min_value: string | null;
  max_value: string | null;
  mapped_ecrf_field_id: string | null;
  mapped_sdtm_variable_id: string | null;
  mapping_status: "UNMAPPED" | "PENDING_APPROVAL" | "APPROVED" | "REJECTED";
  mapping_version: number;
  created_at: string;
  updated_at: string;
}

export interface FieldMappingVersion {
  id: string;
  raw_field_id: string;
  version_number: number;
  mapped_ecrf_field_id: string | null;
  mapped_sdtm_variable_id: string | null;
  mapping_status: string;
  changed_by_id: string;
  approved_by_id: string | null;
  notes: string | null;
  created_at: string;
}

export interface MappingValidationResult {
  total_fields: number;
  mapped_fields: number;
  approved_fields: number;
  pending_fields: number;
  unmapped_fields: number;
  coverage_pct: number;
  issues: string[];
}

export interface FieldMappingSuggestion {
  field_id: string;
  column_name: string;
  mapped_ecrf_field_id: string | null;
  mapped_sdtm_variable_id: string | null;
  confidence: number;
  reasoning: string;
}

export interface SuggestMappingsResponse {
  ai_decision_id: string;
  dataset_id: string;
  suggestions: FieldMappingSuggestion[];
  model_id: string;
}

export interface StudySDTMReadinessResponse {
  study_id: string;
  dataset_count: number;
  total_fields: number;
  approved_fields: number;
  ready: boolean;
  issues: string[];
  datasets: Array<{
    dataset_id: string;
    dataset_name: string;
    total_fields: number;
    approved_fields: number;
    ready: boolean;
  }>;
}

export interface StudyADAMReadinessResponse {
  study_id: string;
  sdtm_artifact_count: number;
  ready: boolean;
  issues: string[];
  sdtm_artifacts: Array<{
    artifact_id: string;
    artifact_name: string;
    domain_count: number;
    domains: string[];
    observation_count: number;
    ready: boolean;
  }>;
}

export interface ADAMGenerationResponse {
  artifact_id: string;
  artifact_version_id: string;
  ai_decision_id: string;
  validation_run_id: string;
  dataset_count: number;
  study_id: string;
  source_sdtm_artifact_ids: string[];
}

export interface StudyCSRReadinessResponse {
  study_id: string;
  tlf_artifact_count: number;
  protocol_artifact_count: number;
  sap_artifact_count: number;
  ready: boolean;
  issues: string[];
  tlf_artifacts: Array<{
    artifact_id: string;
    artifact_name: string;
    table_count: number;
    tables: string[];
    ready: boolean;
  }>;
}

export interface CSRGenerationResponse {
  artifact_id: string;
  artifact_version_id: string;
  ai_decision_id: string;
  validation_run_id: string;
  section_count: number;
  study_id: string;
  source_tlf_artifact_ids: string[];
  source_study_artifact_ids: string[];
}

export interface SDTMGenerationResponse {
  artifact_id: string;
  artifact_version_id: string;
  ai_decision_id: string;
  validation_run_id: string;
  domain_count: number;
  study_id: string;
  source_dataset_ids: string[];
}
