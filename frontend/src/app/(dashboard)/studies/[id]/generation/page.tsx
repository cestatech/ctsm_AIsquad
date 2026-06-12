"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { useStudyPermissions } from "@/hooks/useStudyPermissions";
import { getApiErrorMessage } from "@/lib/api/errors";
import { generationApi } from "@/lib/api/generation";
import { studiesApi } from "@/lib/api/studies";
import { formatRelativeTime } from "@/lib/formatRelativeTime";
import {
  ACTIVE_GENERATION_STATUSES,
  GENERATION_ARTIFACT_TYPE_LABELS,
  GENERATION_STATUS_COLORS,
} from "@/lib/generationLabels";
import type { GenerationJob } from "@/types";

function JobRow({
  job,
  studyId,
  canStop,
  onStop,
  isStopping,
}: {
  job: GenerationJob;
  studyId: string;
  canStop: boolean;
  onStop: (jobId: string) => void;
  isStopping: boolean;
}) {
  const duration =
    job.started_at && job.completed_at
      ? `${Math.round((new Date(job.completed_at).getTime() - new Date(job.started_at).getTime()) / 1000)}s`
      : job.started_at
      ? "running…"
      : null;

  return (
    <tr className="hover:bg-slate-50 transition-colors">
      <td className="px-4 py-3 text-xs font-mono text-slate-500">{job.id.slice(0, 8)}…</td>
      <td className="px-4 py-3 text-sm text-slate-800">{GENERATION_ARTIFACT_TYPE_LABELS[job.artifact_type] ?? job.artifact_type}</td>
      <td className="px-4 py-3">
        <span className={`text-xs px-2 py-0.5 font-medium ${GENERATION_STATUS_COLORS[job.status] ?? "bg-slate-100 text-slate-600"}`}>
          {job.status}
        </span>
      </td>
      <td className="px-4 py-3 text-xs text-slate-500">{job.model_id}</td>
      <td className="px-4 py-3 text-xs text-slate-400">{duration ?? "—"}</td>
      <td className="px-4 py-3 text-xs text-slate-400">{formatRelativeTime(job.created_at)}</td>
      <td className="px-4 py-3 text-xs">
        <div className="flex items-center gap-3">
          {job.output_artifact_id ? (
            <Link
              href={`/studies/${studyId}/artifacts/${job.output_artifact_id}`}
              className="text-brand-600 hover:text-brand-700 font-medium"
            >
              View artifact →
            </Link>
          ) : job.status === "CANCELLED" ? (
            <span className="text-slate-500">Stopped</span>
          ) : job.error_message ? (
            <span className="text-red-600 truncate max-w-[160px] block" title={job.error_message}>
              {job.error_message.slice(0, 60)}{job.error_message.length > 60 ? "…" : ""}
            </span>
          ) : (
            <span className="text-slate-300">—</span>
          )}
          {canStop && ACTIVE_GENERATION_STATUSES.has(job.status) && (
            <button
              type="button"
              onClick={() => onStop(job.id)}
              disabled={isStopping}
              className="text-red-600 hover:text-red-700 font-medium disabled:opacity-50"
            >
              {isStopping ? "Stopping…" : "Stop"}
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

export default function StudyGenerationPage() {
  const params = useParams<{ id: string }>();
  const studyId = params.id;
  const { token } = useAuthStore();
  const perms = useStudyPermissions(params.id);
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);
  const [stoppingJobId, setStoppingJobId] = useState<string | null>(null);

  const { data: study } = useQuery({
    queryKey: ["study", studyId, token],
    queryFn: () => studiesApi.get(studyId, token!),
    enabled: !!token,
  });

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["generation-jobs", studyId, token],
    queryFn: () => generationApi.listJobs({ study_id: studyId, page_size: 50 }, token!),
    enabled: !!token,
    refetchInterval: (query) => {
      const jobs = query.state.data?.items ?? [];
      const hasActive = jobs.some((j) => j.status === "PENDING" || j.status === "RUNNING" || j.status === "QUEUED");
      return hasActive ? 5000 : false;
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (jobId: string) => generationApi.cancelJob(jobId, token!),
    onMutate: (jobId) => setStoppingJobId(jobId),
    onSuccess: () => {
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ["generation-jobs", studyId] });
    },
    onError: (err) =>
      setActionError(getApiErrorMessage(err, "Failed to stop generation.")),
    onSettled: () => setStoppingJobId(null),
  });

  const jobs = data?.items ?? [];

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link href={`/studies/${studyId}`} className="text-slate-400 hover:text-slate-700 text-sm transition-colors">
              ← {study?.short_name ?? study?.name ?? "Study"}
            </Link>
          </div>
          <h1 className="font-display text-xl font-bold text-slate-900">AI Generation</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            {data?.total ?? 0} generation job{data?.total !== 1 ? "s" : ""}
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            href={`/studies/${studyId}/intake`}
            className="text-sm border border-slate-200 text-slate-700 hover:bg-slate-50 px-4 py-2 transition-colors font-medium"
          >
            Go to Intake →
          </Link>
          <button
            onClick={() => refetch()}
            className="text-sm border border-slate-200 text-slate-600 hover:bg-slate-50 px-3 py-2 transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="px-8 py-6">
        {actionError && (
          <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2">
            {actionError}
          </div>
        )}
        <div className="bg-white border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Job ID</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Artifact Type</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Model</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Duration</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Triggered</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Output</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-slate-400 text-sm">Loading…</td>
                </tr>
              ) : jobs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center">
                    <p className="text-slate-400 text-sm mb-2">No generation jobs yet.</p>
                    <p className="text-xs text-slate-400">
                      Complete the{" "}
                      <Link href={`/studies/${studyId}/intake`} className="text-brand-600 hover:text-brand-700">
                        sponsor intake
                      </Link>{" "}
                      and compile the Study Brief to generate Protocol, ICF, and more.
                    </p>
                  </td>
                </tr>
              ) : (
                jobs.map((job) => (
                  <JobRow
                    key={job.id}
                    job={job}
                    studyId={studyId}
                    canStop={perms.canTriggerGeneration}
                    onStop={(jobId) => cancelMutation.mutate(jobId)}
                    isStopping={stoppingJobId === job.id && cancelMutation.isPending}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>

        {jobs.some((j) => ACTIVE_GENERATION_STATUSES.has(j.status)) && (
          <p className="text-xs text-slate-400 mt-3 text-center">
            Active jobs — page auto-refreshes every 5 seconds. Use Stop to cancel queued or running work.
          </p>
        )}
      </div>
    </div>
  );
}
