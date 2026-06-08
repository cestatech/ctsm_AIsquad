import type { ApiError, ApiErrorDetail } from "@/types";

/** Extract a human-readable message from a structured FastAPI error body. */
export function formatApiErrorDetail(detail: ApiErrorDetail): string {
  if (typeof detail === "string") {
    return detail;
  }
  if (detail && typeof detail === "object") {
    const message = detail.message ?? detail.code;
    if (message) {
      const issues = detail.issues?.filter(Boolean) ?? [];
      if (issues.length > 0) {
        return `${message} ${issues.slice(0, 3).join("; ")}`;
      }
      return message;
    }
  }
  return "An unexpected error occurred.";
}

export function formatApiError(error: ApiError): string {
  if (error.detail !== undefined && error.detail !== null) {
    return formatApiErrorDetail(error.detail);
  }
  return error.code ?? "An unexpected error occurred.";
}

export function getApiErrorMessage(err: unknown, fallback = "Request failed."): string {
  if (err instanceof Error && err.message && err.message !== "[object Object]") {
    return err.message;
  }
  if (
    err &&
    typeof err === "object" &&
    "error" in err &&
    err.error &&
    typeof err.error === "object"
  ) {
    return formatApiError(err.error as ApiError);
  }
  return fallback;
}
