import { apiClient } from "./client";
import { downloadAuthenticatedFile } from "@/lib/download";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export interface StatisticalQCRun {
  id: string;
  organization_id: string;
  study_id: string;
  workflow_step: string;
  status: string;
  source_artifact_id: string | null;
  output_artifact_id: string | null;
  primary_ai_decision_id: string | null;
  qc_ai_decision_id: string | null;
  primary_r_program: string;
  qc_r_program: string;
  primary_program_hash: string | null;
  qc_program_hash: string | null;
  comparison_result: Record<string, unknown> | null;
  created_by_id: string;
  created_at: string;
}

interface StatisticalQCRunListResponse {
  items: StatisticalQCRun[];
  total: number;
  page: number;
  page_size: number;
}

export const statisticalQcApi = {
  listRuns: (
    params: {
      study_id?: string;
      output_artifact_id?: string;
      workflow_step?: string;
      page?: number;
      page_size?: number;
    },
    token: string
  ) =>
    apiClient.get<StatisticalQCRunListResponse>("/statistical-qc/runs", {
      params: params as Record<string, string | number | boolean | undefined>,
      token,
    }),

  getRun: (runId: string, token: string) =>
    apiClient.get<StatisticalQCRun>(`/statistical-qc/runs/${runId}`, { token }),

  downloadPrimaryProgram: (runId: string, workflow: string, token: string) =>
    downloadAuthenticatedFile(
      `${API_URL}/statistical-qc/runs/${runId}/primary-program`,
      `primary_${workflow.toLowerCase()}.R`,
      token
    ),

  downloadQcProgram: (runId: string, workflow: string, token: string) =>
    downloadAuthenticatedFile(
      `${API_URL}/statistical-qc/runs/${runId}/qc-program`,
      `qc_${workflow.toLowerCase()}.R`,
      token
    ),
};
