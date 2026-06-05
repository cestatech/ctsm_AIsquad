import { apiClient } from "./client";
import type {
  UploadedFile,
  RawDataset,
  RawField,
  FieldMappingVersion,
  MappingValidationResult,
} from "@/types";

interface RawDatasetListResponse {
  items: RawDataset[];
  total: number;
}

export const rawDataApi = {
  getFile: (fileId: string, token: string) =>
    apiClient.get<UploadedFile>(`/raw-data/files/${fileId}`, { token }),

  listDatasets: (fileId: string, token: string) =>
    apiClient.get<RawDatasetListResponse>(`/raw-data/files/${fileId}/datasets`, {
      token,
    }),

  listFields: (datasetId: string, token: string) =>
    apiClient.get<RawField[]>(`/raw-data/datasets/${datasetId}/fields`, {
      token,
    }),

  mapField: (
    fieldId: string,
    body: {
      mapped_ecrf_field_id?: string | null;
      mapped_sdtm_variable_id?: string | null;
      notes?: string | null;
    },
    token: string
  ) =>
    apiClient.put<RawField>(`/raw-data/fields/${fieldId}/mapping`, {
      body,
      token,
    }),

  approveMapping: (
    fieldId: string,
    body: { notes?: string | null },
    token: string
  ) =>
    apiClient.post<RawField>(`/raw-data/fields/${fieldId}/mapping/approve`, {
      body,
      token,
    }),

  rejectMapping: (
    fieldId: string,
    body: { notes?: string | null },
    token: string
  ) =>
    apiClient.post<RawField>(`/raw-data/fields/${fieldId}/mapping/reject`, {
      body,
      token,
    }),

  validateMapping: (datasetId: string, token: string) =>
    apiClient.get<MappingValidationResult>(
      `/raw-data/datasets/${datasetId}/validate`,
      { token }
    ),

  getMappingHistory: (fieldId: string, token: string) =>
    apiClient.get<FieldMappingVersion[]>(
      `/raw-data/fields/${fieldId}/mapping/history`,
      { token }
    ),
};
