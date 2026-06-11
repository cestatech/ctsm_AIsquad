"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { rawDataApi } from "@/lib/api/rawData";
import { getApiErrorMessage } from "@/lib/api/errors";

interface BulkRejectDialogProps {
  open: boolean;
  datasetId: string;
  mappingIds: string[];
  token: string;
  onClose: () => void;
  onSuccess: () => void;
}

export function BulkRejectDialog({
  open,
  datasetId,
  mappingIds,
  token,
  onClose,
  onSuccess,
}: BulkRejectDialogProps) {
  const [reason, setReason] = useState("");

  const rejectMutation = useMutation({
    mutationFn: () =>
      rawDataApi.bulkRejectMappings(datasetId, mappingIds, reason.trim(), token),
    onSuccess: (data) => {
      onSuccess();
      onClose();
      setReason("");
      if (data.failed > 0) {
        window.alert(
          `Rejected ${data.rejected} mapping(s). ${data.failed} could not be rejected.`
        );
      }
    },
  });

  if (!open) {
    return null;
  }

  const canConfirm = reason.trim().length >= 10 && mappingIds.length > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4">
      <div className="w-full max-w-md bg-white border border-slate-200 shadow-xl">
        <div className="px-5 py-4 border-b border-slate-100">
          <h2 className="font-display font-semibold text-slate-900 text-sm">
            Reject selected mappings
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            {mappingIds.length} mapping{mappingIds.length === 1 ? "" : "s"} will be marked
            REJECTED.
          </p>
        </div>

        <div className="px-5 py-4 space-y-3">
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1.5">
              Rejection reason <span className="text-red-500">*</span>
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={4}
              placeholder="Explain why these AI suggestions are incorrect (minimum 10 characters)"
              className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-brand-500 resize-none"
            />
            <p className="text-[11px] text-slate-400 mt-1">
              {reason.trim().length}/10 characters minimum
            </p>
          </div>

          {rejectMutation.isError && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2">
              {getApiErrorMessage(rejectMutation.error, "Bulk reject failed.")}
            </div>
          )}

        </div>

        <div className="px-5 py-4 border-t border-slate-100 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={() => {
              onClose();
              setReason("");
            }}
            className="text-sm text-slate-500 hover:text-slate-700 transition-colors px-3 py-2"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => rejectMutation.mutate()}
            disabled={!canConfirm || rejectMutation.isPending}
            className="text-sm font-semibold px-4 py-2 bg-red-600 text-white hover:bg-red-500 transition-colors disabled:opacity-50"
          >
            {rejectMutation.isPending ? "Rejecting…" : "Reject mappings"}
          </button>
        </div>
      </div>
    </div>
  );
}
