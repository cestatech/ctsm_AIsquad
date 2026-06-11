import { apiClient } from "./client";
import { triggerBlobDownload } from "@/lib/artifactDownload";
import type {
  SubmissionCreateResponse,
  SubmissionManifest,
  SubmissionPackage,
  SubmissionReadiness,
} from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

interface SubmissionPackageListResponse {
  items: SubmissionPackage[];
  total: number;
}

export const submissionsApi = {
  getReadiness: (studyId: string, token: string) =>
    apiClient.get<SubmissionReadiness>(`/submissions/studies/${studyId}/readiness`, {
      token,
    }),

  createPackage: (studyId: string, token: string) =>
    apiClient.post<SubmissionCreateResponse>(`/submissions/studies/${studyId}/create`, {
      token,
      body: {},
    }),

  listForStudy: (studyId: string, token: string) =>
    apiClient.get<SubmissionPackageListResponse>(`/submissions/studies/${studyId}`, {
      token,
    }),

  getManifest: (packageId: string, token: string) =>
    apiClient.get<SubmissionManifest>(`/submissions/${packageId}/manifest`, { token }),

  downloadZip: async (
    packageId: string,
    token: string
  ): Promise<{ blob: Blob; filename: string }> => {
    const response = await fetch(`${API_URL}/submissions/${packageId}/download`, {
      headers: { Authorization: `Bearer ${token}` },
      credentials: "include",
    });
    if (!response.ok) {
      let detail = "Failed to download submission package";
      try {
        const err = (await response.json()) as {
          detail?: string | { message?: string };
        };
        const raw = err.detail;
        detail =
          typeof raw === "string"
            ? raw
            : (raw as { message?: string })?.message ?? detail;
      } catch {
        /* non-JSON error body */
      }
      throw new Error(detail);
    }
    const disposition = response.headers.get("Content-Disposition") ?? "";
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match?.[1] ?? `submission_${packageId}.zip`;
    const blob = await response.blob();
    return { blob, filename };
  },

  triggerZipDownload: async (packageId: string, token: string) => {
    const { blob, filename } = await submissionsApi.downloadZip(packageId, token);
    triggerBlobDownload(blob, filename);
  },
};
