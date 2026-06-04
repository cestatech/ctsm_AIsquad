"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { usePermissions } from "@/hooks/usePermissions";
import { auditApi } from "@/lib/api/audit";

const ACTION_COLORS: Record<string, string> = {
  USER_LOGIN: "bg-slate-100 text-slate-600",
  USER_LOGOUT: "bg-slate-100 text-slate-500",
  USER_LOGIN_FAILED: "bg-red-100 text-red-600",
  USER_CREATED: "bg-teal-100 text-teal-700",
  USER_DEACTIVATED: "bg-red-100 text-red-700",
  USER_ROLE_CHANGED: "bg-violet-100 text-violet-700",
  STUDY_CREATED: "bg-blue-100 text-blue-700",
  STUDY_UPDATED: "bg-blue-100 text-blue-600",
  STUDY_ARCHIVED: "bg-slate-100 text-slate-600",
  ARTIFACT_CREATED: "bg-indigo-100 text-indigo-700",
  ARTIFACT_UPDATED: "bg-indigo-100 text-indigo-600",
  ARTIFACT_SUBMITTED: "bg-amber-100 text-amber-700",
  ARTIFACT_APPROVED: "bg-emerald-100 text-emerald-700",
  ARTIFACT_REJECTED: "bg-red-100 text-red-700",
  ARTIFACT_LOCKED: "bg-blue-100 text-blue-700",
  ARTIFACT_AMENDED: "bg-purple-100 text-purple-700",
  ARTIFACT_DELETED: "bg-red-100 text-red-700",
  VALIDATION_RUN_STARTED: "bg-cyan-100 text-cyan-700",
  VALIDATION_RUN_COMPLETED: "bg-cyan-100 text-cyan-600",
  AI_GENERATION_STARTED: "bg-violet-100 text-violet-700",
  AI_GENERATION_COMPLETED: "bg-violet-100 text-violet-600",
};

const RESOURCE_TYPE_LABELS: Record<string, string> = {
  user: "User",
  study: "Study",
  artifact: "Artifact",
  organization: "Organization",
  comment: "Comment",
  validation: "Validation",
  generation: "AI Generation",
};

function truncateId(id: string | null) {
  if (!id) return "—";
  return `${id.slice(0, 8)}…`;
}

const PAGE_SIZE = 20;

export default function AuditLogPage() {
  const { token, role } = useAuthStore();
  const perms = usePermissions(role);
  const [page, setPage] = useState(1);
  const [resourceFilter, setResourceFilter] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["audit", token, page, resourceFilter],
    queryFn: () =>
      auditApi.list(
        { page, page_size: PAGE_SIZE, resource_type: resourceFilter || undefined },
        token!
      ),
    enabled: !!token,
  });

  if (!perms.canViewAuditLog) {
    return (
      <div className="px-8 py-16 text-center text-slate-500 text-sm">
        You don&apos;t have permission to view audit logs.
      </div>
    );
  }

  const logs = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <h1 className="font-display text-xl font-bold text-slate-900">Audit Log</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          {total} total events · Append-only · 15-year retention
        </p>
      </div>

      <div className="px-8 py-6">
        {/* Filters */}
        <div className="flex gap-1.5 mb-6 flex-wrap">
          {["", "user", "study", "artifact", "organization"].map((rt) => (
            <button
              key={rt}
              onClick={() => { setResourceFilter(rt); setPage(1); }}
              className={`text-xs px-3 py-1.5 font-medium transition-colors ${
                resourceFilter === rt
                  ? "bg-brand-600 text-white"
                  : "bg-white border border-slate-200 text-slate-600 hover:border-slate-300"
              }`}
            >
              {rt === "" ? "All" : RESOURCE_TYPE_LABELS[rt] ?? rt}
            </button>
          ))}
        </div>

        <div className="bg-white border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide w-40">Timestamp</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Action</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Actor</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Resource</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Resource ID</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">IP Address</th>
                <th className="px-4 py-3 w-8" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-slate-400 text-sm">Loading…</td>
                </tr>
              ) : isError ? (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-red-400 text-sm">Failed to load audit logs.</td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-slate-400 text-sm">No audit events found.</td>
                </tr>
              ) : (
                logs.map((log) => (
                  <>
                    <tr
                      key={log.id}
                      className="hover:bg-slate-50 transition-colors cursor-pointer"
                      onClick={() => setExpandedId(expandedId === log.id ? null : log.id)}
                    >
                      <td className="px-4 py-3 text-xs font-mono text-slate-500 whitespace-nowrap">
                        {new Date(log.created_at).toLocaleString("en-US", {
                          month: "short", day: "numeric",
                          hour: "2-digit", minute: "2-digit",
                        })}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`text-xs px-2 py-0.5 font-medium ${
                            ACTION_COLORS[log.action] ?? "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {log.action.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-700">
                        {log.actor?.full_name ?? (log.actor_user_id ? truncateId(log.actor_user_id) : "System")}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-600">
                        {RESOURCE_TYPE_LABELS[log.resource_type] ?? log.resource_type}
                      </td>
                      <td className="px-4 py-3 text-xs font-mono text-slate-400">
                        {truncateId(log.resource_id)}
                      </td>
                      <td className="px-4 py-3 text-xs font-mono text-slate-400">
                        {log.ip_address ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-400">
                        {expandedId === log.id ? "▲" : "▼"}
                      </td>
                    </tr>
                    {expandedId === log.id && (
                      <tr key={`${log.id}-detail`} className="bg-slate-50">
                        <td colSpan={7} className="px-6 py-4">
                          <div className="grid grid-cols-2 gap-4 text-xs">
                            <div>
                              <p className="text-slate-400 mb-1.5 font-semibold uppercase tracking-wide text-[10px]">Before State</p>
                              <pre className="bg-white border border-slate-200 p-3 text-slate-600 font-mono overflow-auto max-h-32">
                                {log.before_state
                                  ? JSON.stringify(log.before_state, null, 2)
                                  : "null"}
                              </pre>
                            </div>
                            <div>
                              <p className="text-slate-400 mb-1.5 font-semibold uppercase tracking-wide text-[10px]">After State</p>
                              <pre className="bg-white border border-slate-200 p-3 text-slate-600 font-mono overflow-auto max-h-32">
                                {log.after_state
                                  ? JSON.stringify(log.after_state, null, 2)
                                  : "null"}
                              </pre>
                            </div>
                          </div>
                          <div className="mt-3 text-[11px] text-slate-400 font-mono space-x-4">
                            <span>ID: {log.id}</span>
                            <span>Org: {log.organization_id}</span>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))
              )}
            </tbody>
          </table>

          {/* Pagination */}
          {total > PAGE_SIZE && (
            <div className="px-4 py-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
              <span>
                Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total}
              </span>
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
    </div>
  );
}
