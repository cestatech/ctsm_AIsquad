import { apiClient } from "./client";
import type { PaginatedResponse, UploadedFile } from "@/types";

export const uploadsApi = {
  upload: (studyId: string, file: File, description: string | undefined, token: string) => {
    const form = new FormData();
    form.append("file", file);
    if (description) form.append("description", description);
    return apiClient.postForm<UploadedFile>(`/studies/${studyId}/uploads`, { form, token });
  },

  list: (studyId: string, token: string, page = 1, pageSize = 25) =>
    apiClient.get<PaginatedResponse<UploadedFile>>(`/studies/${studyId}/uploads`, {
      params: { page, page_size: pageSize },
      token,
    }),
};
