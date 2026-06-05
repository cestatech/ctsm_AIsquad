import { apiClient } from "./client";
import type { ArtifactType, GenerationJob, PaginatedResponse } from "@/types";

interface GenerationListParams {
  study_id?: string;
  page?: number;
  page_size?: number;
}

interface CreateJobBody {
  study_id: string;
  artifact_type: ArtifactType;
  model_id?: string;
  prompt_template_id?: string;
  input_context?: Record<string, unknown>;
}

interface GenerateFromBriefBody {
  brief_id: string;
  artifact_type: ArtifactType;
  model_id?: string;
}

export const generationApi = {
  listJobs: (params: GenerationListParams, token: string) =>
    apiClient.get<PaginatedResponse<GenerationJob>>("/generation/jobs", {
      params: params as Record<string, string | number | boolean | undefined>,
      token,
    }),

  getJob: (id: string, token: string) =>
    apiClient.get<GenerationJob>(`/generation/jobs/${id}`, { token }),

  createJob: (body: CreateJobBody, token: string) =>
    apiClient.post<GenerationJob>("/generation/jobs", { body, token }),

  generateFromBrief: (body: GenerateFromBriefBody, token: string) =>
    apiClient.post<GenerationJob>("/generation/jobs/from-brief", { body, token }),
};
