import type { ApiError } from "@/types";
import { formatApiError } from "./errors";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    method: string,
    path: string,
    options: {
      body?: unknown;
      params?: Record<string, string | number | boolean | undefined>;
      token?: string;
    } = {}
  ): Promise<T> {
    const url = new URL(`${this.baseUrl}${path}`);

    if (options.params) {
      Object.entries(options.params).forEach(([key, value]) => {
        if (value !== undefined) {
          url.searchParams.set(key, String(value));
        }
      });
    }

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    // Token is injected by the calling hook from the auth store
    if (options.token) {
      headers["Authorization"] = `Bearer ${options.token}`;
    }

    const response = await fetch(url.toString(), {
      method,
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
      credentials: "include", // for refresh token cookie
    });

    if (!response.ok) {
      let error: ApiError;
      try {
        error = await response.json();
      } catch {
        error = { detail: "An unexpected error occurred.", code: "UNKNOWN_ERROR" };
      }
      throw new ApiClientError(response.status, error);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json() as Promise<T>;
  }

  get<T>(path: string, options?: Parameters<typeof this.request>[2]) {
    return this.request<T>("GET", path, options);
  }

  post<T>(path: string, options?: Parameters<typeof this.request>[2]) {
    return this.request<T>("POST", path, options);
  }

  put<T>(path: string, options?: Parameters<typeof this.request>[2]) {
    return this.request<T>("PUT", path, options);
  }

  patch<T>(path: string, options?: Parameters<typeof this.request>[2]) {
    return this.request<T>("PATCH", path, options);
  }

  delete<T>(path: string, options?: Parameters<typeof this.request>[2]) {
    return this.request<T>("DELETE", path, options);
  }

  async postForm<T>(path: string, options: { form: FormData; token?: string }): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const headers: Record<string, string> = {};
    if (options.token) {
      headers["Authorization"] = `Bearer ${options.token}`;
    }
    const response = await fetch(url, {
      method: "POST",
      headers,
      body: options.form,
      credentials: "include",
    });
    if (!response.ok) {
      let error: import("@/types").ApiError;
      try {
        error = await response.json();
      } catch {
        error = { detail: "An unexpected error occurred.", code: "UNKNOWN_ERROR" };
      }
      throw new ApiClientError(response.status, error);
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }
}

export class ApiClientError extends Error {
  constructor(
    public readonly status: number,
    public readonly error: ApiError
  ) {
    super(formatApiError(error));
    this.name = "ApiClientError";
  }
}

export const apiClient = new ApiClient(API_URL);
