export const GENERATION_STATUS_COLORS: Record<string, string> = {
  PENDING: "bg-slate-100 text-slate-600",
  QUEUED: "bg-amber-100 text-amber-600",
  RUNNING: "bg-blue-100 text-blue-700",
  COMPLETED: "bg-emerald-100 text-emerald-700",
  FAILED: "bg-red-100 text-red-700",
  CANCELLED: "bg-slate-100 text-slate-500",
};

export const GENERATION_ARTIFACT_TYPE_LABELS: Record<string, string> = {
  PROTOCOL: "Protocol",
  ICF: "ICF",
  SAP: "SAP",
  EDC_CRF: "eCRF",
  TRACEABILITY_MATRIX: "Traceability Matrix",
  SDTM_DATASET: "SDTM Dataset",
  ADAM_DATASET: "ADaM Dataset",
  TLF: "TLF",
  VALIDATION_REPORT: "Validation Report",
  CSR: "CSR",
  SUBMISSION_PACKAGE: "Submission Package",
  OTHER: "Other",
};

export const ACTIVE_GENERATION_STATUSES = new Set([
  "PENDING",
  "QUEUED",
  "RUNNING",
]);
