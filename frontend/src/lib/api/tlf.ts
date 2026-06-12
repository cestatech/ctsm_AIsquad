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

export interface ListingFigureEntry {
  sap_section: string;
  output_title: string;
  output_type: "table" | "listing" | "figure";
  tlf_index: number;
  status: string;
}

export interface ListingFigureCatalog {
  sap_artifact_id: string | null;
  entries: ListingFigureEntry[];
}

export const tlfApi = {
  generateFromAdam: (adamArtifactId: string, token: string) =>
    apiClient.post<TLFGenerationResponse>(
      `/tlf/artifacts/${adamArtifactId}/generate-tlf`,
      { token }
    ),

  getCatalog: (artifactId: string, token: string) =>
    apiClient.get<ListingFigureCatalog>(`/tlf/artifacts/${artifactId}/catalog`, {
      token,
    }),
};
