"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { usePermissions } from "@/hooks/usePermissions";
import { validationApi } from "@/lib/api/validation";
import type { ValidationRun } from "@/types";

const STATUS_COLORS: Record<string, string> = {
  PENDING:  "bg-slate-100 text-slate-600",
  RUNNING:  "bg-amber-100 text-amber-700",
  PASSED:   "bg-emerald-100 text-emerald-700",
  FAILED:   "bg-red-100 text-red-700",
  ERROR:    "bg-red-100 text-red-800",
};

const PAGE_SIZE = 25;

function RunRow({ run }: { run: ValidationRun }) {
  const passRate =
    run.total_checks && run.passed_checks != null
      ? Math.round((run.passed_checks / run.total_checks) * 100)
      : null;

  return (
    <tr className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
      <td className="px-4 py-3">
        <span className={`text-xs px-2 py-0.5 font-medium ${STATUS_COLORS[run.status] ?? "bg-slate-100 text-slate-600"}`}>
          {run.status}
        </span>
      </td>
      <td className="px-4 py-3 text-xs font-mono text-slate-500">{run.artifact_id.slice(0, 8)}…</td>
      <td className="px-4 py-3 text-xs text-slate-600">{run.engine}</td>
      <td className="px-4 py-3 text-xs text-slate-600">{run.rule_set_version ?? "—"}</td>
      <td className="px-4 py-3 text-xs text-slate-600">
        {run.total_checks != null ? (
          <span>
            {run.passed_checks}/{run.total_checks}
            {passRate != null && (
              <span className={`ml-1.5 font-semibold ${passRate === 100 ? "text-emerald-600" : passRate >= 80 ? "text-amber-600" : "text-red-600"}`}>
                ({passRate}%)
              </span>
            )}
          </span>
        ) : "—"}
      </td>
      <td className="px-4 py-3 text-xs text-slate-500 font-mono whitespace-nowrap">
        {new Date(run.created_at).toLocaleString("en-US", {
          month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
        })}
      </td>
    </tr>
  );
}

export default function ValidationPage() {
  const { token, role } = useAuthStore();
  const perms = usePermissions(role);
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [showTrigger, setShowTrigger] = useState(false);
  const [triggerError, setTriggerError] = useState<string | null>(null);
  const [form, setForm] = useState({
    artifact_id: "",
    artifact_version_id: "",
    engine: "internal",
    rule_set_version: "",
  });

  const { data, isLoading } = useQuery({
    queryKey: ["validation-runs", token, page],
    queryFn: () => validationApi.listRuns({ page, page_size: PAGE_SIZE }, token!),
    enabled: !!token,
  });

  const triggerMutation = useMutation({
    mutationFn: () =>
      validationApi.triggerRun(
        {
          artifact_id: form.artifact_id.trim(),
          artifact_version_id: form.artifact_version_id.trim(),
          engine: form.engine,
          rule_set_version: form.rule_set_version || undefined,
        },
        token!
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["validation-runs"] });
      setShowTrigger(false);
      setForm({ artifact_id: "", artifact_version_id: "", engine: "internal", rule_set_version: "" });
    },
    onError: (err) => setTriggerError(err instanceof Error ? err.message : "Failed to trigger run."),
  });

  const runs = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display text-xl font-bold text-slate-900">Validation Runs</h1>
            <p className="text-slate-500 text-sm mt-0.5">{total} total runs · CDISC conformance checks</p>
          </div>
          {perms.canRunValidation && (
            <button
              onClick={() => { setShowTrigger(true); setTriggerError(null); }}
              className="text-sm font-semibold px-4 py-2 bg-brand-600 text-white hover:bg-brand-500 transition-colors"
            >
              Trigger Run
            </button>
          )}
        </div>
      </div>

      <div className="px-8 py-6">
        <div className="bg-white border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Artifact</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Engine</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Rule Set</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Passed / Total</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Triggered</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-slate-400 text-sm">Loading…</td>
                </tr>
              ) : runs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-slate-400 text-sm">
                    No validation runs yet.{" "}
                    {perms.canRunValidation && (
                      <button
                        onClick={() => setShowTrigger(true)}
                        className="text-brand-600 hover:underline"
                      >
                        Trigger the first one.
                      </button>
                    )}
                  </td>
                </tr>
              ) : (
                runs.map((run) => <RunRow key={run.id} run={run} />)
              )}
            </tbody>
          </table>

          {total > PAGE_SIZE && (
            <div className="px-4 py-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
              <span>Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total}</span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1.5 border border-slate-200 disabled:opacity-40 hover:bg-slate-50 transition-colors"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={!data?.has_next}
                  className="px-3 py-1.5 border border-slate-200 disabled:opacity-40 hover:bg-slate-50 transition-colors"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Trigger Modal */}
      {showTrigger && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white w-full max-w-md border border-slate-200 shadow-xl">
            <div className="px-6 py-4 border-b border-slate-100">
              <h2 className="font-display font-semibold text-slate-900">Trigger Validation Run</h2>
            </div>
            <div className="px-6 py-5 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Artifact ID <span className="text-red-500">*</span></label>
                <input
                  type="text"
                  value={form.artifact_id}
                  onChange={(e) => setForm((f) => ({ ...f, artifact_id: e.target.value }))}
                  placeholder="UUID"
                  className="w-full border border-slate-200 px-3 py-2 text-sm font-mono focus:outline-none focus:border-brand-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Artifact Version ID <span className="text-red-500">*</span></label>
                <input
                  type="text"
                  value={form.artifact_version_id}
                  onChange={(e) => setForm((f) => ({ ...f, artifact_version_id: e.target.value }))}
                  placeholder="UUID"
                  className="w-full border border-slate-200 px-3 py-2 text-sm font-mono focus:outline-none focus:border-brand-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1.5">Engine</label>
                  <select
                    value={form.engine}
                    onChange={(e) => setForm((f) => ({ ...f, engine: e.target.value }))}
                    className="w-full border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:border-brand-500 bg-white"
                  >
                    <option value="internal">Internal</option>
                    <option value="pinnacle21">Pinnacle 21</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1.5">Rule Set Version</label>
                  <input
                    type="text"
                    value={form.rule_set_version}
                    onChange={(e) => setForm((f) => ({ ...f, rule_set_version: e.target.value }))}
                    placeholder="e.g. 3.4"
                    className="w-full border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:border-brand-500"
                  />
                </div>
              </div>
              {triggerError && (
                <div className="bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2">{triggerError}</div>
              )}
            </div>
            <div className="px-6 py-4 border-t border-slate-100 flex gap-3">
              <button
                onClick={() => triggerMutation.mutate()}
                disabled={triggerMutation.isPending || !form.artifact_id.trim() || !form.artifact_version_id.trim()}
                className="text-sm font-semibold px-5 py-2 bg-brand-600 text-white hover:bg-brand-500 disabled:opacity-50 transition-colors"
              >
                {triggerMutation.isPending ? "Triggering…" : "Trigger Run"}
              </button>
              <button
                onClick={() => setShowTrigger(false)}
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
