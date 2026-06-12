import { buildArtifactFallbackFilename } from "@/lib/artifactDownload";
import { downloadAuthenticatedBlob } from "@/lib/download";
import { apiClient } from "./client";
import type { Artifact, ArtifactVersion, PaginatedResponse } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

interface ArtifactListParams {
  study_id?: string;
  artifact_type?: string;
  status?: string;
  page?: number;
  page_size?: number;
}

interface CreateArtifactBody {
  study_id: string;
  artifact_type: string;
  name: string;
  description?: string;
  tags?: string[];
  content?: Record<string, unknown>;
  change_summary?: string;
}

export const artifactsApi = {
  list: (params: ArtifactListParams, token: string) =>
    apiClient.get<PaginatedResponse<Artifact>>("/artifacts", {
      params: params as Record<string, string | number | boolean | undefined>,
      token,
    }),

  get: (id: string, token: string) =>
    apiClient.get<Artifact>(`/artifacts/${id}`, { token }),

  create: (body: CreateArtifactBody, token: string) =>
    apiClient.post<Artifact>("/artifacts", { body, token }),

  update: (
    id: string,
    body: { name?: string; description?: string; content?: Record<string, unknown>; change_summary?: string },
    token: string
  ) => apiClient.patch<Artifact>(`/artifacts/${id}`, { body, token }),

  submit: (id: string, token: string) =>
    apiClient.post<Artifact>(`/artifacts/${id}/submit`, { token }),

  lock: (id: string, token: string) =>
    apiClient.post<Artifact>(`/artifacts/${id}/lock`, { token }),

  amend: (id: string, token: string) =>
    apiClient.post<Artifact>(`/artifacts/${id}/amend`, { token }),

  revise: (id: string, token: string) =>
    apiClient.post<Artifact>(`/artifacts/${id}/revise`, { token }),

  delete: (id: string, token: string) =>
    apiClient.delete<void>(`/artifacts/${id}`, { token }),

  getVersions: (id: string, token: string) =>
    apiClient.get<ArtifactVersion[]>(`/artifacts/${id}/versions`, { token }),

  getVersion: (id: string, versionId: string, token: string) =>
    apiClient.get<ArtifactVersion>(`/artifacts/${id}/versions/${versionId}`, { token }),

  exportArtifact: (
    id: string,
    format: "docx" | "pdf" | "csv" | "zip" | "xml",
    token: string,
    artifact?: Pick<Artifact, "artifact_type" | "name" | "current_version_number">
  ): Promise<{ blob: Blob; filename: string }> =>
    downloadAuthenticatedBlob(
      `${API_URL}/artifacts/${id}/export?format=${format}`,
      token,
      artifact ? buildArtifactFallbackFilename(artifact, format) : `artifact.${format}`
    ),

  downloadCsv: (id: string, token: string): Promise<{ blob: Blob; filename: string }> =>
    downloadAuthenticatedBlob(
      `${API_URL}/artifacts/${id}/download-csv`,
      token,
      "synthetic_data.csv"
    ),

  downloadContent: async (id: string, token: string): Promise<Blob> => {
    const { blob } = await downloadAuthenticatedBlob(
      `${API_URL}/artifacts/${id}/download`,
      token,
      "artifact.json"
    );
    return blob;
  },

  downloadDefineXml: async (id: string, token: string): Promise<Blob> => {
    const { blob } = await downloadAuthenticatedBlob(
      `${API_URL}/artifacts/${id}/define-xml`,
      token,
      "define.xml"
    );
    return blob;
  },
};
