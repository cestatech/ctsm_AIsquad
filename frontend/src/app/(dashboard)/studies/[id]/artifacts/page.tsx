"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { canRemoveArtifact } from "@/hooks/usePermissions";
import { useStudyPermissions } from "@/hooks/useStudyPermissions";
import { useArtifactDownload } from "@/hooks/useArtifactDownload";
import { studiesApi } from "@/lib/api/studies";
import { artifactsApi } from "@/lib/api/artifacts";
import { getApiErrorMessage } from "@/lib/api/errors";
import type { Artifact, ArtifactType } from "@/types";

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-slate-100 text-slate-600",
  IN_REVIEW: "bg-amber-100 text-amber-700",
  APPROVED: "bg-emerald-100 text-emerald-700",
  REJECTED: "bg-red-100 text-red-700",
  LOCKED: "bg-blue-100 text-blue-700",
  AMENDED: "bg-purple-100 text-purple-700",
  SUPERSEDED: "bg-slate-100 text-slate-500",
};

const ARTIFACT_TYPES: { value: ArtifactType; label: string }[] = [
  { value: "PROTOCOL", label: "Protocol" },
  { value: "ICF", label: "Informed Consent Form (ICF)" },
  { value: "SAP", label: "Statistical Analysis Plan (SAP)" },
  { value: "EDC_CRF", label: "eCRF / EDC Form" },
  { value: "TRACEABILITY_MATRIX", label: "Traceability Matrix" },
  { value: "SDTM_DATASET", label: "SDTM Dataset" },
  { value: "ADAM_DATASET", label: "ADaM Dataset" },
  { value: "TLF", label: "Tables, Listings & Figures (TLF)" },
  { value: "VALIDATION_REPORT", label: "Validation Report" },
  { value: "CSR", label: "Clinical Study Report (CSR)" },
  { value: "SUBMISSION_PACKAGE", label: "Submission Package" },
  { value: "OTHER", label: "Other" },
];

const TYPE_LABELS: Record<string, string> = Object.fromEntries(
  ARTIFACT_TYPES.map((t) => [t.value, t.label])
);

export default function ArtifactListPage({ params }: { params: { id: string } }) {
  const { token, user } = useAuthStore();
  const perms = useStudyPermissions(params.id);
  const { downloadArtifact, isDownloading, getDownloadOptions } = useArtifactDownload(token);
  const queryClient = useQueryClient();
  const studyId = params.id;
  const searchParams = useSearchParams();

  const [showNewModal, setShowNewModal] = useState(false);
  const [newForm, setNewForm] = useState({ name: "", artifact_type: "" as ArtifactType | "", description: "" });
  const [formError, setFormError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [removeTarget, setRemoveTarget] = useState<Artifact | null>(null);

  useEffect(() => {
    if (searchParams.get("new") === "1" && perms.canCreateArtifact) {
      setShowNewModal(true);
    }
  }, [searchParams, perms.canCreateArtifact]);

  const { data: study } = useQuery({
    queryKey: ["study", studyId, token],
    queryFn: () => studiesApi.get(studyId, token!),
    enabled: !!token,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["artifacts", studyId, token],
    queryFn: () => artifactsApi.list({ study_id: studyId, page_size: 100 }, token!),
    enabled: !!token,
  });

  const removeMutation = useMutation({
    mutationFn: (artifactId: string) => artifactsApi.delete(artifactId, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["artifacts", studyId] });
      setRemoveTarget(null);
      setActionError(null);
    },
    onError: (err) => setActionError(getApiErrorMessage(err, "Remove failed.")),
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      if (!newForm.name.trim() || !newForm.artifact_type) throw new Error("Name and type are required.");
      return artifactsApi.create(
        { study_id: studyId, name: newForm.name, artifact_type: newForm.artifact_type, description: newForm.description || undefined },
        token!
      );
    },
    onSuccess: (artifact) => {
      queryClient.invalidateQueries({ queryKey: ["artifacts", studyId] });
      setShowNewModal(false);
      setNewForm({ name: "", artifact_type: "", description: "" });
      window.location.href = `/studies/${studyId}/artifacts/${artifact.id}`;
    },
    onError: (err) => {
      setFormError(err instanceof Error ? err.message : "Failed to create artifact.");
    },
  });

  const artifacts = data?.items ?? [];

  function rel(iso: string) {
    const diff = Date.now() - new Date(iso).getTime();
    const hrs = Math.floor(diff / 3_600_000);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  }

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link href={`/studies/${studyId}`} className="text-slate-400 hover:text-slate-700 text-sm transition-colors">
              ← {study?.short_name ?? study?.name ?? "Study"}
            </Link>
          </div>
          <h1 className="font-display text-xl font-bold text-slate-900">Artifacts</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            {data?.total ?? 0} artifacts in this study
          </p>
        </div>
        {perms.canCreateArtifact && (
          <button
            onClick={() => { setShowNewModal(true); setFormError(null); }}
            className="bg-brand-600 hover:bg-brand-500 text-white text-sm font-semibold font-display px-5 py-2.5 transition-colors"
          >
            New artifact
          </button>
        )}
      </div>

      <div className="px-8 py-6">
        {actionError && (
          <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2">
            {actionError}
          </div>
        )}
        <div className="bg-white border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Artifact Name</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Type</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Version</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Tags</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Updated</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-slate-400 text-sm">Loading…</td>
                </tr>
              ) : artifacts.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center">
                    <p className="text-slate-400 text-sm mb-3">No artifacts in this study yet.</p>
                    {perms.canCreateArtifact && (
                      <button
                        onClick={() => setShowNewModal(true)}
                        className="text-xs text-brand-600 hover:text-brand-700 font-medium"
                      >
                        + Create first artifact
                      </button>
                    )}
                  </td>
                </tr>
              ) : (
                artifacts.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3">
                      <Link
                        href={
                          a.artifact_type === "SDTM_DATASET"
                            ? `/studies/${studyId}/sdtm/${a.id}`
                            : a.artifact_type === "TLF"
                              ? `/studies/${studyId}/tlf/${a.id}/catalog`
                              : `/studies/${studyId}/artifacts/${a.id}`
                        }
                        className="font-medium text-slate-900 hover:text-brand-700 transition-colors"
                      >
                        {a.name}
                      </Link>
                      {a.description && (
                        <p className="text-xs text-slate-400 mt-0.5 truncate max-w-xs">{a.description}</p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-600">
                      {TYPE_LABELS[a.artifact_type] ?? a.artifact_type}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 font-medium ${STATUS_COLORS[a.status]}`}>
                        {a.status.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs font-mono text-slate-500">
                      v{a.current_version_number}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-1 flex-wrap">
                        {(a.tags ?? []).slice(0, 3).map((tag) => (
                          <span key={tag} className="text-[10px] px-1.5 py-0.5 bg-slate-100 text-slate-500">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-400">{rel(a.updated_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-2">
                        {a.current_version_id &&
                          getDownloadOptions(a).map((option) => (
                            <button
                              key={`${a.id}-${option.format}`}
                              type="button"
                              onClick={async () => {
                                setActionError(null);
                                try {
                                  await downloadArtifact(a, option.format);
                                } catch (err) {
                                  setActionError(
                                    err instanceof Error ? err.message : "Download failed."
                                  );
                                }
                              }}
                              disabled={isDownloading(a.id)}
                              className="text-[11px] text-brand-600 hover:text-brand-700 font-medium disabled:opacity-50"
                            >
                              {isDownloading(a.id) ? "Downloading…" : option.label}
                            </button>
                          ))}
                        {canRemoveArtifact(a, user?.id, perms) && (
                          <button
                            type="button"
                            onClick={() => {
                              setActionError(null);
                              setRemoveTarget(a);
                            }}
                            className="text-[11px] text-red-600 hover:text-red-700 font-medium"
                          >
                            Remove
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {removeTarget && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white w-full max-w-md border border-slate-200 shadow-xl">
            <div className="px-6 py-4 border-b border-slate-100">
              <h2 className="font-display font-semibold text-slate-900">Remove artifact</h2>
            </div>
            <div className="px-6 py-5 space-y-4">
              <p className="text-sm text-slate-700">
                Are you sure you want to remove <strong>{removeTarget.name}</strong> from this study?
                This action cannot be undone.
              </p>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => removeMutation.mutate(removeTarget.id)}
                  disabled={removeMutation.isPending}
                  className="text-sm font-semibold font-display px-5 py-2 bg-red-600 hover:bg-red-700 text-white transition-colors disabled:opacity-50"
                >
                  {removeMutation.isPending ? "Removing…" : "Yes, remove"}
                </button>
                <button
                  type="button"
                  onClick={() => setRemoveTarget(null)}
                  className="text-slate-500 hover:text-slate-700 text-sm transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* New Artifact Modal */}
      {showNewModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white w-full max-w-md border border-slate-200 shadow-xl">
            <div className="px-6 py-4 border-b border-slate-100">
              <h2 className="font-display font-semibold text-slate-900">New Artifact</h2>
            </div>
            <div className="px-6 py-5 space-y-4">
              {formError && (
                <div className="bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2">{formError}</div>
              )}
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">
                  Artifact Type <span className="text-red-500">*</span>
                </label>
                <select
                  value={newForm.artifact_type}
                  onChange={(e) => setNewForm((f) => ({ ...f, artifact_type: e.target.value as ArtifactType }))}
                  className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 bg-white"
                >
                  <option value="">Select type…</option>
                  {ARTIFACT_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">
                  Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={newForm.name}
                  onChange={(e) => setNewForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. Study Protocol v1.0"
                  className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Description</label>
                <textarea
                  value={newForm.description}
                  onChange={(e) => setNewForm((f) => ({ ...f, description: e.target.value }))}
                  rows={2}
                  placeholder="Optional description"
                  className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 resize-none"
                />
              </div>
            </div>
            <div className="px-6 py-4 border-t border-slate-100 flex gap-3">
              <button
                onClick={() => createMutation.mutate()}
                disabled={createMutation.isPending}
                className="bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white text-sm font-semibold font-display px-5 py-2 transition-colors"
              >
                {createMutation.isPending ? "Creating…" : "Create artifact"}
              </button>
              <button
                onClick={() => { setShowNewModal(false); setFormError(null); }}
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
