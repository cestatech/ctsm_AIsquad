import { apiClient } from "./client";
import type {
  AIDecision,
  DataLineage,
  HumanOverride,
  PaginatedResponse,
  SyntheticDataRun,
  ValidationEvidence,
} from "@/types";

interface DecisionListParams {
  study_id: string;
  agent_name?: string;
  decision_type?: string;
  decision_status?: string;
  page?: number;
  page_size?: number;
}

interface OverrideListParams {
  study_id: string;
  context_type?: string;
  page?: number;
  page_size?: number;
}

interface ValidationListParams {
  study_id: string;
  evidence_status?: string;
  rule_category?: string;
  page?: number;
  page_size?: number;
}

export const intelligenceApi = {
  listDecisions: (params: DecisionListParams, token: string) =>
    apiClient.get<PaginatedResponse<AIDecision>>("/intelligence/decisions", {
      params: params as unknown as Record<string, string | number | boolean | undefined>,
      token,
    }),

  listPendingDecisions: (token: string) =>
    apiClient.get<AIDecision[]>("/intelligence/decisions/pending", { token }),

  getDecision: (id: string, token: string) =>
    apiClient.get<AIDecision>(`/intelligence/decisions/${id}`, { token }),

  acceptDecision: (id: string, body: { notes?: string }, token: string) =>
    apiClient.post<AIDecision>(`/intelligence/decisions/${id}/accept`, { body, token }),

  rejectDecision: (id: string, body: { notes: string }, token: string) =>
    apiClient.post<AIDecision>(`/intelligence/decisions/${id}/reject`, { body, token }),

  listOverrides: (params: OverrideListParams, token: string) =>
    apiClient.get<PaginatedResponse<HumanOverride>>("/intelligence/overrides", {
      params: params as unknown as Record<string, string | number | boolean | undefined>,
      token,
    }),

  getLineageChain: (params: { target_type: string; target_id: string }, token: string) =>
    apiClient.get<{ upstream: DataLineage[]; downstream: DataLineage[] }>(
      "/intelligence/lineage/chain",
      { params: params as Record<string, string | number | boolean | undefined>, token }
    ),

  listValidationEvidence: (params: ValidationListParams, token: string) =>
    apiClient.get<PaginatedResponse<ValidationEvidence>>(
      "/intelligence/validation-evidence",
      { params: params as unknown as Record<string, string | number | boolean | undefined>, token }
    ),

  waiveFinding: (id: string, body: { reason: string }, token: string) =>
    apiClient.post<ValidationEvidence>(`/intelligence/validation-evidence/${id}/waive`, {
      body,
      token,
    }),

  listSyntheticRuns: (
    params: { study_id: string; page?: number; page_size?: number },
    token: string
  ) =>
    apiClient.get<PaginatedResponse<SyntheticDataRun>>("/intelligence/synthetic-runs", {
      params: params as Record<string, string | number | boolean | undefined>,
      token,
    }),
};
