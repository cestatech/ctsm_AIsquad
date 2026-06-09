import { apiClient } from "./client";
import type { CSRGenerationResponse, StudyCSRReadinessResponse } from "@/types";

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
};
