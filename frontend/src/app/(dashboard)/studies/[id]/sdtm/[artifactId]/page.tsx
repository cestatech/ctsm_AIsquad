"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { useSDTMReview, useSDTMArtifactGuard } from "@/hooks/useSDTMReview";
import { useStudyPermissions } from "@/hooks/useStudyPermissions";
import { getApiErrorMessage } from "@/lib/api/errors";
import { defaultSdtmDomainCode } from "@/lib/api/sdtm";
import { studiesApi } from "@/lib/api/studies";
import {
  SDTMApprovalActions,
  SDTMApprovalActionsSkeleton,
} from "@/components/sdtm/SDTMApprovalActions";
import {
  SDTMDomainTabs,
  SDTMDomainTabsSkeleton,
} from "@/components/sdtm/SDTMDomainTabs";
import {
  SDTMValidationPanel,
  SDTMValidationPanelSkeleton,
} from "@/components/sdtm/SDTMValidationPanel";
import {
  SDTMVariableTable,
  SDTMVariableTableSkeleton,
} from "@/components/sdtm/SDTMVariableTable";

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-slate-100 text-slate-600",
  IN_REVIEW: "bg-amber-100 text-amber-700",
  APPROVED: "bg-emerald-100 text-emerald-700",
  REJECTED: "bg-red-100 text-red-700",
  LOCKED: "bg-blue-100 text-blue-700",
  AMENDED: "bg-purple-100 text-purple-700",
  SUPERSEDED: "bg-slate-100 text-slate-500",
};

export default function SDTMReviewPage({
  params,
}: {
  params: { id: string; artifactId: string };
}) {
  const studyId = params.id;
  const artifactId = params.artifactId;
  const { token } = useAuthStore();
  const perms = useStudyPermissions(studyId);
  const [activeDomain, setActiveDomain] = useState("");
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const {
    artifact,
    content,
    validationEvidence,
    isLoading,
    submitForReview,
    isSubmitting,
    recordApproval,
    isRecordingApproval,
    downloadDefineXml,
    isDownloadingDefineXml,
  } = useSDTMReview(studyId, artifactId);

  const guard = useSDTMArtifactGuard(artifact, isLoading);

  const { data: study } = useQuery({
    queryKey: ["study", studyId, token],
    queryFn: () => studiesApi.get(studyId, token!),
    enabled: !!token,
  });

  const domains = content?.domains ?? [];

  useEffect(() => {
    if (domains.length === 0) {
      setActiveDomain("");
      return;
    }
    setActiveDomain((current) => {
      if (current && domains.some((domain) => domain.domain === current)) {
        return current;
      }
      return defaultSdtmDomainCode(domains);
    });
  }, [domains]);

  const activeDomainData = useMemo(
    () => domains.find((domain) => domain.domain === activeDomain),
    [domains, activeDomain]
  );

  async function handleDefineXmlDownload() {
    setDownloadError(null);
    try {
      await downloadDefineXml();
    } catch (err) {
      setDownloadError(getApiErrorMessage(err, "define.xml download failed."));
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
              / Generic detail
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
                  SDTM Dataset
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
              </div>
              <h1 className="font-display text-xl font-bold text-slate-900">
                {artifact.name}
              </h1>
              <p className="text-slate-500 text-sm mt-1">
                {study?.short_name ?? study?.name ?? "Study"} — SDTM domain review
                {content?.sdtm_ig_version
                  ? ` (IG ${content.sdtm_ig_version})`
                  : ""}
              </p>
            </div>
            <button
              type="button"
              onClick={handleDefineXmlDownload}
              disabled={isDownloadingDefineXml || !guard.ready}
              className="shrink-0 border border-slate-200 text-slate-700 hover:border-brand-300 hover:text-brand-700 text-sm font-medium px-4 py-2 transition-colors disabled:opacity-50"
            >
              {isDownloadingDefineXml ? "Downloading…" : "Download define.xml"}
            </button>
          </div>
        ) : (
          <h1 className="font-display text-xl font-bold text-slate-900">
            SDTM Review
          </h1>
        )}
      </div>

      <div className="px-8 py-6 space-y-4">
        {downloadError ? (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3">
            {downloadError}
          </div>
        ) : null}

        {!guard.ready && !isLoading ? (
          <div className="bg-white border border-slate-200 px-8 py-14 text-center">
            <p className="font-display font-semibold text-slate-900 mb-1">
              Unable to open SDTM review
            </p>
            <p className="text-slate-500 text-sm">{guard.message}</p>
          </div>
        ) : (
          <>
            {isLoading ? (
              <SDTMDomainTabsSkeleton />
            ) : (
              <SDTMDomainTabs
                domains={domains}
                activeDomain={activeDomain}
                onSelect={setActiveDomain}
              />
            )}

            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
              <div className="xl:col-span-2 space-y-4">
                {isLoading || !content ? (
                  <SDTMVariableTableSkeleton />
                ) : (
                  <SDTMVariableTable domain={activeDomainData} content={content} />
                )}
              </div>

              <div className="space-y-4">
                {isLoading ? (
                  <>
                    <SDTMValidationPanelSkeleton />
                    <SDTMApprovalActionsSkeleton />
                  </>
                ) : (
                  <>
                    <SDTMValidationPanel
                      evidence={validationEvidence}
                      activeDomain={activeDomain}
                    />
                    {artifact ? (
                      <SDTMApprovalActions
                        artifact={artifact}
                        permissions={perms}
                        onSubmit={submitForReview}
                        onApprove={(comments) =>
                          recordApproval({
                            decision: "APPROVED",
                            comments,
                            versionId: artifact.current_version_id!,
                          })
                        }
                        onReject={(comments) =>
                          recordApproval({
                            decision: "REJECTED",
                            comments,
                            versionId: artifact.current_version_id!,
                          })
                        }
                        isSubmitting={isSubmitting}
                        isRecordingApproval={isRecordingApproval}
                      />
                    ) : null}
                  </>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
