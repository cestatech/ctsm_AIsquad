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
  is_active: boolean;
  created_at: string;
}

export interface User {
  id: string;
  organization_id: string;
  email: string;
  full_name: string;
  title: string | null;
  is_active: boolean;
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

export interface ArtifactVersion {
  id: string;
  artifact_id: string;
  version_number: number;
  is_current: boolean;
  content: Record<string, unknown>;
  content_hash: string;
  file_path: string | null;
  file_size_bytes: number | null;
  file_mime_type: string | null;
  change_summary: string | null;
  status_at_creation: ArtifactStatus;
  created_by_id: string;
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

export interface ApiError {
  detail: string;
  code: string;
  field?: string;
}
