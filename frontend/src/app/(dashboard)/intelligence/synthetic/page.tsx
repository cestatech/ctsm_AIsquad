"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { useIntelligenceStudy } from "@/hooks/useIntelligenceStudy";
import { artifactsApi } from "@/lib/api/artifacts";
import { intelligenceApi, type SyntheticDataRunDetail } from "@/lib/api/intelligence";
import { getApiErrorMessage } from "@/lib/api/errors";
import { StudyPicker } from "@/components/intelligence/StudyPicker";
import type { SyntheticDataRun } from "@/types";

const STATUS_STYLES: Record<SyntheticDataRun["status"], string> = {
  PENDING: "bg-slate-100 text-slate-600",
  RUNNING: "bg-blue-100 text-blue-700",
  COMPLETED: "bg-emerald-100 text-emerald-700",
  FAILED: "bg-red-100 text-red-700",
};

function rel(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const hrs = Math.floor(diff / 3_600_000);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function SyntheticDataPage() {
  const { token } = useAuthStore();
  const { studyId } = useIntelligenceStudy();
  const queryClient = useQueryClient();
  const [activeRun, setActiveRun] = useState<SyntheticDataRunDetail | null>(null);
  const [targetN, setTargetN] = useState(50);
  const [randomSeed, setRandomSeed] = useState(42);
  const [runName, setRunName] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["synthetic-runs", studyId, token],
    queryFn: () =>
      intelligenceApi.listSyntheticRuns({ study_id: studyId! }, token!),
    enabled: !!token && !!studyId,
    staleTime: 30_000,
  });

  const { data: artifactsData } = useQuery({
    queryKey: ["artifacts", studyId, token],
    queryFn: () => artifactsApi.list({ study_id: studyId!, page_size: 50 }, token!),
    enabled: !!token && !!studyId,
  });

  const hasSap = (artifactsData?.items ?? []).some((a) => a.artifact_type === "SAP");

  const createMutation = useMutation({
    mutationFn: () =>
      intelligenceApi.createSyntheticRun(
        {
          study_id: studyId!,
          target_n: targetN,
          random_seed: randomSeed,
          run_name: runName.trim() || undefined,
        },
        token!
      ),
    onSuccess: (run) => {
      setCreateError(null);
      queryClient.invalidateQueries({ queryKey: ["synthetic-runs", studyId] });
      setActiveRun(run);
    },
    onError: (err) => {
      setCreateError(err instanceof Error ? err.message : "Failed to start synthetic run.");
    },
  });

  const detailMutation = useMutation({
    mutationFn: (runId: string) => intelligenceApi.getSyntheticRun(runId, token!),
    onSuccess: (run) => setActiveRun(run),
  });

  const runs = data?.items ?? [];

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display text-xl font-bold text-slate-900">Synthetic Data Runs</h1>
            <p className="text-slate-500 text-sm mt-0.5">
              Reproducible synthetic patient data exported as CSV. All output is labeled SYNTHETIC.
            </p>
          </div>
          <StudyPicker />
        </div>
      </div>

      <div className="px-8 py-6 space-y-4">
        <div className="bg-amber-50 border border-amber-200 px-4 py-2.5 text-xs text-amber-800 font-semibold">
          SYNTHETIC DATA — Not derived from real patients. Do not use in regulatory submissions without clearly labeled separation.
        </div>

        {studyId && !hasSap && artifactsData !== undefined && (
          <div className="bg-amber-50 border border-amber-200 px-5 py-4">
            <p className="text-sm font-semibold text-amber-900">SAP required</p>
            <p className="text-xs text-amber-800 mt-1">
              Synthetic data is generated from the Statistical Analysis Plan. Generate a SAP
              artifact on the study workspace before starting a synthetic run.
            </p>
          </div>
        )}

        {studyId && hasSap && (
          <div className="bg-white border border-slate-200 px-5 py-4">
            <h2 className="text-sm font-semibold text-slate-900 mb-3">Start new synthetic run</h2>
            <p className="text-xs text-slate-500 mb-3">
              Uses the study SAP as the primary input. Protocol and EDC artifacts are included when available.
            </p>
            <div className="flex flex-wrap items-end gap-4">
              <div>
                <label className="block text-[11px] text-slate-500 mb-1">Sample size (N)</label>
                <input
                  type="number"
                  min={1}
                  max={10000}
                  value={targetN}
                  onChange={(e) => setTargetN(Number(e.target.value))}
                  className="w-28 text-sm border border-slate-200 px-2 py-1.5 rounded-sm"
                />
              </div>
              <div>
                <label className="block text-[11px] text-slate-500 mb-1">Random seed</label>
                <input
                  type="number"
                  min={0}
                  value={randomSeed}
                  onChange={(e) => setRandomSeed(Number(e.target.value))}
                  className="w-28 text-sm border border-slate-200 px-2 py-1.5 rounded-sm"
                />
              </div>
              <div className="flex-1 min-w-[200px]">
                <label className="block text-[11px] text-slate-500 mb-1">Run name (optional)</label>
                <input
                  type="text"
                  value={runName}
                  onChange={(e) => setRunName(e.target.value)}
                  placeholder="e.g. Dev cohort v1"
                  className="w-full text-sm border border-slate-200 px-2 py-1.5 rounded-sm"
                />
              </div>
              <button
                type="button"
                onClick={() => createMutation.mutate()}
                disabled={createMutation.isPending}
                className="bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white text-xs font-semibold px-4 py-2 rounded-sm"
              >
                {createMutation.isPending ? "Generating…" : "Generate synthetic data"}
              </button>
            </div>
            {createError && (
              <p className="text-xs text-red-600 mt-2">{createError}</p>
            )}
          </div>
        )}

        {!studyId ? (
          <div className="bg-white border border-slate-200 px-8 py-14 text-center">
            <p className="font-display font-semibold text-slate-900 mb-1">Select a study</p>
            <p className="text-slate-500 text-sm">Choose a study above to view or create synthetic data runs.</p>
          </div>
        ) : isLoading ? (
          <div className="text-center py-12 text-slate-400 text-sm">Loading synthetic runs…</div>
        ) : runs.length === 0 ? (
          <div className="bg-white border border-slate-200 px-8 py-14 text-center">
            <p className="font-display font-semibold text-slate-900 mb-1">No synthetic runs</p>
            <p className="text-slate-500 text-sm">Start a run above to generate labeled synthetic patient data.</p>
          </div>
        ) : (
          <div className="bg-white border border-slate-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Run Name</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Target N</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Records</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Seed</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Created</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {runs.map((run) => (
                  <tr key={run.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3">
                      <p className="font-medium text-slate-900 text-xs leading-snug">{run.run_name}</p>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-600">{run.target_n ?? "—"}</td>
                    <td className="px-4 py-3 text-xs font-mono font-semibold text-slate-700">
                      {run.records_generated?.toLocaleString() ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-xs font-mono text-slate-500">{run.random_seed ?? "—"}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 font-semibold ${STATUS_STYLES[run.status]}`}>
                        {run.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-400">{rel(run.created_at)}</td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => detailMutation.mutate(run.id)}
                        className="text-xs text-brand-600 hover:text-brand-700 font-medium"
                      >
                        Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {activeRun && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white w-full max-w-2xl border border-slate-200 shadow-xl max-h-[85vh] overflow-y-auto">
            <div className="px-6 py-4 border-b border-slate-100">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs px-2 py-0.5 bg-amber-100 text-amber-700 font-semibold">SYNTHETIC</span>
                <span className={`text-xs px-2 py-0.5 font-semibold ${STATUS_STYLES[activeRun.status]}`}>
                  {activeRun.status}
                </span>
              </div>
              <h2 className="font-display font-semibold text-slate-900">{activeRun.run_name}</h2>
            </div>

            <div className="px-6 py-5 space-y-4">
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div><span className="text-slate-400">Target N:</span> {activeRun.target_n}</div>
                <div><span className="text-slate-400">Seed:</span> {activeRun.random_seed}</div>
                <div><span className="text-slate-400">Records:</span> {activeRun.records_generated ?? "—"}</div>
              </div>

              {activeRun.assumptions?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-700 mb-2">Simulation assumptions</p>
                  <div className="space-y-2">
                    {activeRun.assumptions.map((a) => (
                      <div key={a.id} className="bg-slate-50 border border-slate-100 px-3 py-2 text-xs">
                        <p className="font-medium text-slate-800">{a.assumption_type}</p>
                        <p className="text-slate-600 mt-0.5">{a.description}</p>
                        {a.rationale && <p className="text-slate-400 mt-1 italic">{a.rationale}</p>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {"inputs_used" in activeRun.configuration && (
                <div>
                  <p className="text-xs font-semibold text-slate-700 mb-1">Inputs used</p>
                  <pre className="text-[11px] bg-slate-50 border border-slate-100 px-3 py-2 font-mono">
                    {JSON.stringify(activeRun.configuration.inputs_used, null, 2)}
                  </pre>
                </div>
              )}

              {activeRun.output_artifact_id && (
                <div className="flex flex-wrap items-center gap-4">
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        const { blob, filename } = await artifactsApi.downloadCsv(
                          activeRun.output_artifact_id!,
                          token!
                        );
                        const url = URL.createObjectURL(blob);
                        const link = document.createElement("a");
                        link.href = url;
                        link.download = filename;
                        link.click();
                        URL.revokeObjectURL(url);
                      } catch (err) {
                        setCreateError(getApiErrorMessage(err, "CSV download failed."));
                      }
                    }}
                    className="text-xs text-brand-600 hover:text-brand-700 font-semibold"
                  >
                    Download CSV →
                  </button>
                  <a
                    href={`/studies/${activeRun.study_id}/artifacts/${activeRun.output_artifact_id}`}
                    className="text-xs text-slate-500 hover:text-slate-700 font-medium"
                  >
                    Open artifact
                  </a>
                </div>
              )}
            </div>

            <div className="px-6 py-4 border-t border-slate-100 flex justify-end">
              <button
                type="button"
                onClick={() => setActiveRun(null)}
                className="text-slate-500 hover:text-slate-700 text-sm"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
