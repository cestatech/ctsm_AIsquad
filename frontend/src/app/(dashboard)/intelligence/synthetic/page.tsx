"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { useIntelligenceStudy } from "@/hooks/useIntelligenceStudy";
import { intelligenceApi } from "@/lib/api/intelligence";
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
  const [activeRun, setActiveRun] = useState<SyntheticDataRun | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["synthetic-runs", studyId, token],
    queryFn: () =>
      intelligenceApi.listSyntheticRuns({ study_id: studyId! }, token!),
    enabled: !!token && !!studyId,
    staleTime: 30_000,
  });

  const runs = data?.items ?? [];

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display text-xl font-bold text-slate-900">Synthetic Data Runs</h1>
            <p className="text-slate-500 text-sm mt-0.5">
              Reproducible synthetic patient data for development and validation. All output is labeled SYNTHETIC.
            </p>
          </div>
          <StudyPicker />
        </div>
      </div>

      <div className="px-8 py-6">
        <div className="bg-amber-50 border border-amber-200 px-4 py-2.5 mb-4 text-xs text-amber-800 font-semibold">
          SYNTHETIC DATA — Not derived from real patients. Do not use in regulatory submissions without clearly labeled separation.
        </div>

        {!studyId ? (
          <div className="bg-white border border-slate-200 px-8 py-14 text-center">
            <p className="font-display font-semibold text-slate-900 mb-1">Select a study</p>
            <p className="text-slate-500 text-sm">Choose a study above to view its synthetic data runs.</p>
          </div>
        ) : isLoading ? (
          <div className="text-center py-12 text-slate-400 text-sm">Loading synthetic runs…</div>
        ) : runs.length === 0 ? (
          <div className="bg-white border border-slate-200 px-8 py-14 text-center">
            <p className="font-display font-semibold text-slate-900 mb-1">No synthetic runs</p>
            <p className="text-slate-500 text-sm">No synthetic data generation runs have been created for this study.</p>
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
                  <tr
                    key={run.id}
                    className="hover:bg-slate-50 transition-colors cursor-pointer"
                    onClick={() => setActiveRun(run)}
                  >
                    <td className="px-4 py-3">
                      <p className="font-medium text-slate-900 text-xs leading-snug">{run.run_name}</p>
                      {run.description && (
                        <p className="text-[11px] text-slate-400 mt-0.5 max-w-xs truncate">
                          {run.description}
                        </p>
                      )}
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
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveRun(run);
                        }}
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

      {/* Run Detail Modal */}
      {activeRun && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white w-full max-w-xl border border-slate-200 shadow-xl max-h-[85vh] overflow-y-auto">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs px-2 py-0.5 bg-amber-100 text-amber-700 font-semibold">
                    SYNTHETIC
                  </span>
                  <span className={`text-xs px-2 py-0.5 font-semibold ${STATUS_STYLES[activeRun.status]}`}>
                    {activeRun.status}
                  </span>
                </div>
                <h2 className="font-display font-semibold text-slate-900">{activeRun.run_name}</h2>
              </div>
            </div>

            <div className="px-6 py-5 space-y-4">
              {activeRun.description && (
                <p className="text-xs text-slate-600 leading-relaxed">{activeRun.description}</p>
              )}

              <div className="grid grid-cols-2 gap-3">
                {[
                  ["Study ID", activeRun.study_id],
                  ["Target N", String(activeRun.target_n ?? "—")],
                  ["Records Generated", activeRun.records_generated?.toLocaleString() ?? "—"],
                  ["Random Seed", String(activeRun.random_seed ?? "—")],
                  ["Started", activeRun.started_at ? new Date(activeRun.started_at).toLocaleString() : "—"],
                  ["Completed", activeRun.completed_at ? new Date(activeRun.completed_at).toLocaleString() : "—"],
                ].map(([label, value]) => (
                  <div key={label} className="bg-slate-50 px-3 py-2 border border-slate-100">
                    <p className="text-[11px] text-slate-400 uppercase tracking-wide mb-0.5">{label}</p>
                    <p className="text-xs font-medium text-slate-800 font-mono">{value}</p>
                  </div>
                ))}
              </div>

              <div>
                <p className="text-xs font-semibold text-slate-700 mb-1.5">Configuration</p>
                <pre className="text-[11px] text-slate-600 bg-slate-50 border border-slate-100 px-3 py-2 overflow-x-auto font-mono leading-relaxed">
                  {JSON.stringify(activeRun.configuration, null, 2)}
                </pre>
              </div>

              {activeRun.error_message && (
                <div className="bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-700">
                  <strong>Error:</strong> {activeRun.error_message}
                </div>
              )}
            </div>

            <div className="px-6 py-4 border-t border-slate-100">
              <button
                onClick={() => setActiveRun(null)}
                className="text-slate-500 hover:text-slate-700 text-sm transition-colors"
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
