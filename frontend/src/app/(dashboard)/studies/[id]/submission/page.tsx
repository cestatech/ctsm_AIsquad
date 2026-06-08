"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { PackageCheck } from "lucide-react";
import { ReadinessChecklist, ReadinessChecklistSkeleton } from "@/components/submission/ReadinessChecklist";
import type { ReadinessItemModel, ReadinessStatus } from "@/components/submission/ReadinessChecklist";
import { adamApi } from "@/lib/api/adam";
import { artifactsApi } from "@/lib/api/artifacts";
import { csrApi } from "@/lib/api/csr";
import { intelligenceApi } from "@/lib/api/intelligence";
import { studiesApi } from "@/lib/api/studies";
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

  const { data: study, isLoading: studyLoading } = useQuery({
    queryKey: ["study", studyId, token],
    queryFn: () => studiesApi.get(studyId, token!),
    enabled: !!token,
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

  const isLoading =
    studyLoading ||
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
  const allReady = passingCount === items.length;

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
              Checklist for regulatory package readiness across data, outputs, validation, and audit gates.
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
                  {passingCount} / {items.length} checks passing
                </p>
                <p className="mt-1 text-xs leading-relaxed text-slate-500">
                  {allReady
                    ? "All frontend readiness checks are passing."
                    : `${warningCount} warning(s) and ${missingCount} missing gate(s) need attention before packaging.`}
                </p>
              </div>
            </div>
            {/* TODO: wire to Phase 8 API */}
            <button
              type="button"
              disabled
              title="Backend coming soon"
              className="w-full md:w-auto bg-slate-200 text-slate-500 text-sm font-semibold font-display px-5 py-2.5 cursor-not-allowed"
            >
              Package Submission
            </button>
          </div>
        </section>

        {isLoading ? <ReadinessChecklistSkeleton /> : <ReadinessChecklist items={items} />}
      </div>
    </div>
  );
}
