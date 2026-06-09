import { apiClient } from "./client";
import type { DataSourceType, PaginatedResponse, UploadedFile } from "@/types";

export interface LiveUploadOptions {
  data_source_type?: DataSourceType;
  data_cut_label?: string;
  data_cut_date?: string;
  notes?: string;
  description?: string;
}

export const uploadsApi = {
  upload: (
    studyId: string,
    file: File,
    options: LiveUploadOptions | string | undefined,
    token: string
  ) => {
    const form = new FormData();
    form.append("file", file);
    const opts: LiveUploadOptions =
      typeof options === "string" ? { description: options } : options ?? {};
    if (opts.description) form.append("description", opts.description);
    if (opts.notes) form.append("notes", opts.notes);
    if (opts.data_source_type) form.append("data_source_type", opts.data_source_type);
    if (opts.data_cut_label) form.append("data_cut_label", opts.data_cut_label);
    if (opts.data_cut_date) form.append("data_cut_date", opts.data_cut_date);
    return apiClient.postForm<UploadedFile>(`/studies/${studyId}/uploads`, { form, token });
  },

  list: (studyId: string, token: string, page = 1, pageSize = 25) =>
    apiClient.get<PaginatedResponse<UploadedFile>>(`/studies/${studyId}/uploads`, {
      params: { page, page_size: pageSize },
      token,
    }),
};
