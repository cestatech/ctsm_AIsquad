import { apiClient } from "./client";
import type { User } from "@/types";

interface LoginPayload {
  email: string;
  password: string;
}

interface RegisterPayload {
  organization_name: string;
  organization_slug: string;
  full_name: string;
  email: string;
  password: string;
}

interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export const authApi = {
  login: (body: LoginPayload) =>
    apiClient.post<AuthResponse>("/auth/login", { body }),

  register: (body: RegisterPayload) =>
    apiClient.post<AuthResponse>("/auth/register", { body }),

  refresh: () =>
    apiClient.post<TokenResponse>("/auth/refresh"),

  logout: () =>
    apiClient.post<void>("/auth/logout"),

  me: (token: string) =>
    apiClient.get<User>("/auth/me", { token }),

  changePassword: (body: { current_password: string; new_password: string }, token: string) =>
    apiClient.post<void>("/auth/change-password", { body, token }),
};
