"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { useStudyPermissions } from "@/hooks/useStudyPermissions";
import { approvalsApi } from "@/lib/api/approvals";
import type { ApprovalQueueItem } from "@/types";

const TYPE_LABELS: Record<string, string> = {
  PROTOCOL: "Protocol", ICF: "ICF", SAP: "SAP", EDC_CRF: "eCRF",
  TRACEABILITY_MATRIX: "Traceability", SDTM_DATASET: "SDTM",
  ADAM_DATASET: "ADaM", TLF: "TLF", VALIDATION_REPORT: "Validation",
  CSR: "CSR", SUBMISSION_PACKAGE: "Submission", OTHER: "Other",
};

function rel(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const hrs = Math.floor(diff / 3_600_000);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function ApprovalQueueRow({
  item,
  onReview,
}: {
  item: ApprovalQueueItem;
  onReview: (item: ApprovalQueueItem) => void;
}) {
  const perms = useStudyPermissions(item.study_id);

  return (
    <tr className="hover:bg-slate-50 transition-colors">
      <td className="px-4 py-3">
        <Link
          href={`/studies/${item.study_id}/artifacts/${item.artifact_id}`}
          className="font-medium text-slate-900 text-xs leading-snug hover:text-brand-700"
        >
          {item.artifact_name}
        </Link>
      </td>
      <td className="px-4 py-3">
        <Link
          href={`/studies/${item.study_id}`}
          className="text-slate-600 hover:text-brand-700 transition-colors"
        >
          {item.study_name}
        </Link>
        <p className="text-[11px] text-slate-400 font-mono mt-0.5">{item.protocol_number}</p>
      </td>
      <td className="px-4 py-3">
        <span className="text-xs px-2 py-0.5 bg-amber-100 text-amber-700 font-medium">
          {TYPE_LABELS[item.artifact_type] ?? item.artifact_type}
        </span>
      </td>
      <td className="px-4 py-3 text-xs font-mono text-slate-500">v{item.version_number}</td>
      <td className="px-4 py-3 text-xs text-slate-600">{item.submitted_by.full_name}</td>
      <td className="px-4 py-3 text-xs text-slate-400">{rel(item.submitted_at)}</td>
      <td className="px-4 py-3">
        {perms.canApproveArtifact ? (
          <button
            onClick={() => onReview(item)}
            className="text-xs bg-brand-600 hover:bg-brand-500 text-white font-semibold px-3 py-1.5 transition-colors"
          >
            Review
          </button>
        ) : (
          <span className="text-[11px] text-slate-400">No study reviewer role</span>
        )}
      </td>
    </tr>
  );
}

export default function ApprovalsPage() {
  const { token } = useAuthStore();
  const queryClient = useQueryClient();

  const [activeItem, setActiveItem] = useState<ApprovalQueueItem | null>(null);
  const [decision, setDecision] = useState<"APPROVED" | "REJECTED" | null>(null);
  const [comment, setComment] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const activePerms = useStudyPermissions(activeItem?.study_id);

  const { data, isLoading } = useQuery({
    queryKey: ["approvals-queue", token],
    queryFn: () => approvalsApi.queue({ page_size: 50 }, token!),
    enabled: !!token,
    staleTime: 30_000,
  });

  const reviewMutation = useMutation({
    mutationFn: async ({
      item,
      dec,
    }: {
      item: ApprovalQueueItem;
      dec: "APPROVED" | "REJECTED";
    }) =>
      approvalsApi.create(
        {
          artifact_id: item.artifact_id,
          artifact_version_id: item.artifact_version_id!,
          decision: dec,
          comments: comment || undefined,
        },
        token!
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["approvals-queue"] });
      setActiveItem(null);
      setDecision(null);
      setComment("");
      setActionError(null);
    },
    onError: (err) => {
      setActionError(err instanceof Error ? err.message : "Action failed.");
    },
  });

  const pendingItems = data?.items ?? [];

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <h1 className="font-display text-xl font-bold text-slate-900">Approval Queue</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          {isLoading ? "Loading…" : `${data?.total ?? 0} artifact${(data?.total ?? 0) !== 1 ? "s" : ""} awaiting your review`}
        </p>
      </div>

      {actionError && (
        <div className="mx-8 mt-4 bg-red-50 border border-red-200 text-red-800 text-sm px-4 py-3">
          {actionError}
        </div>
      )}

      <div className="px-8 py-6">
        {isLoading ? (
          <div className="text-center py-12 text-slate-400 text-sm">Loading approval queue…</div>
        ) : pendingItems.length === 0 ? (
          <div className="bg-white border border-slate-200 px-8 py-14 text-center">
            <p className="font-display font-semibold text-slate-900 mb-1">Queue is clear</p>
            <p className="text-slate-500 text-sm">All submitted artifacts have been reviewed.</p>
          </div>
        ) : (
          <div className="bg-white border border-slate-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Artifact</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Study</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Type</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Version</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Submitted By</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Submitted</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {pendingItems.map((item) => (
                  <ApprovalQueueRow
                    key={item.artifact_id}
                    item={item}
                    onReview={(selected) => {
                      setActiveItem(selected);
                      setDecision(null);
                      setComment("");
                      setActionError(null);
                    }}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Review Modal */}
      {activeItem && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white w-full max-w-lg border border-slate-200 shadow-xl">
            <div className="px-6 py-4 border-b border-slate-100">
              <h2 className="font-display font-semibold text-slate-900">Review Artifact</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                {activeItem.artifact_name} · v{activeItem.version_number}
              </p>
            </div>

            <div className="px-6 py-5 space-y-4">
              <div className="bg-slate-50 border border-slate-200 px-4 py-3 text-xs space-y-1.5 text-slate-600">
                {[
                  ["Study", activeItem.study_name],
                  ["Protocol", activeItem.protocol_number],
                  ["Type", TYPE_LABELS[activeItem.artifact_type] ?? activeItem.artifact_type],
                  ["Submitted by", activeItem.submitted_by.full_name],
                  ["Submitted", new Date(activeItem.submitted_at).toLocaleString()],
                ].map(([label, value]) => (
                  <div key={label} className="flex justify-between">
                    <span className="text-slate-400">{label}</span>
                    <span className={label === "Protocol" ? "font-mono" : "font-medium"}>{value}</span>
                  </div>
                ))}
              </div>

              <Link
                href={`/studies/${activeItem.study_id}/artifacts/${activeItem.artifact_id}`}
                target="_blank"
                className="block text-xs text-brand-600 hover:text-brand-700 font-medium"
              >
                Open artifact for review ↗
              </Link>

              <div>
                <p className="text-xs font-medium text-slate-700 mb-2">Decision</p>
                <div className="flex gap-2">
                  {(["APPROVED", "REJECTED"] as const).map((dec) => (
                    <button
                      key={dec}
                      onClick={() => setDecision(dec)}
                      className={`flex-1 py-2 text-sm font-semibold font-display border-2 transition-colors ${
                        decision === dec
                          ? dec === "APPROVED"
                            ? "bg-emerald-600 border-emerald-600 text-white"
                            : "bg-red-600 border-red-600 text-white"
                          : "bg-white border-slate-200 text-slate-600 hover:border-brand-400"
                      }`}
                    >
                      {dec === "APPROVED" ? "Approve" : "Reject"}
                    </button>
                  ))}
                </div>
              </div>

              {decision && (
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1.5">
                    {decision === "REJECTED" ? "Rejection reason (required)" : "Comments (optional)"}
                  </label>
                  <textarea
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    rows={3}
                    placeholder={
                      decision === "APPROVED"
                        ? "Optional notes for the record…"
                        : "Describe what needs to be revised…"
                    }
                    className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 resize-none"
                  />
                </div>
              )}

              {actionError && (
                <div className="bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2">{actionError}</div>
              )}
            </div>

            <div className="px-6 py-4 border-t border-slate-100 flex gap-3">
              <button
                onClick={() => {
                  if (decision && activeItem) {
                    reviewMutation.mutate({ item: activeItem, dec: decision });
                  }
                }}
                disabled={
                  !decision ||
                  !activePerms.canApproveArtifact ||
                  reviewMutation.isPending ||
                  (decision === "REJECTED" && !comment.trim())
                }
                className={`text-sm font-semibold font-display px-5 py-2 transition-colors disabled:opacity-50 ${
                  decision === "APPROVED"
                    ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                    : decision === "REJECTED"
                    ? "bg-red-600 hover:bg-red-700 text-white"
                    : "bg-slate-200 text-slate-400 cursor-not-allowed"
                }`}
              >
                {reviewMutation.isPending ? "Submitting…" : "Submit Decision"}
              </button>
              <button
                onClick={() => {
                  setActiveItem(null);
                  setDecision(null);
                  setComment("");
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
