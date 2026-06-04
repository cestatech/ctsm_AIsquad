import { apiClient } from "./client";
import type { PaginatedResponse, ValidationRun } from "@/types";

interface ValidationListParams {
  artifact_id?: string;
  page?: number;
  page_size?: number;
}

interface TriggerRunBody {
  artifact_id: string;
  artifact_version_id: string;
  engine?: string;
  rule_set_version?: string;
}

export const validationApi = {
  listRuns: (params: ValidationListParams, token: string) =>
    apiClient.get<PaginatedResponse<ValidationRun>>("/validation/runs", {
      params: params as Record<string, string | number | boolean | undefined>,
      token,
    }),

  getRun: (id: string, token: string) =>
    apiClient.get<ValidationRun>(`/validation/runs/${id}`, { token }),

  triggerRun: (body: TriggerRunBody, token: string) =>
    apiClient.post<ValidationRun>("/validation/runs", { body, token }),
};
