import { apiClient } from "./client";
import type { PaginatedResponse, User } from "@/types";

interface UserListParams {
  is_active?: boolean;
  page?: number;
  page_size?: number;
}

interface UpdateUserBody {
  full_name?: string;
  title?: string;
}

export const usersApi = {
  list: (params: UserListParams, token: string) =>
    apiClient.get<PaginatedResponse<User>>("/users", {
      params: params as Record<string, string | number | boolean | undefined>,
      token,
    }),

  get: (id: string, token: string) =>
    apiClient.get<User>(`/users/${id}`, { token }),

  update: (id: string, body: UpdateUserBody, token: string) =>
    apiClient.patch<User>(`/users/${id}`, { body, token }),

  deactivate: (id: string, token: string) =>
    apiClient.post<User>(`/users/${id}/deactivate`, { token }),

  activate: (id: string, token: string) =>
    apiClient.post<User>(`/users/${id}/activate`, { token }),

  invite: (body: { email: string; full_name: string; role?: string }, token: string) =>
    apiClient.post<{ user: User; temporary_password: string }>("/users/invite", { body, token }),
};
