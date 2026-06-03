"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { useIntelligenceStudy } from "@/hooks/useIntelligenceStudy";
import { intelligenceApi } from "@/lib/api/intelligence";
import { StudyPicker } from "@/components/intelligence/StudyPicker";
import type { HumanOverride } from "@/types";

function rel(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const hrs = Math.floor(diff / 3_600_000);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

const OVERRIDE_TYPE_STYLES: Record<string, string> = {
  CORRECTION: "bg-red-100 text-red-700",
  REFINEMENT: "bg-amber-100 text-amber-700",
  UNIT_CORRECTION: "bg-blue-100 text-blue-700",
  ADDITION: "bg-emerald-100 text-emerald-700",
};

export default function HumanOverridesPage() {
  const { token } = useAuthStore();
  const { studyId } = useIntelligenceStudy();
  const [activeOverride, setActiveOverride] = useState<HumanOverride | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["human-overrides", studyId, token],
    queryFn: () =>
      intelligenceApi.listOverrides({ study_id: studyId! }, token!),
    enabled: !!token && !!studyId,
    staleTime: 30_000,
  });

  const overrides = data?.items ?? [];

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display text-xl font-bold text-slate-900">Human Overrides</h1>
            <p className="text-slate-500 text-sm mt-0.5">
              Immutable record of every human correction to AI-generated values.{" "}
              {data ? `${data.total} total.` : ""}
            </p>
          </div>
          <StudyPicker />
        </div>
      </div>

      <div className="px-8 py-6">
        <div className="bg-amber-50 border border-amber-200 px-4 py-2.5 mb-4 text-xs text-amber-800">
          Override records are append-only and cannot be modified or deleted. Each entry represents a
          permanent correction to the audit trail.
        </div>

        {!studyId ? (
          <div className="bg-white border border-slate-200 px-8 py-14 text-center">
            <p className="font-display font-semibold text-slate-900 mb-1">Select a study</p>
            <p className="text-slate-500 text-sm">Choose a study above to view its human overrides.</p>
          </div>
        ) : isLoading ? (
          <div className="text-center py-12 text-slate-400 text-sm">Loading overrides…</div>
        ) : overrides.length === 0 ? (
          <div className="bg-white border border-slate-200 px-8 py-14 text-center">
            <p className="font-display font-semibold text-slate-900 mb-1">No overrides recorded</p>
            <p className="text-slate-500 text-sm">No human corrections have been made to AI-generated values.</p>
          </div>
        ) : (
          <div className="bg-white border border-slate-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Context</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Field</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Type</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Actor</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">When</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {overrides.map((override) => (
                  <tr
                    key={override.id}
                    className="hover:bg-slate-50 transition-colors cursor-pointer"
                    onClick={() => setActiveOverride(override)}
                  >
                    <td className="px-4 py-3">
                      <p className="text-xs font-medium text-slate-700">{override.context_type}</p>
                      {override.ai_decision_id && (
                        <p className="text-[11px] text-slate-400 font-mono">
                          AI: {override.ai_decision_id.slice(0, 8)}…
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <code className="text-[11px] text-slate-700 bg-slate-100 px-1.5 py-0.5">
                        {override.field_path ?? "—"}
                      </code>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-xs px-2 py-0.5 font-semibold ${
                          OVERRIDE_TYPE_STYLES[override.override_type] ?? "bg-slate-100 text-slate-700"
                        }`}
                      >
                        {override.override_type}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500 font-mono">
                      {override.actor_user_id.slice(0, 8)}…
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-400">{rel(override.created_at)}</td>
                    <td className="px-4 py-3">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveOverride(override);
                        }}
                        className="text-xs text-brand-600 hover:text-brand-700 font-medium"
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {activeOverride && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white w-full max-w-xl border border-slate-200 shadow-xl max-h-[85vh] overflow-y-auto">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h2 className="font-display font-semibold text-slate-900">Override Record</h2>
                <p className="text-xs text-slate-400 font-mono mt-0.5">{activeOverride.id}</p>
              </div>
              <span
                className={`text-xs px-2 py-1 font-semibold ${
                  OVERRIDE_TYPE_STYLES[activeOverride.override_type] ?? "bg-slate-100 text-slate-700"
                }`}
              >
                {activeOverride.override_type}
              </span>
            </div>

            <div className="px-6 py-5 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                {[
                  ["Context Type", activeOverride.context_type],
                  ["Field Path", activeOverride.field_path ?? "—"],
                  ["Actor ID", activeOverride.actor_user_id],
                  ["Created", new Date(activeOverride.created_at).toLocaleString()],
                ].map(([label, value]) => (
                  <div key={label} className="bg-slate-50 px-3 py-2 border border-slate-100">
                    <p className="text-[11px] text-slate-400 uppercase tracking-wide mb-0.5">{label}</p>
                    <p className="text-xs font-medium text-slate-800 font-mono break-all">{value as string}</p>
                  </div>
                ))}
              </div>

              <div>
                <p className="text-xs font-semibold text-slate-700 mb-2">Justification</p>
                <p className="text-xs text-slate-600 bg-amber-50 border border-amber-100 px-3 py-2.5 leading-relaxed">
                  {activeOverride.reason}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs font-semibold text-slate-700 mb-1.5 flex items-center gap-1">
                    <span className="w-2 h-2 bg-red-400 rounded-full inline-block" />
                    Original Value
                  </p>
                  <pre className="text-[11px] text-slate-600 bg-red-50 border border-red-100 px-3 py-2 font-mono leading-relaxed overflow-x-auto">
                    {JSON.stringify(activeOverride.original_value, null, 2) ?? "null"}
                  </pre>
                </div>
                <div>
                  <p className="text-xs font-semibold text-slate-700 mb-1.5 flex items-center gap-1">
                    <span className="w-2 h-2 bg-emerald-400 rounded-full inline-block" />
                    New Value
                  </p>
                  <pre className="text-[11px] text-slate-600 bg-emerald-50 border border-emerald-100 px-3 py-2 font-mono leading-relaxed overflow-x-auto">
                    {JSON.stringify(activeOverride.new_value, null, 2) ?? "null"}
                  </pre>
                </div>
              </div>
            </div>

            <div className="px-6 py-4 border-t border-slate-100">
              <button
                onClick={() => setActiveOverride(null)}
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
