import { apiClient } from "./client";
import type { Comment, PaginatedResponse } from "@/types";

interface CommentListParams {
  artifact_id: string;
  include_resolved?: boolean;
  page?: number;
  page_size?: number;
}

interface CreateCommentBody {
  artifact_id: string;
  artifact_version_id?: string;
  parent_id?: string;
  body: string;
}

interface UpdateCommentBody {
  body: string;
}

export const commentsApi = {
  list: (params: CommentListParams, token: string) =>
    apiClient.get<{ items: Comment[]; total: number }>("/comments", {
      params: params as unknown as Record<string, string | number | boolean | undefined>,
      token,
    }),

  create: (body: CreateCommentBody, token: string) =>
    apiClient.post<Comment>("/comments", { body, token }),

  update: (id: string, body: UpdateCommentBody, token: string) =>
    apiClient.patch<Comment>(`/comments/${id}`, { body, token }),

  resolve: (id: string, token: string) =>
    apiClient.post<Comment>(`/comments/${id}/resolve`, { token }),

  delete: (id: string, token: string) =>
    apiClient.delete<void>(`/comments/${id}`, { token }),
};
