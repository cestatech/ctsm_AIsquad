"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { usePermissions } from "@/hooks/usePermissions";
import { rawDataApi } from "@/lib/api/rawData";
import type { RawDataset, RawField } from "@/types";

const MAPPING_STATUS_COLORS: Record<string, string> = {
  UNMAPPED: "bg-slate-100 text-slate-500",
  PENDING_APPROVAL: "bg-amber-100 text-amber-700",
  APPROVED: "bg-emerald-100 text-emerald-700",
  REJECTED: "bg-red-100 text-red-700",
};

const TYPE_COLORS: Record<string, string> = {
  string: "text-blue-600",
  number: "text-emerald-600",
  date: "text-violet-600",
  boolean: "text-amber-600",
  unknown: "text-slate-400",
};

const UPLOAD_STATUS_LABELS: Record<string, string> = {
  UPLOADED: "Uploaded",
  PARSED: "Parsed",
  FAILED: "Parse Failed",
  MAPPED: "Mapped",
};

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface MappingFormState {
  ecrf: string;
  sdtm: string;
  notes: string;
}

interface FieldRowProps {
  field: RawField;
  studyId: string;
  token: string;
  canEdit: boolean;
  canApprove: boolean;
}

function FieldRow({ field, studyId, token, canEdit, canApprove }: FieldRowProps) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [form, setForm] = useState<MappingFormState>({
    ecrf: field.mapped_ecrf_field_id ?? "",
    sdtm: field.mapped_sdtm_variable_id ?? "",
    notes: "",
  });

  const mapMutation = useMutation({
    mutationFn: () =>
      rawDataApi.mapField(
        field.id,
        {
          mapped_ecrf_field_id: form.ecrf.trim() || null,
          mapped_sdtm_variable_id: form.sdtm.trim() || null,
          notes: form.notes.trim() || null,
        },
        token
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["raw-fields", field.raw_dataset_id] });
      queryClient.invalidateQueries({ queryKey: ["mapping-validation", field.raw_dataset_id] });
      setExpanded(false);
    },
  });

  const approveMutation = useMutation({
    mutationFn: () => rawDataApi.approveMapping(field.id, { notes: null }, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["raw-fields", field.raw_dataset_id] });
      queryClient.invalidateQueries({ queryKey: ["mapping-validation", field.raw_dataset_id] });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: () => rawDataApi.rejectMapping(field.id, { notes: null }, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["raw-fields", field.raw_dataset_id] });
      queryClient.invalidateQueries({ queryKey: ["mapping-validation", field.raw_dataset_id] });
    },
  });

  const isBusy = mapMutation.isPending || approveMutation.isPending || rejectMutation.isPending;

  return (
    <>
      <tr
        className="hover:bg-slate-50 cursor-pointer transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        <td className="px-4 py-2.5 text-xs font-mono text-slate-700 whitespace-nowrap">
          {field.column_name}
        </td>
        <td className="px-4 py-2.5">
          <span className={`text-xs font-mono ${TYPE_COLORS[field.inferred_type]}`}>
            {field.inferred_type}
          </span>
        </td>
        <td className="px-4 py-2.5 text-xs text-slate-500">
          {field.mapped_ecrf_field_id ? (
            <span className="font-medium text-slate-700">{field.mapped_ecrf_field_id}</span>
          ) : (
            <span className="text-slate-300">—</span>
          )}
        </td>
        <td className="px-4 py-2.5 text-xs text-slate-500">
          {field.mapped_sdtm_variable_id ? (
            <span className="font-medium text-slate-700">{field.mapped_sdtm_variable_id}</span>
          ) : (
            <span className="text-slate-300">—</span>
          )}
        </td>
        <td className="px-4 py-2.5">
          <span
            className={`text-[10px] px-1.5 py-0.5 font-medium ${
              MAPPING_STATUS_COLORS[field.mapping_status]
            }`}
          >
            {field.mapping_status.replace("_", " ")}
          </span>
        </td>
        <td className="px-4 py-2.5 text-[11px] text-slate-400">
          {field.distinct_count} distinct · {field.missing_count} missing
        </td>
        <td className="px-4 py-2.5 text-slate-400">
          <svg
            className={`w-3.5 h-3.5 transition-transform ${expanded ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-slate-50">
          <td colSpan={7} className="px-4 py-4">
            <div className="grid grid-cols-2 gap-6">
              {/* Sample values + stats */}
              <div>
                <p className="text-[11px] text-slate-500 font-medium mb-2">Sample Values</p>
                {field.sample_values.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {field.sample_values.map((v, i) => (
                      <span
                        key={i}
                        className="text-[11px] font-mono bg-white border border-slate-200 px-1.5 py-0.5 text-slate-600"
                      >
                        {v}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span className="text-[11px] text-slate-400">No samples available</span>
                )}
                {(field.min_value || field.max_value) && (
                  <p className="text-[11px] text-slate-400 mt-2">
                    Range: {field.min_value} → {field.max_value}
                  </p>
                )}
              </div>

              {/* Mapping form */}
              {canEdit && (
                <div>
                  <p className="text-[11px] text-slate-500 font-medium mb-2">Mapping</p>
                  <div className="space-y-2">
                    <div>
                      <label className="text-[10px] text-slate-400 uppercase tracking-wide">
                        eCRF Field
                      </label>
                      <input
                        type="text"
                        value={form.ecrf}
                        onChange={(e) => setForm((f) => ({ ...f, ecrf: e.target.value }))}
                        placeholder="e.g. SUBJID"
                        className="mt-0.5 w-full border border-slate-200 bg-white text-xs px-2.5 py-1.5 focus:outline-none focus:border-brand-400"
                        onClick={(e) => e.stopPropagation()}
                      />
                    </div>
                    <div>
                      <label className="text-[10px] text-slate-400 uppercase tracking-wide">
                        SDTM Variable
                      </label>
                      <input
                        type="text"
                        value={form.sdtm}
                        onChange={(e) => setForm((f) => ({ ...f, sdtm: e.target.value }))}
                        placeholder="e.g. DM.SUBJID"
                        className="mt-0.5 w-full border border-slate-200 bg-white text-xs px-2.5 py-1.5 focus:outline-none focus:border-brand-400"
                        onClick={(e) => e.stopPropagation()}
                      />
                    </div>
                    <div>
                      <label className="text-[10px] text-slate-400 uppercase tracking-wide">
                        Notes
                      </label>
                      <input
                        type="text"
                        value={form.notes}
                        onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                        placeholder="Optional mapping rationale"
                        className="mt-0.5 w-full border border-slate-200 bg-white text-xs px-2.5 py-1.5 focus:outline-none focus:border-brand-400"
                        onClick={(e) => e.stopPropagation()}
                      />
                    </div>
                    <div className="flex items-center gap-2 pt-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          mapMutation.mutate();
                        }}
                        disabled={isBusy || (!form.ecrf.trim() && !form.sdtm.trim())}
                        className="text-xs bg-brand-600 hover:bg-brand-500 text-white font-semibold px-3 py-1.5 transition-colors disabled:opacity-50"
                      >
                        {mapMutation.isPending ? "Saving…" : "Save mapping"}
                      </button>
                      {canApprove && field.mapping_status === "PENDING_APPROVAL" && (
                        <>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              approveMutation.mutate();
                            }}
                            disabled={isBusy}
                            className="text-xs bg-emerald-600 hover:bg-emerald-500 text-white font-semibold px-3 py-1.5 transition-colors disabled:opacity-50"
                          >
                            {approveMutation.isPending ? "Approving…" : "Approve"}
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              rejectMutation.mutate();
                            }}
                            disabled={isBusy}
                            className="text-xs bg-red-600 hover:bg-red-500 text-white font-semibold px-3 py-1.5 transition-colors disabled:opacity-50"
                          >
                            {rejectMutation.isPending ? "Rejecting…" : "Reject"}
                          </button>
                        </>
                      )}
                    </div>
                    {(mapMutation.isError || approveMutation.isError || rejectMutation.isError) && (
                      <p className="text-[11px] text-red-600 mt-1">
                        {(mapMutation.error ?? approveMutation.error ?? rejectMutation.error) instanceof Error
                          ? (mapMutation.error ?? approveMutation.error ?? rejectMutation.error as Error).message
                          : "Action failed"}
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

interface DatasetPanelProps {
  dataset: RawDataset;
  studyId: string;
  token: string;
  canEdit: boolean;
  canApprove: boolean;
}

function DatasetPanel({ dataset, studyId, token, canEdit, canApprove }: DatasetPanelProps) {
  const { data: fields, isLoading } = useQuery({
    queryKey: ["raw-fields", dataset.id, token],
    queryFn: () => rawDataApi.listFields(dataset.id, token),
    enabled: !!token,
  });

  const { data: validation } = useQuery({
    queryKey: ["mapping-validation", dataset.id, token],
    queryFn: () => rawDataApi.validateMapping(dataset.id, token),
    enabled: !!token,
  });

  return (
    <div>
      {/* Validation summary */}
      {validation && (
        <div className="px-5 py-3 bg-slate-50 border-b border-slate-100 flex items-center gap-6 text-xs">
          <span className="text-slate-500">
            Coverage:{" "}
            <span className="font-semibold text-slate-900">
              {validation.coverage_pct.toFixed(0)}%
            </span>
          </span>
          <span className="text-slate-500">
            Mapped:{" "}
            <span className="font-semibold text-emerald-700">{validation.mapped_fields}</span>
            {" / "}
            {validation.total_fields}
          </span>
          <span className="text-slate-500">
            Approved:{" "}
            <span className="font-semibold text-blue-700">{validation.approved_fields}</span>
          </span>
          <span className="text-slate-500">
            Pending:{" "}
            <span className="font-semibold text-amber-700">{validation.pending_fields}</span>
          </span>
          {validation.issues.length > 0 && (
            <span className="text-red-600 font-medium">
              {validation.issues.length} issue{validation.issues.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>
      )}

      {/* Issues */}
      {validation && validation.issues.length > 0 && (
        <div className="px-5 py-2 bg-red-50 border-b border-red-100">
          <ul className="space-y-0.5">
            {validation.issues.map((issue, i) => (
              <li key={i} className="text-[11px] text-red-700">
                · {issue}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Field table */}
      {isLoading ? (
        <div className="px-5 py-8 text-center text-xs text-slate-400">Loading fields…</div>
      ) : !fields || fields.length === 0 ? (
        <div className="px-5 py-8 text-center text-xs text-slate-400">
          No fields found. The file may still be parsing.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-slate-100">
                {["Column", "Type", "eCRF Field", "SDTM Variable", "Status", "Stats", ""].map(
                  (h) => (
                    <th
                      key={h}
                      className="px-4 py-2 text-[10px] uppercase tracking-wide text-slate-400 font-semibold whitespace-nowrap"
                    >
                      {h}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {fields.map((field) => (
                <FieldRow
                  key={field.id}
                  field={field}
                  studyId={studyId}
                  token={token}
                  canEdit={canEdit}
                  canApprove={canApprove}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function UploadDetailPage({
  params,
}: {
  params: { id: string; fileId: string };
}) {
  const { token, role } = useAuthStore();
  const perms = usePermissions(role);
  const studyId = params.id;
  const fileId = params.fileId;
  const [activeDataset, setActiveDataset] = useState<string | null>(null);

  const { data: file, isLoading: fileLoading } = useQuery({
    queryKey: ["upload-file", fileId, token],
    queryFn: () => rawDataApi.getFile(fileId, token!),
    enabled: !!token,
  });

  const { data: datasetsData, isLoading: datasetsLoading } = useQuery({
    queryKey: ["raw-datasets", fileId, token],
    queryFn: () => rawDataApi.listDatasets(fileId, token!),
    enabled: !!token,
    select: (data) => data.items as RawDataset[],
  });

  const datasets = datasetsData ?? [];
  const currentDataset = activeDataset
    ? datasets.find((d) => d.id === activeDataset) ?? datasets[0]
    : datasets[0];

  if (fileLoading) {
    return (
      <div className="px-8 py-16 text-center text-slate-400 text-sm">Loading file…</div>
    );
  }

  if (!file) {
    return (
      <div className="px-8 py-16 text-center text-slate-400 text-sm">File not found.</div>
    );
  }

  const uploadStatusColor: Record<string, string> = {
    UPLOADED: "bg-slate-100 text-slate-600",
    PARSED: "bg-emerald-100 text-emerald-700",
    FAILED: "bg-red-100 text-red-700",
    MAPPED: "bg-blue-100 text-blue-700",
  };

  return (
    <div>
      {/* Header */}
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <div className="flex items-center gap-3 mb-2 text-sm">
          <Link
            href="/studies"
            className="text-slate-400 hover:text-slate-700 transition-colors"
          >
            Studies
          </Link>
          <span className="text-slate-300">/</span>
          <Link
            href={`/studies/${studyId}`}
            className="text-slate-400 hover:text-slate-700 transition-colors"
          >
            Study
          </Link>
          <span className="text-slate-300">/</span>
          <span className="text-slate-600">Uploads</span>
        </div>

        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <span
                className={`text-xs px-2 py-0.5 font-medium ${
                  uploadStatusColor[file.upload_status] ?? "bg-slate-100 text-slate-600"
                }`}
              >
                {UPLOAD_STATUS_LABELS[file.upload_status] ?? file.upload_status}
              </span>
              <span className="text-xs text-slate-400 font-mono">{file.mime_type}</span>
            </div>
            <h1 className="font-display text-xl font-bold text-slate-900">
              {file.original_filename}
            </h1>
            <p className="text-slate-500 text-xs mt-1">
              {formatBytes(file.file_size_bytes)}
              {file.file_hash && (
                <> · SHA-256: <span className="font-mono">{file.file_hash.slice(0, 16)}…</span></>
              )}
              {" · "}Uploaded {new Date(file.created_at).toLocaleString()}
            </p>
          </div>
        </div>
      </div>

      {/* Content */}
      {datasetsLoading ? (
        <div className="px-8 py-16 text-center text-slate-400 text-sm">
          Parsing file…
        </div>
      ) : datasets.length === 0 ? (
        <div className="px-8 py-16 text-center">
          <p className="text-slate-500 text-sm font-medium mb-1">No datasets found</p>
          <p className="text-slate-400 text-xs">
            This file has not been parsed yet, or parsing failed.
          </p>
          {file.upload_status === "FAILED" && (
            <p className="text-red-600 text-xs mt-3">Parse failed. Re-upload to retry.</p>
          )}
        </div>
      ) : (
        <div className="px-8 py-6">
          {/* Dataset tabs */}
          {datasets.length > 1 && (
            <div className="flex gap-1 mb-4 border-b border-slate-200">
              {datasets.map((ds) => (
                <button
                  key={ds.id}
                  onClick={() => setActiveDataset(ds.id)}
                  className={`px-4 py-2 text-xs font-medium border-b-2 -mb-px transition-colors ${
                    (currentDataset?.id ?? "") === ds.id
                      ? "border-brand-600 text-brand-700"
                      : "border-transparent text-slate-500 hover:text-slate-700"
                  }`}
                >
                  {ds.dataset_name}
                  <span className="ml-1.5 text-[10px] text-slate-400">
                    {ds.column_count} cols · {ds.row_count} rows
                  </span>
                </button>
              ))}
            </div>
          )}

          {/* Single dataset label when no tabs */}
          {datasets.length === 1 && currentDataset && (
            <div className="flex items-center gap-4 mb-4">
              <h2 className="font-display font-semibold text-slate-900 text-sm">
                {currentDataset.dataset_name}
              </h2>
              <span className="text-xs text-slate-400">
                {currentDataset.column_count} columns · {currentDataset.row_count} rows
              </span>
              <span
                className={`text-[10px] px-1.5 py-0.5 font-medium ${
                  currentDataset.parse_status === "PARSED"
                    ? "bg-emerald-100 text-emerald-700"
                    : currentDataset.parse_status === "FAILED"
                    ? "bg-red-100 text-red-700"
                    : "bg-amber-100 text-amber-700"
                }`}
              >
                {currentDataset.parse_status}
              </span>
            </div>
          )}

          {/* Field mapping table */}
          {currentDataset && (
            <div className="bg-white border border-slate-200">
              <div className="px-5 py-3.5 border-b border-slate-100">
                <h3 className="font-display font-semibold text-slate-900 text-sm">
                  Field Mapping
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Click a row to expand and map the column to an eCRF field or SDTM variable.
                </p>
              </div>
              <DatasetPanel
                dataset={currentDataset}
                studyId={studyId}
                token={token!}
                canEdit={perms.canCreateArtifact}
                canApprove={perms.canApproveArtifact}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
