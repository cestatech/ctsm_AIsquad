import { apiClient } from "./client";

export interface TLFGenerationResponse {
  artifact_id: string;
  artifact_version_id: string;
  ai_decision_id: string;
  validation_run_id: string;
  table_count: number;
  study_id: string;
  source_adam_artifact_ids: string[];
}

export const tlfApi = {
  generateFromAdam: (adamArtifactId: string, token: string) =>
    apiClient.post<TLFGenerationResponse>(
      `/tlf/artifacts/${adamArtifactId}/generate-tlf`,
      { token }
    ),
};
