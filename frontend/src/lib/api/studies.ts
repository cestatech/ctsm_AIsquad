import { apiClient } from "./client";
import type { PaginatedResponse, Study, StudyMember } from "@/types";

interface StudyListParams {
  status?: string;
  page?: number;
  page_size?: number;
}

interface CreateStudyBody {
  protocol_number: string;
  name: string;
  short_name?: string;
  description?: string;
  indication?: string;
  therapeutic_area?: string;
  phase?: string;
  sponsor?: string;
  regulatory_region?: string[];
  start_date?: string;
  end_date?: string;
}

export const studiesApi = {
  list: (params: StudyListParams, token: string) =>
    apiClient.get<PaginatedResponse<Study>>("/studies", {
      params: params as Record<string, string | number | boolean | undefined>,
      token,
    }),

  get: (id: string, token: string) =>
    apiClient.get<Study>(`/studies/${id}`, { token }),

  create: (body: CreateStudyBody, token: string) =>
    apiClient.post<Study>("/studies", { body, token }),

  update: (id: string, body: Partial<CreateStudyBody>, token: string) =>
    apiClient.patch<Study>(`/studies/${id}`, { body, token }),

  archive: (id: string, token: string) =>
    apiClient.post<Study>(`/studies/${id}/archive`, { token }),

  getMembers: (id: string, token: string) =>
    apiClient.get<StudyMember[]>(`/studies/${id}/members`, { token }),

  addMember: (id: string, body: { user_id: string; role: string }, token: string) =>
    apiClient.post<StudyMember>(`/studies/${id}/members`, { body, token }),

  removeMember: (studyId: string, userId: string, token: string) =>
    apiClient.delete<void>(`/studies/${studyId}/members/${userId}`, { token }),
};
