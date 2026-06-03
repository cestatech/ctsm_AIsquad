"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { usePermissions } from "@/hooks/usePermissions";
import { useIntelligenceStudy } from "@/hooks/useIntelligenceStudy";
import { intelligenceApi } from "@/lib/api/intelligence";
import { StudyPicker } from "@/components/intelligence/StudyPicker";
import type { AIDecision, AIDecisionStatus } from "@/types";

const STATUS_STYLES: Record<AIDecisionStatus, string> = {
  PENDING_REVIEW: "bg-amber-100 text-amber-800",
  ACCEPTED: "bg-emerald-100 text-emerald-800",
  REJECTED: "bg-red-100 text-red-700",
  OVERRIDDEN: "bg-purple-100 text-purple-800",
};

function rel(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const hrs = Math.floor(diff / 3_600_000);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function ConfidenceBadge({ value }: { value: number | null }) {
  if (value === null) return <span className="text-slate-400 text-xs">—</span>;
  const pct = Math.round(value * 100);
  const color = pct >= 90 ? "text-emerald-700" : pct >= 75 ? "text-amber-700" : "text-red-700";
  return <span className={`text-xs font-mono font-semibold ${color}`}>{pct}%</span>;
}

export default function AIDecisionsPage() {
  const { token, role } = useAuthStore();
  const perms = usePermissions(role);
  const queryClient = useQueryClient();
  const { studyId } = useIntelligenceStudy();

  const [activeDecision, setActiveDecision] = useState<AIDecision | null>(null);
  const [rejectNotes, setRejectNotes] = useState("");
  const [acceptNotes, setAcceptNotes] = useState("");
  const [action, setAction] = useState<"accept" | "reject" | null>(null);
  const [statusFilter, setStatusFilter] = useState<AIDecisionStatus | "ALL">("ALL");

  const decisionsKey = ["ai-decisions", studyId, token];

  const { data, isLoading } = useQuery({
    queryKey: decisionsKey,
    queryFn: () =>
      intelligenceApi.listDecisions({ study_id: studyId! }, token!),
    enabled: !!token && !!studyId,
    staleTime: 30_000,
  });

  const decisions = data?.items ?? [];

  const acceptMutation = useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) =>
      intelligenceApi.acceptDecision(id, { notes }, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: decisionsKey });
      queryClient.invalidateQueries({ queryKey: ["pending-decisions"] });
      closeModal();
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, notes }: { id: string; notes: string }) =>
      intelligenceApi.rejectDecision(id, { notes }, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: decisionsKey });
      queryClient.invalidateQueries({ queryKey: ["pending-decisions"] });
      closeModal();
    },
  });

  function closeModal() {
    setActiveDecision(null);
    setAction(null);
    setRejectNotes("");
    setAcceptNotes("");
  }

  const filtered =
    statusFilter === "ALL"
      ? decisions
      : decisions.filter((d) => d.status === statusFilter);

  const pendingCount = decisions.filter((d) => d.status === "PENDING_REVIEW").length;

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display text-xl font-bold text-slate-900">AI Decisions</h1>
            <p className="text-slate-500 text-sm mt-0.5">
              Audit and review every AI-generated decision. {pendingCount} pending review.
            </p>
          </div>
          <div className="flex items-center gap-4">
            <StudyPicker />
            <div className="flex gap-2">
              {(["ALL", "PENDING_REVIEW", "ACCEPTED", "REJECTED"] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className={`text-xs px-3 py-1.5 border transition-colors ${
                    statusFilter === s
                      ? "bg-brand-600 border-brand-600 text-white"
                      : "bg-white border-slate-200 text-slate-600 hover:border-brand-400"
                  }`}
                >
                  {s === "ALL" ? "All" : s.replace("_", " ")}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="px-8 py-6">
        {!studyId ? (
          <div className="bg-white border border-slate-200 px-8 py-14 text-center">
            <p className="font-display font-semibold text-slate-900 mb-1">Select a study</p>
            <p className="text-slate-500 text-sm">Choose a study above to view its AI decisions.</p>
          </div>
        ) : isLoading ? (
          <div className="text-center py-12 text-slate-400 text-sm">Loading decisions…</div>
        ) : filtered.length === 0 ? (
          <div className="bg-white border border-slate-200 px-8 py-14 text-center">
            <p className="font-display font-semibold text-slate-900 mb-1">No decisions found</p>
            <p className="text-slate-500 text-sm">No AI decisions match the current filter.</p>
          </div>
        ) : (
          <div className="bg-white border border-slate-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Agent</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Decision Type</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Module</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Confidence</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Created</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.map((decision) => (
                  <tr
                    key={decision.id}
                    className="hover:bg-slate-50 transition-colors cursor-pointer"
                    onClick={() => setActiveDecision(decision)}
                  >
                    <td className="px-4 py-3">
                      <p className="font-medium text-slate-900 font-mono text-xs">{decision.agent_name}</p>
                      {decision.agent_version && (
                        <p className="text-slate-400 text-[11px]">v{decision.agent_version}</p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-700">{decision.decision_type}</td>
                    <td className="px-4 py-3">
                      <span className="text-xs px-2 py-0.5 bg-slate-100 text-slate-600 font-medium">
                        {decision.module ?? "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <ConfidenceBadge value={decision.confidence} />
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 font-semibold ${STATUS_STYLES[decision.status]}`}>
                        {decision.status.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-400">{rel(decision.created_at)}</td>
                    <td className="px-4 py-3">
                      {decision.status === "PENDING_REVIEW" && perms.canApproveArtifact && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setActiveDecision(decision);
                            setAction(null);
                          }}
                          className="text-xs bg-brand-600 hover:bg-brand-500 text-white font-semibold px-3 py-1.5 transition-colors"
                        >
                          Review
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Decision Detail / Review Modal */}
      {activeDecision && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white w-full max-w-2xl border border-slate-200 shadow-xl max-h-[90vh] overflow-y-auto">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h2 className="font-display font-semibold text-slate-900">AI Decision</h2>
                <p className="text-xs text-slate-400 font-mono mt-0.5">{activeDecision.id}</p>
              </div>
              <span className={`text-xs px-2 py-1 font-semibold ${STATUS_STYLES[activeDecision.status]}`}>
                {activeDecision.status.replace("_", " ")}
              </span>
            </div>

            <div className="px-6 py-5 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                {[
                  ["Agent", `${activeDecision.agent_name} v${activeDecision.agent_version ?? "?"}`],
                  ["Decision Type", activeDecision.decision_type],
                  ["Module", activeDecision.module ?? "—"],
                  ["Model", activeDecision.model_id ?? "—"],
                  ["Confidence", activeDecision.confidence !== null ? `${Math.round(activeDecision.confidence * 100)}%` : "—"],
                  ["Created", new Date(activeDecision.created_at).toLocaleString()],
                ].map(([label, value]) => (
                  <div key={label} className="bg-slate-50 px-3 py-2 border border-slate-100">
                    <p className="text-[11px] text-slate-400 uppercase tracking-wide mb-0.5">{label}</p>
                    <p className="text-xs font-medium text-slate-800 font-mono">{value}</p>
                  </div>
                ))}
              </div>

              {activeDecision.reasoning && (
                <div>
                  <p className="text-xs font-semibold text-slate-700 mb-1.5">Reasoning</p>
                  <p className="text-xs text-slate-600 bg-blue-50 border border-blue-100 px-3 py-2.5 leading-relaxed">
                    {activeDecision.reasoning}
                  </p>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs font-semibold text-slate-700 mb-1.5">Input Context</p>
                  <pre className="text-[11px] text-slate-600 bg-slate-50 border border-slate-100 px-3 py-2 overflow-x-auto font-mono leading-relaxed">
                    {JSON.stringify(activeDecision.input_context, null, 2)}
                  </pre>
                </div>
                <div>
                  <p className="text-xs font-semibold text-slate-700 mb-1.5">Output</p>
                  <pre className="text-[11px] text-slate-600 bg-slate-50 border border-slate-100 px-3 py-2 overflow-x-auto font-mono leading-relaxed">
                    {JSON.stringify(activeDecision.output, null, 2)}
                  </pre>
                </div>
              </div>

              {activeDecision.status === "PENDING_REVIEW" && perms.canApproveArtifact && (
                <div className="border-t border-slate-100 pt-4">
                  <p className="text-xs font-semibold text-slate-700 mb-3">Review Decision</p>
                  <div className="flex gap-2 mb-3">
                    {(["accept", "reject"] as const).map((a) => (
                      <button
                        key={a}
                        onClick={() => setAction(a)}
                        className={`flex-1 py-2 text-sm font-semibold font-display border-2 transition-colors ${
                          action === a
                            ? a === "accept"
                              ? "bg-emerald-600 border-emerald-600 text-white"
                              : "bg-red-600 border-red-600 text-white"
                            : "bg-white border-slate-200 text-slate-600 hover:border-brand-400"
                        }`}
                      >
                        {a === "accept" ? "Accept" : "Reject"}
                      </button>
                    ))}
                  </div>

                  {action === "accept" && (
                    <textarea
                      value={acceptNotes}
                      onChange={(e) => setAcceptNotes(e.target.value)}
                      rows={2}
                      placeholder="Optional review notes…"
                      className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-brand-500 resize-none"
                    />
                  )}
                  {action === "reject" && (
                    <textarea
                      value={rejectNotes}
                      onChange={(e) => setRejectNotes(e.target.value)}
                      rows={2}
                      placeholder="Rejection reason (required)…"
                      className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-brand-500 resize-none"
                    />
                  )}
                </div>
              )}

              {activeDecision.review_notes && (
                <div>
                  <p className="text-xs font-semibold text-slate-700 mb-1">Review Notes</p>
                  <p className="text-xs text-slate-600 italic">{activeDecision.review_notes}</p>
                </div>
              )}
            </div>

            <div className="px-6 py-4 border-t border-slate-100 flex gap-3">
              {activeDecision.status === "PENDING_REVIEW" &&
                perms.canApproveArtifact &&
                action && (
                  <button
                    disabled={
                      (action === "reject" && !rejectNotes.trim()) ||
                      acceptMutation.isPending ||
                      rejectMutation.isPending
                    }
                    onClick={() => {
                      if (action === "accept") {
                        acceptMutation.mutate({ id: activeDecision.id, notes: acceptNotes || undefined });
                      } else {
                        rejectMutation.mutate({ id: activeDecision.id, notes: rejectNotes });
                      }
                    }}
                    className={`text-sm font-semibold font-display px-5 py-2 transition-colors disabled:opacity-50 ${
                      action === "accept"
                        ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                        : "bg-red-600 hover:bg-red-700 text-white"
                    }`}
                  >
                    {acceptMutation.isPending || rejectMutation.isPending
                      ? "Submitting…"
                      : action === "accept"
                      ? "Confirm Accept"
                      : "Confirm Reject"}
                  </button>
                )}
              <button
                onClick={closeModal}
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
