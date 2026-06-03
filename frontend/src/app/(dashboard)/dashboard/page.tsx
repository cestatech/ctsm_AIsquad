"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { usePermissions } from "@/hooks/usePermissions";
import { studiesApi } from "@/lib/api/studies";
import { artifactsApi } from "@/lib/api/artifacts";
import { approvalsApi } from "@/lib/api/approvals";
import { MOCK_STUDIES, MOCK_ARTIFACTS, MOCK_PENDING_APPROVALS } from "@/lib/mockData";

function rel(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

const ARTIFACT_STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-slate-100 text-slate-600",
  IN_REVIEW: "bg-amber-100 text-amber-700",
  APPROVED: "bg-emerald-100 text-emerald-700",
  REJECTED: "bg-red-100 text-red-700",
  LOCKED: "bg-blue-100 text-blue-700",
  AMENDED: "bg-purple-100 text-purple-700",
  SUPERSEDED: "bg-slate-100 text-slate-500",
};

const STUDY_STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-slate-100 text-slate-600",
  ACTIVE: "bg-emerald-100 text-emerald-700",
  ON_HOLD: "bg-amber-100 text-amber-700",
  COMPLETED: "bg-blue-100 text-blue-700",
  ARCHIVED: "bg-slate-100 text-slate-500",
  TERMINATED: "bg-red-100 text-red-700",
};

export default function DashboardPage() {
  const { token, user, role } = useAuthStore();
  const perms = usePermissions(role);

  const { data: studiesData } = useQuery({
    queryKey: ["studies", token],
    queryFn: async () => {
      try {
        return await studiesApi.list({ page_size: 4 }, token!);
      } catch {
        return { items: MOCK_STUDIES.slice(0, 4), total: MOCK_STUDIES.length, page: 1, page_size: 4, has_next: false, has_prev: false };
      }
    },
    enabled: !!token,
  });

  const { data: artifactsData } = useQuery({
    queryKey: ["artifacts-all", token],
    queryFn: async () => {
      try {
        return await artifactsApi.list({ page_size: 5 }, token!);
      } catch {
        return { items: MOCK_ARTIFACTS.slice(0, 5), total: MOCK_ARTIFACTS.length, page: 1, page_size: 5, has_next: false, has_prev: false };
      }
    },
    enabled: !!token,
  });

  const { data: approvalsData } = useQuery({
    queryKey: ["approvals-queue", token],
    queryFn: async () => {
      try {
        return await approvalsApi.queue({ page_size: 5 }, token!);
      } catch {
        return { items: [], total: MOCK_PENDING_APPROVALS.length, page: 1, page_size: 5, has_next: false, has_prev: false };
      }
    },
    enabled: !!token,
  });

  const studies = studiesData?.items ?? [];
  const artifacts = artifactsData?.items ?? [];
  const pendingCount = approvalsData?.total ?? MOCK_PENDING_APPROVALS.length;
  const activeStudies = studies.filter((s) => s.status === "ACTIVE").length;

  if (!user) return null;

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <h1 className="font-display text-xl font-bold text-slate-900">Dashboard</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Welcome back, {user.full_name.split(" ")[0]}
        </p>
      </div>

      <div className="px-8 py-8 space-y-8">
        {/* Stats */}
        <div className="grid grid-cols-4 gap-px bg-slate-200 border border-slate-200">
          {[
            { label: "Active Studies", value: activeStudies || studiesData?.total || 0 },
            { label: "Total Artifacts", value: artifactsData?.total ?? MOCK_ARTIFACTS.length },
            { label: "Pending Approvals", value: pendingCount },
            { label: "Team Members", value: 4 },
          ].map((stat) => (
            <div key={stat.label} className="bg-white px-6 py-5">
              <p className="font-display text-2xl font-bold text-slate-900">{stat.value}</p>
              <p className="text-slate-500 text-sm mt-1">{stat.label}</p>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-6">
          {/* Recent Studies */}
          <div className="bg-white border border-slate-200">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
              <h2 className="font-display font-semibold text-slate-900 text-sm">Recent Studies</h2>
              <Link href="/studies" className="text-xs text-brand-600 hover:text-brand-700 font-medium">
                View all →
              </Link>
            </div>
            <div className="divide-y divide-slate-100">
              {studies.length === 0 ? (
                <div className="px-5 py-8 text-center text-slate-500 text-sm">No studies yet</div>
              ) : (
                studies.slice(0, 4).map((study) => (
                  <Link
                    key={study.id}
                    href={`/studies/${study.id}`}
                    className="flex items-center justify-between px-5 py-3 hover:bg-slate-50 transition-colors group"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-900 truncate group-hover:text-brand-700">
                        {study.short_name ?? study.name}
                      </p>
                      <p className="text-xs text-slate-500 font-mono mt-0.5">{study.protocol_number}</p>
                    </div>
                    <span
                      className={`flex-shrink-0 ml-3 text-xs px-2 py-0.5 font-medium ${
                        STUDY_STATUS_COLORS[study.status] ?? "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {study.status}
                    </span>
                  </Link>
                ))
              )}
            </div>
            {perms.isAdmin && (
              <div className="px-5 py-3 border-t border-slate-100">
                <Link
                  href="/studies/new"
                  className="text-xs text-brand-600 hover:text-brand-700 font-medium"
                >
                  + New study
                </Link>
              </div>
            )}
          </div>

          {/* Recent Artifacts */}
          <div className="bg-white border border-slate-200">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
              <h2 className="font-display font-semibold text-slate-900 text-sm">Recent Artifacts</h2>
            </div>
            <div className="divide-y divide-slate-100">
              {artifacts.length === 0 ? (
                <div className="px-5 py-8 text-center text-slate-500 text-sm">No artifacts yet</div>
              ) : (
                artifacts.slice(0, 5).map((artifact) => (
                  <Link
                    key={artifact.id}
                    href={`/studies/${artifact.study_id}/artifacts/${artifact.id}`}
                    className="flex items-center justify-between px-5 py-3 hover:bg-slate-50 transition-colors group"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-900 truncate group-hover:text-brand-700">
                        {artifact.name}
                      </p>
                      <p className="text-xs text-slate-500 mt-0.5">
                        v{artifact.current_version_number} · {rel(artifact.updated_at)}
                      </p>
                    </div>
                    <span
                      className={`flex-shrink-0 ml-3 text-xs px-2 py-0.5 font-medium ${
                        ARTIFACT_STATUS_COLORS[artifact.status] ?? "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {artifact.status.replace("_", " ")}
                    </span>
                  </Link>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Pending Approvals (for ADMIN + REVIEWER) */}
        {perms.canApproveArtifact && pendingCount > 0 && (
          <div className="bg-amber-50 border border-amber-200 px-6 py-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-amber-900 font-display">
                {pendingCount} artifact{pendingCount !== 1 ? "s" : ""} awaiting review
              </p>
              <p className="text-xs text-amber-700 mt-0.5">
                Your approval is required before these artifacts can proceed.
              </p>
            </div>
            <Link
              href="/approvals"
              className="bg-amber-700 hover:bg-amber-800 text-white text-xs font-semibold font-display px-4 py-2 transition-colors flex-shrink-0 ml-4"
            >
              Review queue
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
