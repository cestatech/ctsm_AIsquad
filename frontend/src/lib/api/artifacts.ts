import { apiClient } from "./client";
import type { Artifact, ArtifactVersion, PaginatedResponse } from "@/types";

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
};
