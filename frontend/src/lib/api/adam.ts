import { apiClient } from "./client";
import type { ADAMGenerationResponse, StudyADAMReadinessResponse } from "@/types";

export const adamApi = {
  getStudyReadiness: (studyId: string, token: string) =>
    apiClient.get<StudyADAMReadinessResponse>(
      `/adam/studies/${studyId}/adam-readiness`,
      { token }
    ),

  generateFromStudy: (studyId: string, token: string) =>
    apiClient.post<ADAMGenerationResponse>(
      `/adam/studies/${studyId}/generate-adam`,
      { token }
    ),

  generateFromSdtm: (sdtmArtifactId: string, token: string) =>
    apiClient.post<ADAMGenerationResponse>(
      `/adam/artifacts/${sdtmArtifactId}/generate-adam`,
      { token }
    ),
};
