import { apiClient } from "./client";
import { artifactsApi } from "./artifacts";
import type { Artifact, ArtifactVersion } from "@/types";
import type { CSRGenerationResponse, StudyCSRReadinessResponse } from "@/types";

export interface CSRSectionTLFReference {
  table_id?: string;
  title?: string;
  population?: string;
  key_result?: string;
}

export interface CSRTLFIntegrationEntry {
  table_id?: string;
  csr_section?: string;
  insertion_note?: string;
}

export interface CSRSection {
  number: string;
  title: string;
  ich_e3_reference?: string;
  content_outline?: string;
  status?: string;
  word_count_estimate?: number;
  prose?: string;
  narrative_summary?: string;
  tlf_references?: CSRSectionTLFReference[];
  ai_decision_id?: string;
}

export interface CSRArtifactContent {
  document_type?: string;
  title?: string;
  version?: string;
  ich_e3_compliant?: boolean;
  shell_only?: boolean;
  prose_generated?: boolean;
  sections?: CSRSection[];
  tlf_integration?: CSRTLFIntegrationEntry[];
  source_tlf_artifact_ids?: string[];
  synopsis?: Record<string, unknown>;
  appendices?: string[];
}

export interface CSRSectionRegenerateRequest {
  instructions?: string;
}

export interface CSRSectionProseResponse {
  section_id: string;
  prose: string;
  ai_decision_id: string;
}

export interface CSREditorBundle {
  artifact: Artifact;
  content: CSRArtifactContent;
  rawContent: Record<string, unknown>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseSection(value: unknown): CSRSection | null {
  if (!isRecord(value)) return null;
  const number = value.number;
  const title = value.title;
  if (typeof number !== "string" && typeof number !== "number") return null;
  if (typeof title !== "string") return null;

  const tlfRefs = Array.isArray(value.tlf_references)
    ? value.tlf_references
        .filter(isRecord)
        .map((ref) => ({
          table_id: typeof ref.table_id === "string" ? ref.table_id : undefined,
          title: typeof ref.title === "string" ? ref.title : undefined,
          population:
            typeof ref.population === "string" ? ref.population : undefined,
          key_result:
            typeof ref.key_result === "string" ? ref.key_result : undefined,
        }))
    : undefined;

  return {
    number: String(number),
    title,
    ich_e3_reference:
      typeof value.ich_e3_reference === "string"
        ? value.ich_e3_reference
        : undefined,
    content_outline:
      typeof value.content_outline === "string"
        ? value.content_outline
        : undefined,
    status: typeof value.status === "string" ? value.status : undefined,
    word_count_estimate:
      typeof value.word_count_estimate === "number"
        ? value.word_count_estimate
        : undefined,
    prose: typeof value.prose === "string" ? value.prose : undefined,
    narrative_summary:
      typeof value.narrative_summary === "string"
        ? value.narrative_summary
        : undefined,
    tlf_references: tlfRefs,
    ai_decision_id:
      typeof value.ai_decision_id === "string"
        ? value.ai_decision_id
        : undefined,
  };
}

export function parseCSRArtifactContent(raw: Record<string, unknown>): CSRArtifactContent {
  const sections = Array.isArray(raw.sections)
    ? raw.sections
        .map(parseSection)
        .filter((section): section is CSRSection => section !== null)
    : [];

  const tlfIntegration = Array.isArray(raw.tlf_integration)
    ? raw.tlf_integration
        .filter(isRecord)
        .map((entry) => ({
          table_id:
            typeof entry.table_id === "string" ? entry.table_id : undefined,
          csr_section:
            typeof entry.csr_section === "string"
              ? entry.csr_section
              : undefined,
          insertion_note:
            typeof entry.insertion_note === "string"
              ? entry.insertion_note
              : undefined,
        }))
    : undefined;

  const sourceTlfIds = Array.isArray(raw.source_tlf_artifact_ids)
    ? raw.source_tlf_artifact_ids.filter(
        (id): id is string => typeof id === "string"
      )
    : undefined;

  return {
    document_type:
      typeof raw.document_type === "string" ? raw.document_type : undefined,
    title: typeof raw.title === "string" ? raw.title : undefined,
    version: typeof raw.version === "string" ? raw.version : undefined,
    ich_e3_compliant:
      typeof raw.ich_e3_compliant === "boolean"
        ? raw.ich_e3_compliant
        : undefined,
    shell_only:
      typeof raw.shell_only === "boolean" ? raw.shell_only : undefined,
    prose_generated:
      typeof raw.prose_generated === "boolean"
        ? raw.prose_generated
        : undefined,
    sections,
    tlf_integration: tlfIntegration,
    source_tlf_artifact_ids: sourceTlfIds,
    synopsis: isRecord(raw.synopsis) ? raw.synopsis : undefined,
    appendices: Array.isArray(raw.appendices)
      ? raw.appendices.filter((item): item is string => typeof item === "string")
      : undefined,
  };
}

export function isSectionProseComplete(section: CSRSection): boolean {
  const prose = section.prose?.trim();
  return Boolean(prose && prose.length > 0);
}

export function getCSREditorPath(studyId: string, artifactId: string): string {
  return `/studies/${studyId}/csr/${artifactId}/edit`;
}

async function getCurrentVersionContent(
  artifactId: string,
  token: string
): Promise<Record<string, unknown>> {
  const versions = await artifactsApi.getVersions(artifactId, token);
  const current =
    versions.find((version: ArtifactVersion) => version.is_current) ??
    versions[versions.length - 1];
  return current?.content ?? {};
}

export const csrApi = {
  getStudyReadiness: (studyId: string, token: string, dataCutId?: string) =>
    apiClient.get<StudyCSRReadinessResponse>(
      `/csr/studies/${studyId}/csr-readiness`,
      {
        token,
        params: dataCutId ? { data_cut_id: dataCutId } : undefined,
      }
    ),

  generateFromStudy: (
    studyId: string,
    token: string,
    body?: { data_cut_id?: string; generate_shell?: boolean }
  ) =>
    apiClient.post<CSRGenerationResponse>(
      `/csr/studies/${studyId}/generate-csr`,
      { token, body: body ?? {} }
    ),

  generateFromTlf: (
    tlfArtifactId: string,
    token: string,
    body?: { generate_shell?: boolean }
  ) =>
    apiClient.post<CSRGenerationResponse>(
      `/csr/artifacts/${tlfArtifactId}/generate-csr`,
      { token, body: body ?? {} }
    ),

  loadEditorBundle: async (
    artifactId: string,
    token: string
  ): Promise<CSREditorBundle> => {
    const artifact = await artifactsApi.get(artifactId, token);
    const raw = await getCurrentVersionContent(artifactId, token);
    return {
      artifact,
      content: parseCSRArtifactContent(raw),
      rawContent: raw,
    };
  },

  saveContent: (
    artifactId: string,
    content: Record<string, unknown>,
    token: string,
    changeSummary?: string
  ) =>
    artifactsApi.update(
      artifactId,
      {
        content,
        change_summary: changeSummary,
      },
      token
    ),

  regenerateSection: (
    artifactId: string,
    sectionId: string,
    token: string,
    body?: CSRSectionRegenerateRequest
  ) =>
    apiClient.post<CSRSectionProseResponse>(
      `/csr/artifacts/${artifactId}/sections/${sectionId}/regenerate`,
      { token, body: body ?? {} }
    ),
};
