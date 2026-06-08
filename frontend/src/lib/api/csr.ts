import { apiClient } from "./client";
import type { CSRGenerationResponse, StudyCSRReadinessResponse } from "@/types";

export const csrApi = {
  getStudyReadiness: (studyId: string, token: string) =>
    apiClient.get<StudyCSRReadinessResponse>(
      `/csr/studies/${studyId}/csr-readiness`,
      { token }
    ),

  generateFromStudy: (studyId: string, token: string) =>
    apiClient.post<CSRGenerationResponse>(
      `/csr/studies/${studyId}/generate-csr`,
      { token }
    ),

  generateFromTlf: (tlfArtifactId: string, token: string) =>
    apiClient.post<CSRGenerationResponse>(
      `/csr/artifacts/${tlfArtifactId}/generate-csr`,
      { token }
    ),
};
