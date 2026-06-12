"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { useCSRArtifactGuard, useCSREditor } from "@/hooks/useCSREditor";
import { useStudyPermissions } from "@/hooks/useStudyPermissions";
import { getApiErrorMessage } from "@/lib/api/errors";
import { studiesApi } from "@/lib/api/studies";
import {
  CSROutlineNavigator,
  CSROutlineNavigatorSkeleton,
} from "@/components/csr/CSROutlineNavigator";
import {
  CSRSectionEditor,
  CSRSectionEditorSkeleton,
} from "@/components/csr/CSRSectionEditor";
import {
  CSRTLFReferencePanel,
  CSRTLFReferencePanelSkeleton,
} from "@/components/csr/CSRTLFReferencePanel";

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-slate-100 text-slate-600",
  IN_REVIEW: "bg-amber-100 text-amber-700",
  APPROVED: "bg-emerald-100 text-emerald-700",
  REJECTED: "bg-red-100 text-red-700",
  LOCKED: "bg-blue-100 text-blue-700",
  AMENDED: "bg-purple-100 text-purple-700",
  SUPERSEDED: "bg-slate-100 text-slate-500",
};

export default function CSRSectionEditorPage({
  params,
}: {
  params: { id: string; artifactId: string };
}) {
  const studyId = params.id;
  const artifactId = params.artifactId;
  const { token } = useAuthStore();
  const perms = useStudyPermissions(studyId);
  const readOnly = perms.isReviewer || !perms.canEditArtifact;
  const [actionError, setActionError] = useState<string | null>(null);

  const {
    artifact,
    content,
    sections,
    activeSectionId,
    setActiveSectionId,
    isLoading,
    isError,
    error,
    updateSectionProse,
    handleSectionBlur,
    regenerateSection,
    isRegenerating,
    regeneratingSectionId,
    saveError,
    saveStatus,
  } = useCSREditor(studyId, artifactId);

  const guard = useCSRArtifactGuard(artifact, isLoading);

  const { data: study } = useQuery({
    queryKey: ["study", studyId, token],
    queryFn: () => studiesApi.get(studyId, token!),
    enabled: !!token,
  });

  const activeSection = useMemo(
    () => sections.find((section) => section.number === activeSectionId) ?? null,
    [sections, activeSectionId]
  );

  async function handleRegenerate(sectionId: string) {
    setActionError(null);
    try {
      await regenerateSection({ sectionId });
    } catch (err) {
      setActionError(
        getApiErrorMessage(err, "Section regeneration failed.")
      );
    }
  }

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <div className="flex items-center gap-2 mb-2">
          <Link
            href={`/studies/${studyId}/artifacts`}
            className="text-slate-400 hover:text-slate-700 text-sm transition-colors"
          >
            ← Artifacts
          </Link>
          {artifact ? (
            <Link
              href={`/studies/${studyId}/artifacts/${artifactId}`}
              className="text-slate-400 hover:text-slate-700 text-sm transition-colors"
            >
              / CSR detail
            </Link>
          ) : null}
        </div>

        {isLoading ? (
          <div className="space-y-2">
            <div className="h-4 w-40 bg-slate-100 animate-pulse rounded-sm" />
            <div className="h-7 w-96 bg-slate-100 animate-pulse rounded-sm" />
          </div>
        ) : artifact ? (
          <div className="flex items-start justify-between gap-6">
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-xs px-2 py-0.5 bg-slate-100 text-slate-600 font-medium">
                  CSR
                </span>
                <span
                  className={`text-xs px-2 py-0.5 font-medium ${
                    STATUS_COLORS[artifact.status] ?? "bg-slate-100 text-slate-600"
                  }`}
                >
                  {artifact.status.replace("_", " ")}
                </span>
                <span className="text-xs font-mono text-slate-400">
                  v{artifact.current_version_number}
                </span>
                {readOnly ? (
                  <span className="text-xs px-2 py-0.5 bg-slate-100 text-slate-500 font-medium">
                    Read-only
                  </span>
                ) : null}
              </div>
              <h1 className="font-display text-xl font-bold text-slate-900">
                {artifact.name}
              </h1>
              <p className="text-slate-500 text-sm mt-1">
                {study?.short_name ?? study?.name ?? "Study"} — ICH E3 section editor
                {content?.title ? ` · ${content.title}` : ""}
              </p>
            </div>
            <div className="text-right shrink-0">
              {saveStatus === "saving" ? (
                <p className="text-xs text-slate-500">Saving…</p>
              ) : saveStatus === "saved" ? (
                <p className="text-xs text-emerald-600">All changes saved</p>
              ) : (
                <p className="text-xs text-slate-400">Edits autosave on blur</p>
              )}
            </div>
          </div>
        ) : (
          <h1 className="font-display text-xl font-bold text-slate-900">
            CSR Section Editor
          </h1>
        )}
      </div>

      <div className="px-8 py-6">
        {actionError || saveError ? (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 mb-4">
            {actionError ?? saveError}
          </div>
        ) : null}

        {isError ? (
          <div className="bg-white border border-slate-200 px-8 py-14 text-center">
            <p className="font-display font-semibold text-slate-900 mb-1">
              Unable to load CSR editor
            </p>
            <p className="text-slate-500 text-sm">
              {getApiErrorMessage(error, "An unexpected error occurred.")}
            </p>
          </div>
        ) : !guard.ready && !isLoading ? (
          <div className="bg-white border border-slate-200 px-8 py-14 text-center">
            <p className="font-display font-semibold text-slate-900 mb-1">
              Unable to open CSR editor
            </p>
            <p className="text-slate-500 text-sm">{guard.message}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 items-start">
            <div className="xl:col-span-3">
              {isLoading ? (
                <CSROutlineNavigatorSkeleton />
              ) : (
                <CSROutlineNavigator
                  sections={sections}
                  activeSectionId={activeSectionId}
                  onSelect={setActiveSectionId}
                />
              )}
            </div>

            <div className="xl:col-span-6">
              {isLoading ? (
                <CSRSectionEditorSkeleton />
              ) : (
                <CSRSectionEditor
                  sections={sections}
                  activeSectionId={activeSectionId}
                  readOnly={readOnly}
                  onSectionProseChange={updateSectionProse}
                  onSectionBlur={handleSectionBlur}
                  onRegenerate={handleRegenerate}
                  regeneratingSectionId={
                    isRegenerating ? regeneratingSectionId : null
                  }
                />
              )}
            </div>

            <div className="xl:col-span-3">
              {isLoading ? (
                <CSRTLFReferencePanelSkeleton />
              ) : (
                <CSRTLFReferencePanel
                  studyId={studyId}
                  content={content}
                  activeSection={activeSection}
                />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
