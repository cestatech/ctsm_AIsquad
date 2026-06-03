import { apiClient } from "./client";
import type { AuditLog, PaginatedResponse } from "@/types";

interface AuditListParams {
  resource_type?: string;
  action?: string;
  actor_user_id?: string;
  from_date?: string;
  to_date?: string;
  page?: number;
  page_size?: number;
}

export const auditApi = {
  list: (params: AuditListParams, token: string) =>
    apiClient.get<PaginatedResponse<AuditLog>>("/audit", {
      params: params as Record<string, string | number | boolean | undefined>,
      token,
    }),

  get: (id: string, token: string) =>
    apiClient.get<AuditLog>(`/audit/${id}`, { token }),
};
