"use client";

import { useState } from "react";
import { getApiErrorMessage } from "@/lib/api/errors";
import type { Artifact } from "@/types";

interface StudyPermissions {
  canSubmitArtifact: boolean;
  canApproveArtifact: boolean;
  canRejectArtifact: boolean;
}

interface SDTMApprovalActionsProps {
  artifact: Artifact;
  permissions: StudyPermissions;
  onSubmit: () => Promise<unknown>;
  onApprove: (comments?: string) => Promise<unknown>;
  onReject: (comments: string) => Promise<unknown>;
  isSubmitting: boolean;
  isRecordingApproval: boolean;
}

function ActionButton({
  label,
  variant = "default",
  onClick,
  disabled,
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
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`text-sm font-medium px-4 py-2 transition-colors disabled:opacity-50 ${cls}`}
    >
      {label}
    </button>
  );
}

export function SDTMApprovalActions({
  artifact,
  permissions,
  onSubmit,
  onApprove,
  onReject,
  isSubmitting,
  isRecordingApproval,
}: SDTMApprovalActionsProps) {
  const [modal, setModal] = useState<"approve" | "reject" | null>(null);
  const [comments, setComments] = useState("");
  const [error, setError] = useState<string | null>(null);

  const showSubmit =
    artifact.status === "DRAFT" && permissions.canSubmitArtifact;
  const showReviewActions =
    artifact.status === "IN_REVIEW" &&
    (permissions.canApproveArtifact || permissions.canRejectArtifact);

  if (!showSubmit && !showReviewActions) {
    return (
      <div className="border border-slate-200 bg-white px-5 py-4">
        <h2 className="font-display font-semibold text-slate-900 text-sm mb-1">
          Review Actions
        </h2>
        <p className="text-xs text-slate-500">
          No actions available for status {artifact.status.replace("_", " ")} with your role.
        </p>
      </div>
    );
  }

  async function handleSubmit() {
    setError(null);
    try {
      await onSubmit();
    } catch (err) {
      setError(getApiErrorMessage(err, "Submit failed."));
    }
  }

  async function handleDecision() {
    setError(null);
    try {
      if (modal === "approve") {
        await onApprove(comments.trim() || undefined);
      } else if (modal === "reject") {
        if (!comments.trim()) {
          setError("A rejection comment is required.");
          return;
        }
        await onReject(comments.trim());
      }
      setModal(null);
      setComments("");
    } catch (err) {
      setError(getApiErrorMessage(err, "Approval action failed."));
    }
  }

  return (
    <>
      <div className="border border-slate-200 bg-white px-5 py-4">
        <h2 className="font-display font-semibold text-slate-900 text-sm mb-3">
          Review Actions
        </h2>
        {error ? (
          <div className="mb-3 bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2">
            {error}
          </div>
        ) : null}
        <div className="flex flex-wrap gap-2">
          {showSubmit ? (
            <ActionButton
              label={isSubmitting ? "Submitting…" : "Submit for Review"}
              variant="primary"
              onClick={handleSubmit}
              disabled={isSubmitting}
            />
          ) : null}
          {showReviewActions && permissions.canApproveArtifact ? (
            <ActionButton
              label="Approve"
              variant="primary"
              onClick={() => {
                setError(null);
                setComments("");
                setModal("approve");
              }}
              disabled={isRecordingApproval}
            />
          ) : null}
          {showReviewActions && permissions.canRejectArtifact ? (
            <ActionButton
              label="Reject"
              variant="danger"
              onClick={() => {
                setError(null);
                setComments("");
                setModal("reject");
              }}
              disabled={isRecordingApproval}
            />
          ) : null}
        </div>
      </div>

      {modal ? (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 px-4">
          <div className="bg-white w-full max-w-md border border-slate-200 shadow-xl">
            <div className="px-6 py-4 border-b border-slate-100">
              <h3 className="font-display font-semibold text-slate-900">
                {modal === "approve" ? "Approve SDTM Dataset" : "Reject SDTM Dataset"}
              </h3>
            </div>
            <div className="px-6 py-5 space-y-4">
              <p className="text-sm text-slate-600">
                {modal === "approve"
                  ? "Confirm approval of this SDTM dataset artifact."
                  : "Provide a reason for rejection. This will be recorded in the approval history."}
              </p>
              <textarea
                value={comments}
                onChange={(event) => setComments(event.target.value)}
                rows={4}
                placeholder={
                  modal === "reject"
                    ? "Rejection reason (required)"
                    : "Optional approval notes"
                }
                className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-brand-500 resize-none"
              />
              <div className="flex gap-3">
                <ActionButton
                  label={
                    isRecordingApproval
                      ? "Saving…"
                      : modal === "approve"
                        ? "Confirm Approve"
                        : "Confirm Reject"
                  }
                  variant={modal === "approve" ? "primary" : "danger"}
                  onClick={handleDecision}
                  disabled={isRecordingApproval}
                />
                <button
                  type="button"
                  onClick={() => {
                    setModal(null);
                    setComments("");
                    setError(null);
                  }}
                  className="text-sm text-slate-500 hover:text-slate-700 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

export function SDTMApprovalActionsSkeleton() {
  return (
    <div className="border border-slate-200 bg-white px-5 py-4">
      <div className="h-4 w-32 bg-slate-100 animate-pulse rounded-sm mb-3" />
      <div className="h-9 w-40 bg-slate-50 animate-pulse rounded-sm" />
    </div>
  );
}
