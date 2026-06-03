"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { artifactsApi } from "@/lib/api/artifacts";
import { MOCK_ARTIFACTS, MOCK_ARTIFACT_VERSIONS, MOCK_USERS } from "@/lib/mockData";

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-slate-100 text-slate-600",
  IN_REVIEW: "bg-amber-100 text-amber-700",
  APPROVED: "bg-emerald-100 text-emerald-700",
  REJECTED: "bg-red-100 text-red-700",
  LOCKED: "bg-blue-100 text-blue-700",
  AMENDED: "bg-purple-100 text-purple-700",
  SUPERSEDED: "bg-slate-100 text-slate-500",
};

export default function VersionHistoryPage({ params }: { params: { id: string; artifactId: string } }) {
  const { token } = useAuthStore();
  const { id: studyId, artifactId } = params;

  const { data: artifact } = useQuery({
    queryKey: ["artifact", artifactId, token],
    queryFn: async () => {
      try {
        return await artifactsApi.get(artifactId, token!);
      } catch {
        return MOCK_ARTIFACTS.find((a) => a.id === artifactId) ?? MOCK_ARTIFACTS[0];
      }
    },
    enabled: !!token,
  });

  const { data: versions, isLoading } = useQuery({
    queryKey: ["artifact-versions", artifactId, token],
    queryFn: async () => {
      try {
        return await artifactsApi.getVersions(artifactId, token!);
      } catch {
        return MOCK_ARTIFACT_VERSIONS.filter((v) => v.artifact_id === artifactId);
      }
    },
    enabled: !!token,
  });

  const sortedVersions = (versions ?? []).slice().sort((a, b) => b.version_number - a.version_number);

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <div className="flex items-center gap-2 mb-2">
          <Link
            href={`/studies/${studyId}/artifacts/${artifactId}`}
            className="text-slate-400 hover:text-slate-700 text-sm transition-colors"
          >
            ← {artifact?.name ?? "Artifact"}
          </Link>
        </div>
        <h1 className="font-display text-xl font-bold text-slate-900">Version History</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          {sortedVersions.length} version{sortedVersions.length !== 1 ? "s" : ""} · Append-only record
        </p>
      </div>

      <div className="px-8 py-6 max-w-3xl">
        {isLoading ? (
          <div className="text-center text-slate-400 text-sm py-10">Loading versions…</div>
        ) : sortedVersions.length === 0 ? (
          <div className="text-center text-slate-400 text-sm py-10">No versions recorded yet.</div>
        ) : (
          <div className="relative">
            {/* Timeline line */}
            <div className="absolute left-3.5 top-4 bottom-4 w-px bg-slate-200" />

            <div className="space-y-0">
              {sortedVersions.map((version, index) => {
                const creator = MOCK_USERS.find((u) => u.id === version.created_by_id) ?? MOCK_USERS[0];
                const isCurrent = version.is_current;

                return (
                  <div key={version.id} className="relative pl-10 pb-6">
                    {/* Dot */}
                    <div
                      className={`absolute left-0.5 top-1 w-6 h-6 flex items-center justify-center text-xs font-bold font-mono ${
                        isCurrent ? "bg-brand-600 text-white" : "bg-white border-2 border-slate-300 text-slate-500"
                      }`}
                    >
                      {version.version_number}
                    </div>

                    <div
                      className={`bg-white border p-5 ${
                        isCurrent ? "border-brand-300 shadow-sm" : "border-slate-200"
                      }`}
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-display font-semibold text-slate-900 text-sm">
                              Version {version.version_number}
                            </span>
                            {isCurrent && (
                              <span className="text-[10px] px-2 py-0.5 bg-brand-100 text-brand-700 font-semibold">
                                CURRENT
                              </span>
                            )}
                            <span
                              className={`text-xs px-2 py-0.5 font-medium ${
                                STATUS_COLORS[version.status_at_creation] ?? "bg-slate-100 text-slate-600"
                              }`}
                            >
                              {version.status_at_creation.replace("_", " ")}
                            </span>
                          </div>
                          <p className="text-xs text-slate-500">
                            by {creator.full_name} ·{" "}
                            {new Date(version.created_at).toLocaleString("en-US", {
                              month: "short",
                              day: "numeric",
                              year: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </p>
                        </div>
                        {index === 0 && !isCurrent && (
                          <span className="text-xs text-slate-400">Latest</span>
                        )}
                      </div>

                      {version.change_summary && (
                        <p className="text-sm text-slate-700 mb-3">{version.change_summary}</p>
                      )}

                      <div className="flex items-center gap-4 text-xs text-slate-400">
                        <span className="font-mono">Hash: {version.content_hash.slice(0, 20)}…</span>
                        {version.file_size_bytes && (
                          <span>{(version.file_size_bytes / 1024).toFixed(1)} KB</span>
                        )}
                      </div>

                      {Object.keys(version.content).length > 0 && (
                        <details className="mt-3">
                          <summary className="text-xs text-brand-600 hover:text-brand-700 cursor-pointer font-medium">
                            View content snapshot
                          </summary>
                          <pre className="mt-2 text-xs text-slate-600 bg-slate-50 p-3 overflow-auto max-h-40 font-mono border border-slate-100">
                            {JSON.stringify(version.content, null, 2)}
                          </pre>
                        </details>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div className="mt-6 bg-slate-50 border border-slate-200 px-5 py-4 text-xs text-slate-500">
          <strong className="text-slate-700">Regulatory note:</strong> Version records are append-only and immutable
          per 21 CFR Part 11 / ICH E6 requirements. No version can be modified or deleted.
        </div>
      </div>
    </div>
  );
}
