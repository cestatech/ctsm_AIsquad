"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { useStudyPermissions } from "@/hooks/useStudyPermissions";
import { getApiErrorMessage } from "@/lib/api/errors";
import { generationApi } from "@/lib/api/generation";
import type { ArtifactType, GenerationJob } from "@/types";

const STATUS_COLORS: Record<string, string> = {
  PENDING:   "bg-slate-100 text-slate-600",
  QUEUED:    "bg-amber-100 text-amber-600",
  RUNNING:   "bg-blue-100 text-blue-700",
  COMPLETED: "bg-emerald-100 text-emerald-700",
  FAILED:    "bg-red-100 text-red-700",
  CANCELLED: "bg-slate-100 text-slate-500",
};

const ARTIFACT_TYPE_LABELS: Record<string, string> = {
  PROTOCOL: "Protocol", ICF: "ICF", SAP: "SAP", EDC_CRF: "eCRF",
  TRACEABILITY_MATRIX: "Traceability Matrix", SDTM_DATASET: "SDTM Dataset",
  ADAM_DATASET: "ADaM Dataset", TLF: "TLF", VALIDATION_REPORT: "Validation Report",
  CSR: "CSR", SUBMISSION_PACKAGE: "Submission Package", OTHER: "Other",
};

const ARTIFACT_TYPES: ArtifactType[] = [
  "PROTOCOL", "ICF", "SAP", "EDC_CRF", "SDTM_DATASET",
  "ADAM_DATASET", "TLF", "CSR",
];

const PAGE_SIZE = 25;
const ACTIVE_STATUSES = new Set(["PENDING", "QUEUED", "RUNNING"]);

function JobRow({
  job,
  canStop,
  onStop,
  isStopping,
}: {
  job: GenerationJob;
  canStop: boolean;
  onStop: (jobId: string) => void;
  isStopping: boolean;
}) {
  const duration =
    job.started_at && job.completed_at
      ? Math.round((new Date(job.completed_at).getTime() - new Date(job.started_at).getTime()) / 1000)
      : null;

  return (
    <tr className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
      <td className="px-4 py-3">
        <span className={`text-xs px-2 py-0.5 font-medium ${STATUS_COLORS[job.status] ?? "bg-slate-100 text-slate-600"}`}>
          {job.status}
        </span>
      </td>
      <td className="px-4 py-3 text-xs text-slate-700 font-medium">
        {ARTIFACT_TYPE_LABELS[job.artifact_type] ?? job.artifact_type}
      </td>
      <td className="px-4 py-3 text-xs font-mono text-slate-500">{job.study_id.slice(0, 8)}…</td>
      <td className="px-4 py-3 text-xs text-slate-500 font-mono">{job.model_id}</td>
      <td className="px-4 py-3 text-xs text-slate-500">
        {job.output_artifact_id ? (
          <span className="text-brand-600 font-mono">{job.output_artifact_id.slice(0, 8)}…</span>
        ) : job.error_message ? (
          <span className="text-red-500 truncate max-w-[160px] block" title={job.error_message}>
            {job.error_message.slice(0, 40)}{job.error_message.length > 40 && "…"}
          </span>
        ) : "—"}
      </td>
      <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">
        {duration != null ? `${duration}s` : "—"}
      </td>
      <td className="px-4 py-3 text-xs text-slate-500 font-mono whitespace-nowrap">
        {new Date(job.created_at).toLocaleString("en-US", {
          month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
        })}
      </td>
      <td className="px-4 py-3 text-xs">
        {canStop && ACTIVE_STATUSES.has(job.status) ? (
          <button
            type="button"
            onClick={() => onStop(job.id)}
            disabled={isStopping}
            className="text-red-600 hover:text-red-700 font-medium disabled:opacity-50"
          >
            {isStopping ? "Stopping…" : "Stop"}
          </button>
        ) : (
          <span className="text-slate-300">—</span>
        )}
      </td>
    </tr>
  );
}

export default function GenerationPage() {
  const { token } = useAuthStore();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [showNew, setShowNew] = useState(false);
  const [jobError, setJobError] = useState<string | null>(null);
  const [stoppingJobId, setStoppingJobId] = useState<string | null>(null);
  const [form, setForm] = useState({
    study_id: "",
    artifact_type: "PROTOCOL" as ArtifactType,
    model_id: "claude-sonnet-4-6",
  });
  const perms = useStudyPermissions(form.study_id || undefined);

  const { data, isLoading } = useQuery({
    queryKey: ["generation-jobs", token, page],
    queryFn: () => generationApi.listJobs({ page, page_size: PAGE_SIZE }, token!),
    enabled: !!token,
    refetchInterval: 10_000,
  });

  const cancelMutation = useMutation({
    mutationFn: (jobId: string) => generationApi.cancelJob(jobId, token!),
    onMutate: (jobId) => setStoppingJobId(jobId),
    onSuccess: () => {
      setJobError(null);
      queryClient.invalidateQueries({ queryKey: ["generation-jobs"] });
    },
    onError: (err) =>
      setJobError(getApiErrorMessage(err, "Failed to stop generation.")),
    onSettled: () => setStoppingJobId(null),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      generationApi.createJob(
        {
          study_id: form.study_id.trim(),
          artifact_type: form.artifact_type,
          model_id: form.model_id,
        },
        token!
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["generation-jobs"] });
      setShowNew(false);
      setForm({ study_id: "", artifact_type: "PROTOCOL", model_id: "claude-sonnet-4-6" });
    },
    onError: (err) => setJobError(err instanceof Error ? err.message : "Failed to create job."),
  });

  const jobs = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display text-xl font-bold text-slate-900">AI Generation</h1>
            <p className="text-slate-500 text-sm mt-0.5">
              {total} total jobs · Refreshes every 10s
            </p>
          </div>
          {perms.canTriggerGeneration && (
            <button
              onClick={() => { setShowNew(true); setJobError(null); }}
              className="text-sm font-semibold px-4 py-2 bg-brand-600 text-white hover:bg-brand-500 transition-colors"
            >
              New Generation
            </button>
          )}
        </div>
      </div>

      <div className="px-8 py-6">
        <div className="bg-amber-50 border border-amber-200 px-4 py-2.5 mb-5 text-xs text-amber-800">
          Jobs are queued and executed by background workers. Output artifacts surface as DRAFT and require review at{" "}
          <a href="/intelligence/decisions" className="underline">Intelligence → AI Decisions</a>.
        </div>

        <div className="bg-white border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Type</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Study</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Model</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Output / Error</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Duration</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Triggered</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-slate-400 text-sm">Loading…</td>
                </tr>
              ) : jobs.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-slate-400 text-sm">
                    No generation jobs yet.{" "}
                    {perms.canTriggerGeneration && (
                      <button onClick={() => setShowNew(true)} className="text-brand-600 hover:underline">
                        Create the first one.
                      </button>
                    )}
                  </td>
                </tr>
              ) : (
                jobs.map((job) => (
                  <JobRow
                    key={job.id}
                    job={job}
                    canStop={perms.canTriggerGeneration}
                    onStop={(jobId) => cancelMutation.mutate(jobId)}
                    isStopping={stoppingJobId === job.id && cancelMutation.isPending}
                  />
                ))
              )}
            </tbody>
          </table>

          {total > PAGE_SIZE && (
            <div className="px-4 py-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
              <span>Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total}</span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1.5 border border-slate-200 disabled:opacity-40 hover:bg-slate-50 transition-colors"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={!data?.has_next}
                  className="px-3 py-1.5 border border-slate-200 disabled:opacity-40 hover:bg-slate-50 transition-colors"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* New Job Modal */}
      {showNew && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white w-full max-w-md border border-slate-200 shadow-xl">
            <div className="px-6 py-4 border-b border-slate-100">
              <h2 className="font-display font-semibold text-slate-900">New AI Generation Job</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Logs an AIDecision record and queues the job. Output requires review before use.
              </p>
            </div>
            <div className="px-6 py-5 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Study ID <span className="text-red-500">*</span></label>
                <input
                  type="text"
                  value={form.study_id}
                  onChange={(e) => setForm((f) => ({ ...f, study_id: e.target.value }))}
                  placeholder="UUID"
                  className="w-full border border-slate-200 px-3 py-2 text-sm font-mono focus:outline-none focus:border-brand-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Document Type <span className="text-red-500">*</span></label>
                <select
                  value={form.artifact_type}
                  onChange={(e) => setForm((f) => ({ ...f, artifact_type: e.target.value as ArtifactType }))}
                  className="w-full border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:border-brand-500 bg-white"
                >
                  {ARTIFACT_TYPES.map((t) => (
                    <option key={t} value={t}>{ARTIFACT_TYPE_LABELS[t] ?? t}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Model</label>
                <select
                  value={form.model_id}
                  onChange={(e) => setForm((f) => ({ ...f, model_id: e.target.value }))}
                  className="w-full border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:border-brand-500 bg-white"
                >
                  <option value="claude-sonnet-4-6">Claude Sonnet 4.6</option>
                  <option value="claude-opus-4-7">Claude Opus 4.7</option>
                  <option value="claude-haiku-4-5-20251001">Claude Haiku 4.5</option>
                </select>
              </div>
              {jobError && (
                <div className="bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2">{jobError}</div>
              )}
            </div>
            <div className="px-6 py-4 border-t border-slate-100 flex gap-3">
              <button
                onClick={() => createMutation.mutate()}
                disabled={createMutation.isPending || !form.study_id.trim()}
                className="text-sm font-semibold px-5 py-2 bg-brand-600 text-white hover:bg-brand-500 disabled:opacity-50 transition-colors"
              >
                {createMutation.isPending ? "Creating…" : "Create Job"}
              </button>
              <button
                onClick={() => setShowNew(false)}
                className="text-slate-500 hover:text-slate-700 text-sm transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
