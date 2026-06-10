"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { usePermissions } from "@/hooks/usePermissions";
import { studiesApi } from "@/lib/api/studies";
import type { Study, StudyStatus } from "@/types";

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-slate-100 text-slate-600",
  ACTIVE: "bg-emerald-100 text-emerald-700",
  ON_HOLD: "bg-amber-100 text-amber-700",
  COMPLETED: "bg-blue-100 text-blue-700",
  ARCHIVED: "bg-slate-100 text-slate-500",
  TERMINATED: "bg-red-100 text-red-700",
};

const PHASE_LABELS: Record<string, string> = {
  PHASE_1: "Phase 1",
  PHASE_1_2: "Phase 1/2",
  PHASE_2: "Phase 2",
  PHASE_2_3: "Phase 2/3",
  PHASE_3: "Phase 3",
  PHASE_3_4: "Phase 3/4",
  PHASE_4: "Phase 4",
  OBSERVATIONAL: "Observational",
  OTHER: "Other",
};

const ALL_STATUSES: StudyStatus[] = ["DRAFT", "ACTIVE", "ON_HOLD", "COMPLETED", "ARCHIVED", "TERMINATED"];

function canTerminateStudy(study: Study): boolean {
  return study.status !== "TERMINATED" && study.status !== "ARCHIVED";
}

export default function StudiesPage() {
  const { token, role } = useAuthStore();
  const perms = usePermissions(role);
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<StudyStatus | "ALL">("ALL");
  const [terminatingId, setTerminatingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["studies", token, statusFilter],
    queryFn: () =>
      studiesApi.list(
        { status: statusFilter !== "ALL" ? statusFilter : undefined, page_size: 50 },
        token!
      ),
    enabled: !!token,
  });

  const studies = data?.items ?? [];

  const terminateMutation = useMutation({
    mutationFn: (studyId: string) => studiesApi.terminate(studyId, token!),
    onSuccess: () => {
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ["studies"] });
    },
    onError: (err: Error) => setActionError(err.message),
    onSettled: () => setTerminatingId(null),
  });

  function handleTerminate(study: Study) {
    const confirmed = window.confirm(
      `Terminate "${study.name}"? The study will become read-only and cannot be reactivated.`
    );
    if (!confirmed) return;
    setTerminatingId(study.id);
    terminateMutation.mutate(study.id);
  }

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white flex items-center justify-between">
        <div>
          <h1 className="font-display text-xl font-bold text-slate-900">Studies</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            {data?.total ?? 0} studies in your organization
          </p>
        </div>
        {perms.isAdmin && (
          <Link
            href="/studies/new"
            className="bg-brand-600 hover:bg-brand-500 text-white text-sm font-semibold font-display px-5 py-2.5 transition-colors"
          >
            New study
          </Link>
        )}
      </div>

      <div className="px-8 py-6">
        {actionError && (
          <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-xs px-4 py-3">
            {actionError}
          </div>
        )}

        {/* Filters */}
        <div className="flex gap-1.5 mb-6">
          <button
            onClick={() => setStatusFilter("ALL")}
            className={`text-xs px-3 py-1.5 font-medium transition-colors ${
              statusFilter === "ALL"
                ? "bg-brand-600 text-white"
                : "bg-white border border-slate-200 text-slate-600 hover:border-slate-300"
            }`}
          >
            All
          </button>
          {ALL_STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`text-xs px-3 py-1.5 font-medium transition-colors ${
                statusFilter === s
                  ? "bg-brand-600 text-white"
                  : "bg-white border border-slate-200 text-slate-600 hover:border-slate-300"
              }`}
            >
              {s.charAt(0) + s.slice(1).toLowerCase().replace("_", " ")}
            </button>
          ))}
        </div>

        {/* Table */}
        <div className="bg-white border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Protocol</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Study Name</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Indication</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Phase</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Start Date</th>
                {perms.isAdmin && (
                  <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Actions</th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isLoading ? (
                <tr>
                  <td colSpan={perms.isAdmin ? 7 : 6} className="px-4 py-10 text-center text-slate-400 text-sm">
                    Loading studies…
                  </td>
                </tr>
              ) : studies.length === 0 ? (
                <tr>
                  <td colSpan={perms.isAdmin ? 7 : 6} className="px-4 py-10 text-center text-slate-400 text-sm">
                    No studies found.{" "}
                    {perms.isAdmin && (
                      <Link href="/studies/new" className="text-brand-600 hover:underline">
                        Create your first study.
                      </Link>
                    )}
                  </td>
                </tr>
              ) : (
                studies.map((study) => (
                  <tr key={study.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-slate-500">{study.protocol_number}</td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/studies/${study.id}`}
                        className="font-medium text-slate-900 hover:text-brand-700 transition-colors"
                      >
                        {study.name}
                      </Link>
                      {study.regulatory_region && study.regulatory_region.length > 0 && (
                        <div className="flex gap-1 mt-0.5">
                          {study.regulatory_region.map((r) => (
                            <span key={r} className="text-[10px] px-1.5 py-0.5 bg-slate-100 text-slate-500 font-mono">
                              {r}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-600 text-xs">{study.indication ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-600 text-xs">
                      {study.phase ? PHASE_LABELS[study.phase] ?? study.phase : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 font-medium ${STATUS_COLORS[study.status]}`}>
                        {study.status.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-600 text-xs">
                      {study.start_date
                        ? new Date(study.start_date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
                        : "—"}
                    </td>
                    {perms.isAdmin && (
                      <td className="px-4 py-3 text-right">
                        {canTerminateStudy(study) ? (
                          <button
                            type="button"
                            onClick={() => handleTerminate(study)}
                            disabled={terminatingId === study.id}
                            className="text-xs font-medium text-red-700 hover:text-red-800 border border-red-200 hover:border-red-300 px-2.5 py-1 disabled:opacity-50"
                          >
                            {terminatingId === study.id ? "Terminating…" : "Terminate"}
                          </button>
                        ) : (
                          <span className="text-xs text-slate-400">—</span>
                        )}
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
