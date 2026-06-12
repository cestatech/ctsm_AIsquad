import { downloadAuthenticatedBlob } from "@/lib/download";
import { approvalsApi } from "./approvals";
import { artifactsApi } from "./artifacts";
import { intelligenceApi } from "./intelligence";
import { validationApi } from "./validation";
import type {
  ApprovalDecision,
  Artifact,
  ArtifactVersion,
  ValidationEvidence,
} from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export type SdtmVariableOrigin =
  | "Collected"
  | "Derived"
  | "Assigned"
  | "Protocol"
  | "Predecessor"
  | string;

export interface SDTMVariableSpec {
  variable?: string;
  name?: string;
  label?: string;
  type?: string;
  origin?: string;
  derivation?: string;
  description?: string;
  notes?: string;
  controlled_terminology?: string | null;
}

export interface SDTMDomain {
  domain: string;
  domain_label?: string;
  class?: string;
  variables: Array<string | SDTMVariableSpec>;
  observations?: Record<string, unknown>[];
}

export interface SDTMDerivedVariable {
  variable: string;
  logic?: string;
  derivation?: string;
}

export interface SDTMArtifactContent {
  document_type?: string;
  protocol_number?: string;
  study_name?: string;
  sdtm_ig_version?: string;
  validation_engine?: string;
  domains: SDTMDomain[];
  derived_variables?: SDTMDerivedVariable[];
}

export interface SDTMNormalizedVariable {
  name: string;
  label: string;
  dataType: string;
  origin: string;
  derivation: string;
}

export interface SDTMReviewBundle {
  artifact: Artifact;
  content: SDTMArtifactContent;
  validationEvidence: ValidationEvidence[];
}

export function sdtmReviewPath(studyId: string, artifactId: string): string {
  return `/studies/${studyId}/sdtm/${artifactId}`;
}

export function isSdtmArtifactContent(
  content: Record<string, unknown> | SDTMArtifactContent
): content is SDTMArtifactContent {
  return Array.isArray((content as SDTMArtifactContent).domains);
}

export function normalizeSdtmVariable(
  spec: string | SDTMVariableSpec,
  domainCode: string,
  derivationIndex: Record<string, string>
): SDTMNormalizedVariable {
  if (typeof spec === "string") {
    const derivation =
      derivationIndex[`${domainCode}.${spec}`] ?? derivationIndex[spec] ?? "";
    return {
      name: spec,
      label: spec,
      dataType: inferSdtmDataType(spec),
      origin: derivation ? "Derived" : inferDefaultOrigin(spec),
      derivation,
    };
  }

  const name = spec.variable ?? spec.name ?? "UNK";
  const derivation =
    spec.derivation ??
    derivationIndex[`${domainCode}.${name}`] ??
    derivationIndex[name] ??
    "";

  return {
    name,
    label: spec.label ?? name,
    dataType: spec.type ? mapSdtmType(spec.type) : inferSdtmDataType(name),
    origin: spec.origin ?? (derivation ? "Derived" : inferDefaultOrigin(name)),
    derivation,
  };
}

export function buildDerivationIndex(
  content: SDTMArtifactContent
): Record<string, string> {
  const index: Record<string, string> = {};
  for (const entry of content.derived_variables ?? []) {
    const logic = entry.logic ?? entry.derivation ?? "";
    if (!entry.variable || !logic) continue;
    index[entry.variable] = logic;
    if (entry.variable.includes(".")) {
      const [, short] = entry.variable.split(".", 2);
      index[short] = logic;
    }
  }
  return index;
}

export function defaultSdtmDomainCode(domains: SDTMDomain[]): string {
  if (domains.length === 0) return "";
  const dm = domains.find((d) => d.domain.toUpperCase() === "DM");
  return dm?.domain ?? domains[0].domain;
}

export function isOpenValidationFinding(evidence: ValidationEvidence): boolean {
  return (
    evidence.status === "FAIL" ||
    evidence.status === "WARNING" ||
    evidence.status === "PENDING"
  );
}

function inferDefaultOrigin(name: string): string {
  if (name === "STUDYID" || name === "DOMAIN" || name === "USUBJID") {
    return "Assigned";
  }
  return "Collected";
}

function inferSdtmDataType(name: string): string {
  if (name.endsWith("DTC") || name.endsWith("DT")) return "date";
  if (["AGE", "STUDYID", "USUBJID"].includes(name)) {
    return name === "AGE" ? "float" : "text";
  }
  return "text";
}

function mapSdtmType(type: string): string {
  const normalized = type.toLowerCase();
  if (normalized === "char") return "text";
  if (normalized === "num" || normalized === "number") return "float";
  return type;
}

export const sdtmApi = {
  getArtifact: (artifactId: string, token: string) =>
    artifactsApi.get(artifactId, token),

  getArtifactContent: async (
    artifactId: string,
    token: string
  ): Promise<SDTMArtifactContent> => {
    const versions = await artifactsApi.getVersions(artifactId, token);
    const current =
      versions.find((version: ArtifactVersion) => version.is_current) ??
      versions[versions.length - 1];
    const raw = current?.content ?? {};
    if (!isSdtmArtifactContent(raw)) {
      return { domains: [] };
    }
    return raw;
  },

  getValidationEvidenceForArtifact: async (
    studyId: string,
    artifactId: string,
    token: string
  ): Promise<ValidationEvidence[]> => {
    const runsResponse = await validationApi.listRuns(
      { artifact_id: artifactId, page_size: 100 },
      token
    );
    const runIds = new Set(runsResponse.items.map((run) => run.id));
    if (runIds.size === 0) {
      return [];
    }

    const evidenceResponse = await intelligenceApi.listValidationEvidence(
      { study_id: studyId, page_size: 500 },
      token
    );

    return evidenceResponse.items.filter(
      (item) =>
        item.validation_run_id !== null && runIds.has(item.validation_run_id)
    );
  },

  submitForReview: (artifactId: string, token: string) =>
    artifactsApi.submit(artifactId, token),

  recordApprovalDecision: (
    artifactId: string,
    artifactVersionId: string,
    decision: ApprovalDecision,
    token: string,
    comments?: string
  ) =>
    approvalsApi.create(
      {
        artifact_id: artifactId,
        artifact_version_id: artifactVersionId,
        decision,
        comments,
      },
      token
    ),

  downloadDefineXml: (artifactId: string, token: string) =>
    downloadAuthenticatedBlob(
      `${API_URL}/artifacts/${artifactId}/define-xml`,
      token,
      "define.xml"
    ),

  loadReviewBundle: async (
    studyId: string,
    artifactId: string,
    token: string
  ): Promise<SDTMReviewBundle> => {
    const [artifact, content, validationEvidence] = await Promise.all([
      sdtmApi.getArtifact(artifactId, token),
      sdtmApi.getArtifactContent(artifactId, token),
      sdtmApi.getValidationEvidenceForArtifact(studyId, artifactId, token),
    ]);
    return { artifact, content, validationEvidence };
  },
};
