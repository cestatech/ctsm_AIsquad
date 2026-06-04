"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { usePermissions } from "@/hooks/usePermissions";
import { artifactsApi } from "@/lib/api/artifacts";
import { approvalsApi } from "@/lib/api/approvals";
import { commentsApi } from "@/lib/api/comments";
import type { Artifact, Comment } from "@/types";

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-slate-100 text-slate-600",
  IN_REVIEW: "bg-amber-100 text-amber-700",
  APPROVED: "bg-emerald-100 text-emerald-700",
  REJECTED: "bg-red-100 text-red-700",
  LOCKED: "bg-blue-100 text-blue-700",
  AMENDED: "bg-purple-100 text-purple-700",
  SUPERSEDED: "bg-slate-100 text-slate-500",
};

const TYPE_LABELS: Record<string, string> = {
  PROTOCOL: "Protocol", ICF: "ICF", SAP: "SAP", EDC_CRF: "eCRF",
  TRACEABILITY_MATRIX: "Traceability Matrix", SDTM_DATASET: "SDTM Dataset",
  ADAM_DATASET: "ADaM Dataset", TLF: "TLF", VALIDATION_REPORT: "Validation Report",
  CSR: "CSR", SUBMISSION_PACKAGE: "Submission Package", OTHER: "Other",
};

function ActionButton({
  label, variant = "default", onClick, disabled,
}: {
  label: string;
  variant?: "default" | "danger" | "primary";
  onClick: () => void;
  disabled?: boolean;
}) {
  const cls = {
    default: "border border-slate-200 text-slate-700 hover:border-slate-300 hover:bg-slate-50",
    danger: "border border-red-200 text-red-700 hover:border-red-300 hover:bg-red-50",
    primary: "bg-brand-600 text-white hover:bg-brand-500",
  }[variant];
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`text-sm font-medium px-4 py-2 transition-colors disabled:opacity-50 ${cls}`}
    >
      {label}
    </button>
  );
}

function CommentThread({ comment, token, artifactId, onRefetch }: {
  comment: Comment; token: string; artifactId: string; onRefetch: () => void;
}) {
  const [replyOpen, setReplyOpen] = useState(false);
  const [replyBody, setReplyBody] = useState("");

  const replyMutation = useMutation({
    mutationFn: () => commentsApi.create({ artifact_id: artifactId, parent_id: comment.id, body: replyBody.trim() }, token),
    onSuccess: () => { setReplyBody(""); setReplyOpen(false); onRefetch(); },
  });

  const resolveMutation = useMutation({
    mutationFn: () => commentsApi.resolve(comment.id, token),
    onSuccess: onRefetch,
  });

  return (
    <div className={`border-l-2 pl-4 ${comment.is_resolved ? "border-slate-100 opacity-60" : "border-brand-200"}`}>
      <div className="flex items-start justify-between gap-2 mb-1">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-slate-800">{comment.author?.full_name ?? "Unknown"}</span>
          <span className="text-[11px] text-slate-400">
            {new Date(comment.created_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
          </span>
          {comment.is_resolved && (
            <span className="text-[10px] px-1.5 py-0.5 bg-emerald-100 text-emerald-700 font-semibold">Resolved</span>
          )}
        </div>
        {!comment.is_resolved && (
          <div className="flex gap-2">
            <button
              onClick={() => setReplyOpen((v) => !v)}
              className="text-[11px] text-slate-400 hover:text-brand-600 transition-colors"
            >
              Reply
            </button>
            <button
              onClick={() => resolveMutation.mutate()}
              disabled={resolveMutation.isPending}
              className="text-[11px] text-slate-400 hover:text-emerald-600 transition-colors disabled:opacity-40"
            >
              Resolve
            </button>
          </div>
        )}
      </div>
      <p className="text-xs text-slate-700 leading-relaxed">{comment.body}</p>

      {/* Replies */}
      {comment.replies && comment.replies.length > 0 && (
        <div className="mt-3 space-y-3">
          {comment.replies.map((reply) => (
            <div key={reply.id} className="border-l-2 border-slate-100 pl-3">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-xs font-semibold text-slate-800">{reply.author?.full_name ?? "Unknown"}</span>
                <span className="text-[11px] text-slate-400">
                  {new Date(reply.created_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                </span>
              </div>
              <p className="text-xs text-slate-700 leading-relaxed">{reply.body}</p>
            </div>
          ))}
        </div>
      )}

      {replyOpen && (
        <div className="mt-2 space-y-2">
          <textarea
            value={replyBody}
            onChange={(e) => setReplyBody(e.target.value)}
            rows={2}
            placeholder="Write a reply…"
            className="w-full border border-slate-200 px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-brand-500 resize-none"
          />
          <div className="flex gap-2">
            <button
              onClick={() => replyMutation.mutate()}
              disabled={replyMutation.isPending || !replyBody.trim()}
              className="text-xs px-3 py-1.5 bg-brand-600 text-white font-medium hover:bg-brand-500 disabled:opacity-50 transition-colors"
            >
              {replyMutation.isPending ? "Posting…" : "Post Reply"}
            </button>
            <button onClick={() => setReplyOpen(false)} className="text-xs text-slate-400 hover:text-slate-600 transition-colors">
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ArtifactDetailPage({ params }: { params: { id: string; artifactId: string } }) {
  const { token, role } = useAuthStore();
  const perms = usePermissions(role);
  const queryClient = useQueryClient();
  const { id: studyId, artifactId } = params;

  const [approvalModal, setApprovalModal] = useState<"approve" | "reject" | null>(null);
  const [approvalComment, setApprovalComment] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [newComment, setNewComment] = useState("");

  const { data: artifact, isLoading } = useQuery({
    queryKey: ["artifact", artifactId, token],
    queryFn: () => artifactsApi.get(artifactId, token!),
    enabled: !!token,
  });

  const { data: commentsData, refetch: refetchComments } = useQuery({
    queryKey: ["comments", artifactId, token],
    queryFn: () => commentsApi.list({ artifact_id: artifactId }, token!),
    enabled: !!token && !!artifactId,
  });

  const postCommentMutation = useMutation({
    mutationFn: () => commentsApi.create({ artifact_id: artifactId, body: newComment.trim() }, token!),
    onSuccess: () => { setNewComment(""); refetchComments(); },
  });

  const submitMutation = useMutation({
    mutationFn: () => artifactsApi.submit(artifactId, token!),
    onSuccess: (updated) => {
      queryClient.setQueryData(["artifact", artifactId, token], updated);
      queryClient.invalidateQueries({ queryKey: ["artifacts", studyId] });
    },
    onError: (err) => setActionError(err instanceof Error ? err.message : "Action failed."),
  });

  const lockMutation = useMutation({
    mutationFn: () => artifactsApi.lock(artifactId, token!),
    onSuccess: (updated) => {
      queryClient.setQueryData(["artifact", artifactId, token], updated);
    },
    onError: (err) => setActionError(err instanceof Error ? err.message : "Action failed."),
  });

  const amendMutation = useMutation({
    mutationFn: () => artifactsApi.amend(artifactId, token!),
    onSuccess: (updated) => {
      queryClient.setQueryData(["artifact", artifactId, token], updated);
    },
    onError: (err) => setActionError(err instanceof Error ? err.message : "Action failed."),
  });

  const approvalMutation = useMutation({
    mutationFn: async (decision: "APPROVED" | "REJECTED") => {
      if (!artifact?.current_version_id) throw new Error("No current version.");
      return approvalsApi.create(
        { artifact_id: artifactId, artifact_version_id: artifact.current_version_id, decision, comments: approvalComment || undefined },
        token!
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["artifact", artifactId] });
      queryClient.invalidateQueries({ queryKey: ["artifacts", studyId] });
      setApprovalModal(null);
      setApprovalComment("");
    },
    onError: (err) => setActionError(err instanceof Error ? err.message : "Action failed."),
  });

  if (isLoading) {
    return <div className="px-8 py-16 text-center text-slate-400 text-sm">Loading artifact…</div>;
  }

  if (!artifact) {
    return <div className="px-8 py-16 text-center text-slate-400 text-sm">Artifact not found.</div>;
  }

  function renderActions(a: Artifact) {
    const actions: React.ReactNode[] = [];
    if (a.status === "DRAFT" && perms.canEditArtifact) {
      actions.push(
        <ActionButton key="edit" label="Edit" onClick={() => alert("Edit flow — content editor coming in a future release.")} />
      );
    }
    if (a.status === "DRAFT" && perms.canSubmitArtifact) {
      actions.push(
        <ActionButton
          key="submit" label="Submit for Review" variant="primary"
          onClick={() => { setActionError(null); submitMutation.mutate(); }}
          disabled={submitMutation.isPending}
        />
      );
    }
    if (a.status === "IN_REVIEW" && perms.canApproveArtifact) {
      actions.push(
        <ActionButton
          key="approve" label="Approve" variant="primary"
          onClick={() => { setApprovalModal("approve"); setActionError(null); }}
        />,
        <ActionButton
          key="reject" label="Reject" variant="danger"
          onClick={() => { setApprovalModal("reject"); setActionError(null); }}
        />
      );
    }
    if (a.status === "APPROVED" && perms.canLockArtifact) {
      actions.push(
        <ActionButton
          key="lock" label="Lock" variant="primary"
          onClick={() => { setActionError(null); lockMutation.mutate(); }}
          disabled={lockMutation.isPending}
        />
      );
    }
    if (a.status === "LOCKED" && perms.canAmendArtifact) {
      actions.push(
        <ActionButton
          key="amend" label="Amend"
          onClick={() => { setActionError(null); amendMutation.mutate(); }}
          disabled={amendMutation.isPending}
        />
      );
    }
    return actions;
  }

  return (
    <div>
      {/* Header */}
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <div className="flex items-center gap-2 mb-2">
          <Link href={`/studies/${studyId}/artifacts`} className="text-slate-400 hover:text-slate-700 text-sm transition-colors">
            ← Artifacts
          </Link>
        </div>
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-xs px-2 py-0.5 bg-slate-100 text-slate-600 font-medium">
                {TYPE_LABELS[artifact.artifact_type] ?? artifact.artifact_type}
              </span>
              <span className={`text-xs px-2 py-0.5 font-medium ${STATUS_COLORS[artifact.status]}`}>
                {artifact.status.replace("_", " ")}
              </span>
              <span className="text-xs font-mono text-slate-400">v{artifact.current_version_number}</span>
              {artifact.locked_at && (
                <span className="text-xs text-slate-400">
                  Locked {new Date(artifact.locked_at).toLocaleDateString()}
                </span>
              )}
            </div>
            <h1 className="font-display text-xl font-bold text-slate-900">{artifact.name}</h1>
            {artifact.description && (
              <p className="text-slate-500 text-sm mt-1">{artifact.description}</p>
            )}
          </div>
          <div className="flex gap-2 flex-shrink-0 ml-6">
            {renderActions(artifact)}
          </div>
        </div>
      </div>

      {actionError && (
        <div className="mx-8 mt-4 bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3">
          {actionError}
        </div>
      )}

      <div className="px-8 py-6 grid grid-cols-3 gap-6">
        {/* Main content */}
        <div className="col-span-2 space-y-4">
          {/* Content preview */}
          <div className="bg-white border border-slate-200">
            <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between">
              <h2 className="font-display font-semibold text-slate-900 text-sm">Content</h2>
              <span className="text-xs text-slate-400">JSON content preview</span>
            </div>
            <div className="p-5">
              <pre className="text-xs text-slate-600 bg-slate-50 p-4 overflow-auto max-h-64 font-mono border border-slate-100">
                {JSON.stringify(
                  {
                    title: artifact.name,
                    type: artifact.artifact_type,
                    status: artifact.status,
                    version: artifact.current_version_number,
                    note: "Content editor available in upcoming release. Upload files or trigger AI generation.",
                  },
                  null,
                  2
                )}
              </pre>
            </div>
          </div>

          {/* Tags */}
          {artifact.tags && artifact.tags.length > 0 && (
            <div className="bg-white border border-slate-200 px-5 py-4">
              <h2 className="font-display font-semibold text-slate-900 text-sm mb-3">Tags</h2>
              <div className="flex flex-wrap gap-1.5">
                {artifact.tags.map((tag) => (
                  <span key={tag} className="text-xs px-2.5 py-1 bg-slate-100 text-slate-600">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Metadata */}
          <div className="bg-white border border-slate-200 p-5">
            <h3 className="font-display font-semibold text-slate-900 text-sm mb-4">Details</h3>
            <dl className="space-y-3 text-xs">
              <div>
                <dt className="text-slate-400 mb-0.5">Created by</dt>
                <dd className="text-slate-700 font-medium font-mono text-[11px]">
                  {artifact.created_by_id.slice(0, 8)}…
                </dd>
              </div>
              <div>
                <dt className="text-slate-400 mb-0.5">Created</dt>
                <dd className="text-slate-700">{new Date(artifact.created_at).toLocaleDateString()}</dd>
              </div>
              <div>
                <dt className="text-slate-400 mb-0.5">Last updated</dt>
                <dd className="text-slate-700">{new Date(artifact.updated_at).toLocaleDateString()}</dd>
              </div>
              <div>
                <dt className="text-slate-400 mb-0.5">Current version</dt>
                <dd className="text-slate-700 font-mono">v{artifact.current_version_number}</dd>
              </div>
            </dl>
          </div>

          {/* Version history link */}
          <div className="bg-white border border-slate-200 p-5">
            <h3 className="font-display font-semibold text-slate-900 text-sm mb-3">Version History</h3>
            <p className="text-xs text-slate-500 mb-3">
              {artifact.current_version_number} version{artifact.current_version_number !== 1 ? "s" : ""}
            </p>
            <Link
              href={`/studies/${studyId}/artifacts/${artifactId}/versions`}
              className="text-xs text-brand-600 hover:text-brand-700 font-medium"
            >
              View full history →
            </Link>
          </div>

          {/* Workflow guide */}
          <div className="bg-slate-50 border border-slate-200 p-4">
            <h3 className="font-display font-semibold text-slate-700 text-xs mb-2 uppercase tracking-wide">Workflow</h3>
            <div className="space-y-1.5 text-xs text-slate-500">
              {["DRAFT", "IN_REVIEW", "APPROVED", "LOCKED"].map((s, i) => (
                <div key={s} className={`flex items-center gap-2 ${s === artifact.status ? "text-brand-700 font-semibold" : ""}`}>
                  <span className={`w-4 h-4 flex items-center justify-center text-[10px] font-bold ${s === artifact.status ? "bg-brand-600 text-white" : "bg-slate-200 text-slate-500"}`}>
                    {i + 1}
                  </span>
                  {s.replace("_", " ")}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Comments */}
      <div className="px-8 pb-8">
        <div className="bg-white border border-slate-200">
          <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between">
            <h2 className="font-display font-semibold text-slate-900 text-sm">
              Comments {commentsData && commentsData.total > 0 && (
                <span className="ml-1.5 text-xs text-slate-400 font-normal">({commentsData.total})</span>
              )}
            </h2>
          </div>
          <div className="p-5 space-y-4">
            {(commentsData?.items ?? []).length === 0 ? (
              <p className="text-xs text-slate-400">No comments yet. Be the first to leave a note.</p>
            ) : (
              (commentsData?.items ?? []).map((comment) => (
                <CommentThread
                  key={comment.id}
                  comment={comment}
                  token={token!}
                  artifactId={artifactId}
                  onRefetch={refetchComments}
                />
              ))
            )}
            <div className="pt-2 border-t border-slate-100 space-y-2">
              <textarea
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                rows={3}
                placeholder="Leave a comment…"
                className="w-full border border-slate-200 px-3 py-2 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-brand-500 resize-none"
              />
              <button
                onClick={() => postCommentMutation.mutate()}
                disabled={postCommentMutation.isPending || !newComment.trim()}
                className="text-xs px-4 py-2 bg-brand-600 text-white font-medium hover:bg-brand-500 disabled:opacity-50 transition-colors"
              >
                {postCommentMutation.isPending ? "Posting…" : "Post Comment"}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Approval / Rejection Modal */}
      {approvalModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white w-full max-w-md border border-slate-200 shadow-xl">
            <div className="px-6 py-4 border-b border-slate-100">
              <h2 className="font-display font-semibold text-slate-900">
                {approvalModal === "approve" ? "Approve Artifact" : "Reject Artifact"}
              </h2>
            </div>
            <div className="px-6 py-5 space-y-4">
              <p className="text-sm text-slate-600">
                You are about to{" "}
                <strong>{approvalModal === "approve" ? "approve" : "reject"}</strong>{" "}
                <strong>{artifact.name}</strong> (v{artifact.current_version_number}).
              </p>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">
                  {approvalModal === "reject" ? "Rejection reason (required)" : "Comments (optional)"}
                </label>
                <textarea
                  value={approvalComment}
                  onChange={(e) => setApprovalComment(e.target.value)}
                  rows={4}
                  placeholder={approvalModal === "approve" ? "Optional approval notes…" : "Describe what needs to be revised…"}
                  className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 resize-none"
                />
              </div>
              {actionError && (
                <div className="bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2">{actionError}</div>
              )}
            </div>
            <div className="px-6 py-4 border-t border-slate-100 flex gap-3">
              <button
                onClick={() => approvalMutation.mutate(approvalModal === "approve" ? "APPROVED" : "REJECTED")}
                disabled={approvalMutation.isPending || (approvalModal === "reject" && !approvalComment.trim())}
                className={`text-sm font-semibold font-display px-5 py-2 transition-colors disabled:opacity-50 ${
                  approvalModal === "approve"
                    ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                    : "bg-red-600 hover:bg-red-700 text-white"
                }`}
              >
                {approvalMutation.isPending
                  ? "Processing…"
                  : approvalModal === "approve"
                  ? "Confirm Approval"
                  : "Confirm Rejection"}
              </button>
              <button
                onClick={() => { setApprovalModal(null); setApprovalComment(""); setActionError(null); }}
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
