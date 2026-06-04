import { apiClient } from "./client";
import type { Organization } from "@/types";

interface OrgUpdateBody {
  name?: string;
  description?: string;
  logo_url?: string;
  settings?: Record<string, unknown>;
}

export interface OrgDetail extends Organization {
  settings: Record<string, unknown>;
  updated_at: string;
}

export const organizationsApi = {
  getMe: (token: string) =>
    apiClient.get<OrgDetail>("/organizations/me", { token }),

  updateMe: (body: OrgUpdateBody, token: string) =>
    apiClient.patch<OrgDetail>("/organizations/me", { body, token }),
};
