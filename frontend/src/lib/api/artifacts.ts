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

  delete: (id: string, token: string) =>
    apiClient.delete<void>(`/artifacts/${id}`, { token }),

  getVersions: (id: string, token: string) =>
    apiClient.get<ArtifactVersion[]>(`/artifacts/${id}/versions`, { token }),

  getVersion: (id: string, versionId: string, token: string) =>
    apiClient.get<ArtifactVersion>(`/artifacts/${id}/versions/${versionId}`, { token }),

  downloadCsv: async (id: string, token: string): Promise<{ blob: Blob; filename: string }> => {
    const response = await fetch(`${API_URL}/artifacts/${id}/download-csv`, {
      headers: { Authorization: `Bearer ${token}` },
      credentials: "include",
    });
    if (!response.ok) {
      let detail = "Failed to download CSV";
      try {
        const err = await response.json();
        detail = (err as { detail?: string | { message?: string } }).detail
          ? typeof (err as { detail: unknown }).detail === "string"
            ? (err as { detail: string }).detail
            : ((err as { detail: { message?: string } }).detail?.message ?? detail)
          : detail;
      } catch {
        /* non-JSON error body */
      }
      throw new Error(detail);
    }
    const disposition = response.headers.get("Content-Disposition") ?? "";
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match?.[1] ?? "synthetic_data.csv";
    const blob = await response.blob();
    return { blob, filename };
  },

  downloadContent: async (id: string, token: string): Promise<Blob> => {
    const response = await fetch(`${API_URL}/artifacts/${id}/download`, {
      headers: { Authorization: `Bearer ${token}` },
      credentials: "include",
    });
    if (!response.ok) {
      let detail = "Failed to download artifact";
      try {
        const err = await response.json();
        detail = (err as { detail?: string }).detail ?? detail;
      } catch {
        /* non-JSON error body */
      }
      throw new Error(detail);
    }
    return response.blob();
  },

  downloadDefineXml: async (id: string, token: string): Promise<Blob> => {
    const response = await fetch(`${API_URL}/artifacts/${id}/define-xml`, {
      headers: { Authorization: `Bearer ${token}` },
      credentials: "include",
    });
    if (!response.ok) {
      let detail = "Failed to download define.xml";
      try {
        const err = await response.json();
        detail = (err as { detail?: string }).detail ?? detail;
      } catch {
        /* non-JSON error body */
      }
      throw new Error(detail);
    }
    return response.blob();
  },
};
