import { apiClient } from "./client";
import type { Approval, PaginatedResponse } from "@/types";

interface ApprovalQueueParams {
  page?: number;
  page_size?: number;
}

interface CreateApprovalBody {
  artifact_id: string;
  artifact_version_id: string;
  decision: "APPROVED" | "REJECTED";
  comments?: string;
}

export const approvalsApi = {
  queue: (params: ApprovalQueueParams, token: string) =>
    apiClient.get<PaginatedResponse<Approval>>("/approvals/queue", {
      params: params as Record<string, string | number | boolean | undefined>,
      token,
    }),

  list: (artifactId: string, token: string) =>
    apiClient.get<Approval[]>(`/approvals?artifact_id=${artifactId}`, { token }),

  create: (body: CreateApprovalBody, token: string) =>
    apiClient.post<Approval>("/approvals", { body, token }),
};
