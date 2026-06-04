import { apiClient } from "./client";
import type { SponsorIntake, StudyBrief } from "@/types";

export const intakeApi = {
  start: (studyId: string, token: string) =>
    apiClient.post<{ intake: SponsorIntake }>("/intake", {
      body: {},
      token,
      params: { study_id: studyId },
    }),

  get: (intakeId: string, token: string) =>
    apiClient.get<SponsorIntake>(`/intake/${intakeId}`, { token }),

  list: (studyId: string, token: string) =>
    apiClient.get<SponsorIntake[]>("/intake", {
      params: { study_id: studyId },
      token,
    }),

  respond: (intakeId: string, message: string, token: string) =>
    apiClient.post<SponsorIntake>(`/intake/${intakeId}/respond`, {
      body: { message },
      token,
    }),

  compileBrief: (intakeId: string, token: string) =>
    apiClient.post<StudyBrief>(`/intake/${intakeId}/compile`, {
      body: {},
      token,
    }),

  getBrief: (intakeId: string, token: string) =>
    apiClient.get<StudyBrief>(`/intake/${intakeId}/brief`, { token }),
};
