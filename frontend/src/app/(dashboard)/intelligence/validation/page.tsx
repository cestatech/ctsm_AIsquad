"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { usePermissions } from "@/hooks/usePermissions";
import { useIntelligenceStudy } from "@/hooks/useIntelligenceStudy";
import { intelligenceApi } from "@/lib/api/intelligence";
import { StudyPicker } from "@/components/intelligence/StudyPicker";
import type { ValidationEvidence, ValidationEvidenceStatus } from "@/types";

const STATUS_STYLES: Record<ValidationEvidenceStatus, string> = {
  PENDING: "bg-slate-100 text-slate-600",
  PASS: "bg-emerald-100 text-emerald-700",
  FAIL: "bg-red-100 text-red-700",
  WARNING: "bg-amber-100 text-amber-700",
  WAIVED: "bg-purple-100 text-purple-700",
};

const SEVERITY_STYLES: Record<string, string> = {
  ERROR: "text-red-600 font-semibold",
  WARNING: "text-amber-600",
};

export default function ValidationEvidencePage() {
  const { token, role } = useAuthStore();
  const perms = usePermissions(role);
  const queryClient = useQueryClient();
  const { studyId } = useIntelligenceStudy();

  const [statusFilter, setStatusFilter] = useState<ValidationEvidenceStatus | "ALL">("ALL");
  const [waiverTarget, setWaiverTarget] = useState<ValidationEvidence | null>(null);
  const [waiverReason, setWaiverReason] = useState("");

  const evidenceKey = ["validation-evidence", studyId, token];

  const { data, isLoading } = useQuery({
    queryKey: evidenceKey,
    queryFn: () =>
      intelligenceApi.listValidationEvidence({ study_id: studyId! }, token!),
    enabled: !!token && !!studyId,
    staleTime: 30_000,
  });

  const evidence = data?.items ?? [];

  const waiveMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      intelligenceApi.waiveFinding(id, { reason }, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: evidenceKey });
      queryClient.invalidateQueries({ queryKey: ["validation-evidence-hub"] });
      setWaiverTarget(null);
      setWaiverReason("");
    },
  });

  const filtered =
    statusFilter === "ALL"
      ? evidence
      : evidence.filter((e) => e.status === statusFilter);

  const counts = {
    FAIL: evidence.filter((e) => e.status === "FAIL").length,
    WARNING: evidence.filter((e) => e.status === "WARNING").length,
    PASS: evidence.filter((e) => e.status === "PASS").length,
    WAIVED: evidence.filter((e) => e.status === "WAIVED").length,
  };

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display text-xl font-bold text-slate-900">Validation Evidence</h1>
            <p className="text-slate-500 text-sm mt-0.5">
              CDISC conformance findings. {counts.FAIL} errors, {counts.WARNING} warnings, {counts.PASS} passing.
            </p>
          </div>
          <StudyPicker />
        </div>
      </div>

      {/* Summary bar */}
      <div className="px-8 pt-5 pb-2 flex gap-3">
        {([
          ["ALL", "All", evidence.length, "bg-slate-600"],
          ["FAIL", "Errors", counts.FAIL, "bg-red-600"],
          ["WARNING", "Warnings", counts.WARNING, "bg-amber-500"],
          ["PASS", "Passing", counts.PASS, "bg-emerald-600"],
          ["WAIVED", "Waived", counts.WAIVED, "bg-purple-600"],
        ] as const).map(([val, label, count, color]) => (
          <button
            key={val}
            onClick={() => setStatusFilter(val as ValidationEvidenceStatus | "ALL")}
            className={`flex items-center gap-2 px-3 py-2 border-2 text-xs font-semibold transition-all ${
              statusFilter === val
                ? `border-current text-white ${color}`
                : "border-slate-200 text-slate-600 bg-white hover:border-slate-300"
            }`}
          >
            <span
              className={`w-5 h-5 flex items-center justify-center text-[11px] font-bold ${
                statusFilter === val ? "text-white" : `text-white ${color}`
              }`}
              style={statusFilter !== val ? { background: "transparent" } : {}}
            >
              {count}
            </span>
            {label}
          </button>
        ))}
      </div>

      <div className="px-8 py-4">
        {!studyId ? (
          <div className="bg-white border border-slate-200 px-8 py-14 text-center">
            <p className="font-display font-semibold text-slate-900 mb-1">Select a study</p>
            <p className="text-slate-500 text-sm">Choose a study above to view validation evidence.</p>
          </div>
        ) : isLoading ? (
          <div className="text-center py-12 text-slate-400 text-sm">Loading validation evidence…</div>
        ) : filtered.length === 0 ? (
          <div className="bg-white border border-slate-200 px-8 py-14 text-center">
            <p className="font-display font-semibold text-slate-900 mb-1">No findings</p>
            <p className="text-slate-500 text-sm">No validation evidence matches the current filter.</p>
          </div>
        ) : (
          <div className="bg-white border border-slate-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Rule</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Field</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Standard</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Severity</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.map((ev) => (
                  <tr key={ev.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3">
                      <p className="text-xs font-medium text-slate-900">{ev.rule_name ?? "—"}</p>
                      <p className="text-[11px] text-slate-400 font-mono">{ev.rule_id}</p>
                    </td>
                    <td className="px-4 py-3">
                      <code className="text-[11px] text-slate-700 bg-slate-100 px-1.5 py-0.5">
                        {ev.subject_field ?? ev.subject_type}
                      </code>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500 font-mono">{ev.cdisc_standard ?? "—"}</td>
                    <td className="px-4 py-3">
                      {ev.finding_severity ? (
                        <span className={`text-xs ${SEVERITY_STYLES[ev.finding_severity] ?? "text-slate-600"}`}>
                          {ev.finding_severity}
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 font-semibold ${STATUS_STYLES[ev.status]}`}>
                        {ev.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {ev.status === "FAIL" && perms.canApproveArtifact && (
                        <button
                          onClick={() => {
                            setWaiverTarget(ev);
                            setWaiverReason("");
                          }}
                          className="text-xs border border-purple-300 text-purple-700 hover:bg-purple-50 px-2 py-1 transition-colors"
                        >
                          Waive
                        </button>
                      )}
                      {ev.status === "WAIVED" && (
                        <span className="text-[11px] text-slate-400 italic">
                          Waived {ev.waived_at ? new Date(ev.waived_at).toLocaleDateString() : ""}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Waiver Modal */}
      {waiverTarget && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white w-full max-w-lg border border-slate-200 shadow-xl">
            <div className="px-6 py-4 border-b border-slate-100">
              <h2 className="font-display font-semibold text-slate-900">Waive Finding</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                {waiverTarget.rule_id} — {waiverTarget.rule_name}
              </p>
            </div>

            <div className="px-6 py-5 space-y-4">
              {waiverTarget.finding_message && (
                <div className="bg-red-50 border border-red-100 px-3 py-2.5 text-xs text-red-700 leading-relaxed">
                  {waiverTarget.finding_message}
                </div>
              )}

              <div className="bg-amber-50 border border-amber-200 px-3 py-2.5 text-xs text-amber-800">
                Waivers are permanent and will be included in the regulatory submission package.
                A mandatory justification is required.
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">
                  Waiver Justification <span className="text-red-500">*</span>
                </label>
                <textarea
                  value={waiverReason}
                  onChange={(e) => setWaiverReason(e.target.value)}
                  rows={4}
                  placeholder="Provide a detailed scientific or operational justification for waiving this finding…"
                  className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 resize-none"
                />
              </div>
            </div>

            <div className="px-6 py-4 border-t border-slate-100 flex gap-3">
              <button
                disabled={!waiverReason.trim() || waiveMutation.isPending}
                onClick={() => waiveMutation.mutate({ id: waiverTarget.id, reason: waiverReason })}
                className="text-sm font-semibold font-display px-5 py-2 bg-purple-600 hover:bg-purple-700 text-white transition-colors disabled:opacity-50"
              >
                {waiveMutation.isPending ? "Submitting…" : "Submit Waiver"}
              </button>
              <button
                onClick={() => {
                  setWaiverTarget(null);
                  setWaiverReason("");
                }}
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
