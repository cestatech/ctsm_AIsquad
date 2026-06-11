"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, PackageCheck } from "lucide-react";
import { ReadinessChecklist, ReadinessChecklistSkeleton } from "@/components/submission/ReadinessChecklist";
import type { ReadinessItemModel, ReadinessStatus } from "@/components/submission/ReadinessChecklist";
import { PackagePanel } from "@/components/submission/PackagePanel";
import { adamApi } from "@/lib/api/adam";
import { artifactsApi } from "@/lib/api/artifacts";
import { csrApi } from "@/lib/api/csr";
import { ApiClientError } from "@/lib/api/client";
import { getApiErrorMessage } from "@/lib/api/errors";
import { intelligenceApi } from "@/lib/api/intelligence";
import { studiesApi } from "@/lib/api/studies";
import { submissionsApi } from "@/lib/api/submissions";
import { useStudyPermissions } from "@/hooks/useStudyPermissions";
import { shouldPollPackage } from "@/lib/submissionStatus";
import { useAuthStore } from "@/store/authStore";
import type { Artifact, ArtifactType } from "@/types";

function getArtifactStatus(artifacts: Artifact[], artifactType: ArtifactType): ReadinessStatus {
  const matching = artifacts.filter((artifact) => artifact.artifact_type === artifactType);

  if (matching.some((artifact) => artifact.status === "APPROVED" || artifact.status === "LOCKED")) {
    return "complete";
  }

  return matching.length > 0 ? "warning" : "missing";
}

function statusResolution(status: ReadinessStatus, complete: string, warning: string, missing: string) {
  if (status === "complete") return complete;
  if (status === "warning") return warning;
  return missing;
}

export default function SubmissionReadinessPage({ params }: { params: { id: string } }) {
  const studyId = params.id;
  const { token } = useAuthStore();
  const perms = useStudyPermissions(studyId);
  const queryClient = useQueryClient();
  const [createError, setCreateError] = useState<string | null>(null);
  const [notReadyIssues, setNotReadyIssues] = useState<string[]>([]);

  const { data: study, isLoading: studyLoading } = useQuery({
    queryKey: ["study", studyId, token],
    queryFn: () => studiesApi.get(studyId, token!),
    enabled: !!token,
  });

  const { data: backendReadiness, isLoading: backendReadinessLoading } = useQuery({
    queryKey: ["submission-readiness", studyId, token],
    queryFn: () => submissionsApi.getReadiness(studyId, token!),
    enabled: !!token,
  });

  const { data: packagesData, isLoading: packagesLoading } = useQuery({
    queryKey: ["submission-packages", studyId, token],
    queryFn: () => submissionsApi.listForStudy(studyId, token!),
    enabled: !!token,
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      const latest = items[0];
      if (!latest) return false;
      return shouldPollPackage(latest) ? 5000 : false;
    },
  });

  const { data: artifactsData, isLoading: artifactsLoading } = useQuery({
    queryKey: ["artifacts", studyId, token],
    queryFn: () => artifactsApi.list({ study_id: studyId, page_size: 100 }, token!),
    enabled: !!token,
  });

  const { data: adamReadiness, isLoading: adamLoading } = useQuery({
    queryKey: ["submission-adam-readiness", studyId, token],
    queryFn: () => adamApi.getStudyReadiness(studyId, token!),
    enabled: !!token,
  });

  const { data: csrReadiness, isLoading: csrLoading } = useQuery({
    queryKey: ["submission-csr-readiness", studyId, token],
    queryFn: () => csrApi.getStudyReadiness(studyId, token!),
    enabled: !!token,
  });

  const { data: validationFailures, isLoading: validationFailuresLoading } = useQuery({
    queryKey: ["submission-validation-failures", studyId, token],
    queryFn: () =>
      intelligenceApi.listValidationEvidence(
        { study_id: studyId, evidence_status: "FAIL", page_size: 1 },
        token!
      ),
    enabled: !!token,
  });

  const { data: validationWarnings, isLoading: validationWarningsLoading } = useQuery({
    queryKey: ["submission-validation-warnings", studyId, token],
    queryFn: () =>
      intelligenceApi.listValidationEvidence(
        { study_id: studyId, evidence_status: "WARNING", page_size: 1 },
        token!
      ),
    enabled: !!token,
  });

  const { data: pendingDecisions, isLoading: pendingDecisionsLoading } = useQuery({
    queryKey: ["submission-pending-ai-decisions", studyId, token],
    queryFn: () =>
      intelligenceApi.listDecisions(
        { study_id: studyId, decision_status: "PENDING_REVIEW", page_size: 1 },
        token!
      ),
    enabled: !!token,
  });

  const createMutation = useMutation({
    mutationFn: () => submissionsApi.createPackage(studyId, token!),
    onMutate: () => {
      setCreateError(null);
      setNotReadyIssues([]);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["submission-packages", studyId] });
      queryClient.invalidateQueries({ queryKey: ["submission-readiness", studyId] });
    },
    onError: (err) => {
      setCreateError(getApiErrorMessage(err, "Failed to create submission package."));
      if (err instanceof ApiClientError) {
        const detail = err.error.detail;
        if (detail && typeof detail === "object" && Array.isArray(detail.issues)) {
          setNotReadyIssues(detail.issues);
        }
      }
    },
  });

  const isLoading =
    studyLoading ||
    backendReadinessLoading ||
    packagesLoading ||
    artifactsLoading ||
    adamLoading ||
    csrLoading ||
    validationFailuresLoading ||
    validationWarningsLoading ||
    pendingDecisionsLoading;

  const artifacts = artifactsData?.items ?? [];
  const sdtmArtifactStatus = getArtifactStatus(artifacts, "SDTM_DATASET");
  const adamArtifactStatus = getArtifactStatus(artifacts, "ADAM_DATASET");
  const tlfArtifactStatus = getArtifactStatus(artifacts, "TLF");
  const csrArtifactStatus = getArtifactStatus(artifacts, "CSR");

  const sdtmStatus: ReadinessStatus =
    sdtmArtifactStatus === "complete" && adamReadiness?.ready === false
      ? "warning"
      : sdtmArtifactStatus;

  const validationFailureCount = validationFailures?.total ?? 0;
  const validationWarningCount = validationWarnings?.total ?? 0;
  const validationStatus: ReadinessStatus =
    validationFailureCount > 0 ? "missing" : validationWarningCount > 0 ? "warning" : "complete";

  const pendingDecisionCount = pendingDecisions?.total ?? 0;
  const aiReviewStatus: ReadinessStatus = pendingDecisionCount > 0 ? "missing" : "complete";

  const items: ReadinessItemModel[] = [
    {
      id: "sdtm-approved",
      category: "SDTM",
      label: "SDTM dataset generated and approved",
      description:
        adamReadiness?.ready === false && adamReadiness.issues.length > 0
          ? adamReadiness.issues[0]
          : `${adamReadiness?.sdtm_artifact_count ?? 0} SDTM artifact(s) available for downstream ADaM readiness.`,
      status: sdtmStatus,
      resolution: statusResolution(
        sdtmStatus,
        "Approved SDTM dataset is ready for submission packaging.",
        "Resolve the ADaM readiness issue before packaging.",
        "Generate the SDTM package and move it through approval."
      ),
    },
    {
      id: "define-xml",
      category: "SDTM",
      label: "define.xml available",
      description: "An approved SDTM dataset is required before define.xml can be included.",
      status: sdtmArtifactStatus,
      resolution: statusResolution(
        sdtmArtifactStatus,
        "Approved SDTM package can supply define.xml metadata.",
        "Finish review for the SDTM package.",
        "Create and approve an SDTM dataset artifact."
      ),
    },
    {
      id: "adam-approved",
      category: "ADaM",
      label: "ADaM dataset generated and approved",
      description:
        adamArtifactStatus === "complete"
          ? "Approved ADaM analysis dataset is available."
          : "ADaM depends on approved SDTM inputs and an approved ADaM artifact.",
      status: adamArtifactStatus,
      resolution: statusResolution(
        adamArtifactStatus,
        "Approved ADaM package is ready.",
        "Complete review and approval for the ADaM artifact.",
        "Generate ADaM from the approved SDTM package and submit it for approval."
      ),
    },
    {
      id: "tlf-approved",
      category: "TLF",
      label: "TLF package generated and approved",
      description: `${csrReadiness?.tlf_artifact_count ?? 0} TLF package(s) detected for CSR readiness.`,
      status: tlfArtifactStatus,
      resolution: statusResolution(
        tlfArtifactStatus,
        "Approved TLF package is ready for CSR and submission packaging.",
        "Complete review and approval for the TLF package.",
        "Generate tables, listings, and figures, then submit them for approval."
      ),
    },
    {
      id: "csr-approved",
      category: "CSR",
      label: "CSR generated and approved",
      description:
        csrReadiness?.ready === false && csrReadiness.issues.length > 0
          ? csrReadiness.issues[0]
          : "CSR readiness checks TLF, protocol, and SAP inputs before report assembly.",
      status: csrArtifactStatus,
      resolution: statusResolution(
        csrArtifactStatus,
        "Approved CSR is ready for regulatory package assembly.",
        "Complete review and approval for the CSR artifact.",
        "Assemble the CSR after TLF, protocol, and SAP prerequisites are ready."
      ),
    },
    {
      id: "validation-findings",
      category: "Validation",
      label: "0 open CDISC findings",
      description:
        validationFailureCount > 0
          ? `${validationFailureCount} failing CDISC validation finding(s) remain open.`
          : `${validationWarningCount} CDISC warning finding(s) remain open.`,
      status: validationStatus,
      resolution: statusResolution(
        validationStatus,
        "No failing or warning CDISC validation evidence is open.",
        "Review or waive warning findings before final packaging.",
        "Resolve or waive failing CDISC validation findings."
      ),
    },
    {
      id: "ai-decisions-reviewed",
      category: "Audit",
      label: "All AI decisions reviewed",
      description:
        pendingDecisionCount > 0
          ? `${pendingDecisionCount} AI decision(s) are still pending human review.`
          : "No AI decisions are pending review for this study.",
      status: aiReviewStatus,
      resolution: statusResolution(
        aiReviewStatus,
        "AI decision audit trail is fully reviewed.",
        "Review warning-level AI decision records.",
        "Accept, reject, or override all pending AI decisions."
      ),
    },
  ];

  const passingCount = items.filter((item) => item.status === "complete").length;
  const warningCount = items.filter((item) => item.status === "warning").length;
  const missingCount = items.filter((item) => item.status === "missing").length;
  const checklistReady = passingCount === items.length;
  const backendReady = backendReadiness?.ready === true;
  const canCreate =
    perms.canCreateSubmissionPackage && backendReady && !createMutation.isPending;
  const latestPackage = packagesData?.items?.[0] ?? null;

  return (
    <div>
      <div className="px-4 sm:px-8 py-5 border-b border-slate-200 bg-white">
        <div className="flex items-center gap-2 mb-1">
          <Link
            href={`/studies/${studyId}`}
            className="text-slate-400 hover:text-slate-700 text-sm transition-colors"
          >
            ← {study?.short_name ?? study?.name ?? "Study"}
          </Link>
        </div>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h1 className="font-display text-xl font-bold text-slate-900">
              Submission Readiness
            </h1>
            <p className="text-slate-500 text-sm mt-0.5">
              Backend readiness gates packaging. The checklist below is explanatory only.
            </p>
          </div>
        </div>
      </div>

      <div className="px-4 sm:px-8 py-6 space-y-6">
        <section className="bg-white border border-slate-200 p-5">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-start gap-3">
              <div className="h-10 w-10 bg-brand-50 text-brand-700 flex items-center justify-center">
                <PackageCheck className="h-5 w-5" />
              </div>
              <div>
                <p className="font-display text-lg font-semibold text-slate-900">
                  {backendReady
                    ? "Backend readiness: ready"
                    : "Backend readiness: not ready"}
                </p>
                <p className="mt-1 text-xs leading-relaxed text-slate-500">
                  Checklist: {passingCount} / {items.length} passing
                  {!checklistReady &&
                    ` (${warningCount} warning(s), ${missingCount} missing)`}
                  . Packaging requires backend approval of SDTM, ADaM, TLF, and CSR.
                </p>
              </div>
            </div>
            {perms.canCreateSubmissionPackage ? (
              <button
                type="button"
                disabled={!canCreate}
                onClick={() => createMutation.mutate()}
                title={
                  !backendReady
                    ? "Resolve backend readiness blockers before packaging"
                    : undefined
                }
                className="w-full md:w-auto bg-brand-600 text-white text-sm font-semibold font-display px-5 py-2.5 hover:bg-brand-700 disabled:bg-slate-200 disabled:text-slate-500 disabled:cursor-not-allowed"
              >
                {createMutation.isPending ? "Creating package…" : "Package Submission"}
              </button>
            ) : (
              <p className="text-sm text-slate-600 max-w-sm">
                Submission packaging requires the <strong>Admin</strong> role. You can
                track package status below.
              </p>
            )}
          </div>

          {!backendReady && backendReadiness?.issues && backendReadiness.issues.length > 0 && (
            <div className="mt-4 rounded border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              <p className="font-semibold">Backend blockers</p>
              <ul className="mt-2 list-disc pl-5 space-y-1">
                {backendReadiness.issues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            </div>
          )}

          {createError && (
            <div className="mt-4 rounded border border-red-200 bg-red-50 p-4 text-sm text-red-800">
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <div>
                  <p className="font-semibold">Could not create package</p>
                  <p className="mt-1">{createError}</p>
                  {notReadyIssues.length > 0 && (
                    <ul className="mt-2 list-disc pl-5 space-y-1">
                      {notReadyIssues.map((issue) => (
                        <li key={issue}>{issue}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </div>
          )}
        </section>

        {latestPackage && token && (
          <PackagePanel
            studyId={studyId}
            token={token}
            package={latestPackage}
            permissions={{
              canCreateSubmissionPackage: perms.canCreateSubmissionPackage,
              canViewSubmissionManifest: perms.canViewSubmissionManifest,
              canDownloadSubmissionPackage: perms.canDownloadSubmissionPackage,
            }}
            onRecreate={() => createMutation.mutate()}
            isRecreating={createMutation.isPending}
          />
        )}

        {isLoading ? <ReadinessChecklistSkeleton /> : <ReadinessChecklist items={items} />}
      </div>
    </div>
  );
}
