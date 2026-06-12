import { downloadAuthenticatedBlob } from "@/lib/download";
import { apiClient } from "./client";
import type {
  UploadedFile,
  RawDataset,
  RawField,
  FieldMappingVersion,
  MappingValidationResult,
  SDTMGenerationResponse,
  StudySDTMReadinessResponse,
  SuggestMappingsResponse,
} from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

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

  bulkApproveMappings: (
    datasetId: string,
    body: { notes?: string | null },
    token: string
  ) =>
    apiClient.post<{
      approved_count: number;
      skipped_count: number;
      fields: RawField[];
    }>(`/raw-data/datasets/${datasetId}/mapping/bulk-approve`, { body, token }),

  bulkRejectMappings: (
    datasetId: string,
    mappingIds: string[],
    reason: string,
    token: string
  ) =>
    apiClient.post<{ rejected: number; failed: number }>(
      `/raw-data/datasets/${datasetId}/mapping/bulk-reject`,
      {
        body: { mapping_ids: mappingIds, reason },
        token,
      }
    ),

  downloadMappingExport: async (datasetId: string, token: string): Promise<Blob> => {
    const { blob } = await downloadAuthenticatedBlob(
      `${API_URL}/raw-data/datasets/${datasetId}/mapping/export`,
      token,
      "mapping-export.csv"
    );
    return blob;
  },

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

  suggestMappings: (datasetId: string, token: string) =>
    apiClient.post<SuggestMappingsResponse>(
      `/raw-data/datasets/${datasetId}/suggest-mappings`,
      { token }
    ),

  getStudySdtmReadiness: (studyId: string, token: string) =>
    apiClient.get<StudySDTMReadinessResponse>(
      `/raw-data/studies/${studyId}/sdtm-readiness`,
      { token }
    ),

  generateStudySdtm: (studyId: string, token: string) =>
    apiClient.post<SDTMGenerationResponse>(
      `/raw-data/studies/${studyId}/generate-sdtm`,
      { token }
    ),

  generateSdtm: (datasetId: string, token: string) =>
    apiClient.post<SDTMGenerationResponse>(
      `/raw-data/datasets/${datasetId}/generate-sdtm`,
      { token }
    ),

  applySuggestions: (
    datasetId: string,
    body: {
      ai_decision_id: string;
      suggestions: Array<{
        field_id: string;
        mapped_ecrf_field_id?: string | null;
        mapped_sdtm_variable_id?: string | null;
        notes?: string | null;
      }>;
    },
    token: string
  ) =>
    apiClient.post<RawField[]>(
      `/raw-data/datasets/${datasetId}/apply-suggestions`,
      { body, token }
    ),
};
