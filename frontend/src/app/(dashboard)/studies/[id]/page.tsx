"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { usePermissions } from "@/hooks/usePermissions";
import { studiesApi } from "@/lib/api/studies";
import { artifactsApi } from "@/lib/api/artifacts";

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
  DRAFT: "bg-slate-100 text-slate-700",
  ACTIVE: "bg-emerald-100 text-emerald-700",
  ON_HOLD: "bg-amber-100 text-amber-700",
  COMPLETED: "bg-blue-100 text-blue-700",
  ARCHIVED: "bg-slate-100 text-slate-500",
  TERMINATED: "bg-red-100 text-red-700",
};

const PHASE_LABELS: Record<string, string> = {
  PHASE_1: "Phase 1", PHASE_1_2: "Phase 1/2", PHASE_2: "Phase 2",
  PHASE_2_3: "Phase 2/3", PHASE_3: "Phase 3", PHASE_3_4: "Phase 3/4",
  PHASE_4: "Phase 4", OBSERVATIONAL: "Observational", OTHER: "Other",
};

const ROLE_COLORS: Record<string, string> = {
  ADMIN: "bg-brand-100 text-brand-700",
  CONTRIBUTOR: "bg-teal-100 text-teal-700",
  REVIEWER: "bg-violet-100 text-violet-700",
};

const ARTIFACT_TYPE_LABELS: Record<string, string> = {
  PROTOCOL: "Protocol", ICF: "ICF", SAP: "SAP", EDC_CRF: "eCRF",
  TRACEABILITY_MATRIX: "Traceability", SDTM_DATASET: "SDTM",
  ADAM_DATASET: "ADaM", TLF: "TLF", VALIDATION_REPORT: "Validation",
  CSR: "CSR", SUBMISSION_PACKAGE: "Submission", OTHER: "Other",
};

export default function StudyWorkspacePage({ params }: { params: { id: string } }) {
  const { token, role } = useAuthStore();
  const perms = usePermissions(role);
  const studyId = params.id;

  const { data: study, isLoading: studyLoading } = useQuery({
    queryKey: ["study", studyId, token],
    queryFn: () => studiesApi.get(studyId, token!),
    enabled: !!token,
  });

  const { data: artifactsData } = useQuery({
    queryKey: ["artifacts", studyId, token],
    queryFn: () => artifactsApi.list({ study_id: studyId, page_size: 50 }, token!),
    enabled: !!token,
  });

  const { data: members } = useQuery({
    queryKey: ["study-members", studyId, token],
    queryFn: () => studiesApi.getMembers(studyId, token!),
    enabled: !!token,
  });

  if (studyLoading) {
    return (
      <div className="px-8 py-16 text-center text-slate-400 text-sm">Loading study…</div>
    );
  }

  if (!study) {
    return (
      <div className="px-8 py-16 text-center text-slate-400 text-sm">Study not found.</div>
    );
  }

  const artifacts = artifactsData?.items ?? [];
  const statusCounts = artifacts.reduce<Record<string, number>>((acc, a) => {
    acc[a.status] = (acc[a.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div>
      {/* Header */}
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <div className="flex items-center gap-3 mb-2">
          <Link href="/studies" className="text-slate-400 hover:text-slate-700 text-sm transition-colors">
            ← Studies
          </Link>
        </div>
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <span className="font-mono text-xs text-slate-500 bg-slate-100 px-2 py-0.5">
                {study.protocol_number}
              </span>
              <span className={`text-xs px-2 py-0.5 font-medium ${STUDY_STATUS_COLORS[study.status]}`}>
                {study.status.replace("_", " ")}
              </span>
              {study.phase && (
                <span className="text-xs px-2 py-0.5 bg-slate-100 text-slate-600 font-medium">
                  {PHASE_LABELS[study.phase] ?? study.phase}
                </span>
              )}
            </div>
            <h1 className="font-display text-xl font-bold text-slate-900">{study.name}</h1>
            {study.description && (
              <p className="text-slate-500 text-sm mt-1 max-w-2xl">{study.description}</p>
            )}
          </div>
          <div className="flex gap-2 flex-shrink-0 ml-6">
            <Link
              href={`/studies/${study.id}/intake`}
              className="border border-brand-600 text-brand-600 hover:bg-brand-50 text-sm font-semibold font-display px-4 py-2 transition-colors"
            >
              Intake
            </Link>
            <Link
              href={`/studies/${study.id}/artifacts`}
              className="bg-brand-600 hover:bg-brand-500 text-white text-sm font-semibold font-display px-4 py-2 transition-colors"
            >
              Artifacts
            </Link>
          </div>
        </div>
      </div>

      <div className="px-8 py-6 grid grid-cols-3 gap-6">
        {/* Left column: Details + Artifact summary */}
        <div className="col-span-2 space-y-6">
          {/* Artifact status overview */}
          {artifacts.length > 0 && (
            <div className="bg-white border border-slate-200">
              <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
                <h2 className="font-display font-semibold text-slate-900 text-sm">Artifacts</h2>
                <Link
                  href={`/studies/${study.id}/artifacts`}
                  className="text-xs text-brand-600 hover:text-brand-700 font-medium"
                >
                  View all ({artifactsData?.total ?? artifacts.length}) →
                </Link>
              </div>
              <div className="divide-y divide-slate-100">
                {artifacts.slice(0, 6).map((artifact) => (
                  <Link
                    key={artifact.id}
                    href={`/studies/${study.id}/artifacts/${artifact.id}`}
                    className="flex items-center justify-between px-5 py-3 hover:bg-slate-50 transition-colors group"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-900 truncate group-hover:text-brand-700">
                        {artifact.name}
                      </p>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {ARTIFACT_TYPE_LABELS[artifact.artifact_type] ?? artifact.artifact_type}
                        {" · "}v{artifact.current_version_number}
                      </p>
                    </div>
                    <span
                      className={`flex-shrink-0 ml-3 text-xs px-2 py-0.5 font-medium ${
                        ARTIFACT_STATUS_COLORS[artifact.status]
                      }`}
                    >
                      {artifact.status.replace("_", " ")}
                    </span>
                  </Link>
                ))}
              </div>
              {perms.canCreateArtifact && (
                <div className="px-5 py-3 border-t border-slate-100">
                  <Link
                    href={`/studies/${study.id}/artifacts?new=1`}
                    className="text-xs text-brand-600 hover:text-brand-700 font-medium"
                  >
                    + New artifact
                  </Link>
                </div>
              )}
            </div>
          )}

          {artifacts.length === 0 && (
            <div className="bg-white border border-slate-200 px-8 py-12 text-center">
              <p className="font-display font-semibold text-slate-900 mb-2">No artifacts yet</p>
              <p className="text-slate-500 text-sm mb-5">
                Artifacts are versioned documents like protocols, ICFs, and SAPs.
              </p>
              {perms.canCreateArtifact && (
                <Link
                  href={`/studies/${study.id}/artifacts?new=1`}
                  className="bg-brand-600 hover:bg-brand-500 text-white text-sm font-semibold font-display px-5 py-2.5 transition-colors"
                >
                  Create first artifact
                </Link>
              )}
            </div>
          )}

          {/* Artifact Status Summary */}
          {artifacts.length > 0 && (
            <div className="grid grid-cols-4 gap-px bg-slate-200 border border-slate-200">
              {[
                { label: "Draft", key: "DRAFT", color: "text-slate-700" },
                { label: "In Review", key: "IN_REVIEW", color: "text-amber-700" },
                { label: "Approved", key: "APPROVED", color: "text-emerald-700" },
                { label: "Locked", key: "LOCKED", color: "text-blue-700" },
              ].map(({ label, key, color }) => (
                <div key={key} className="bg-white px-5 py-4">
                  <p className={`font-display text-xl font-bold ${color}`}>{statusCounts[key] ?? 0}</p>
                  <p className="text-slate-500 text-xs mt-1">{label}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right column: Study details + Members */}
        <div className="space-y-4">
          {/* Study Details */}
          <div className="bg-white border border-slate-200 p-5">
            <h3 className="font-display font-semibold text-slate-900 text-sm mb-4">Study Details</h3>
            <dl className="space-y-3 text-xs">
              {[
                { label: "Therapeutic Area", value: study.therapeutic_area },
                { label: "Indication", value: study.indication },
                { label: "Sponsor", value: study.sponsor },
                {
                  label: "Timeline",
                  value: study.start_date
                    ? `${study.start_date} → ${study.end_date ?? "TBD"}`
                    : null,
                },
                {
                  label: "Regions",
                  value: study.regulatory_region?.join(", "),
                },
              ]
                .filter((d) => d.value)
                .map((d) => (
                  <div key={d.label}>
                    <dt className="text-slate-400 mb-0.5">{d.label}</dt>
                    <dd className="text-slate-700 font-medium">{d.value}</dd>
                  </div>
                ))}
            </dl>
          </div>

          {/* Team Members */}
          <div className="bg-white border border-slate-200 p-5">
            <h3 className="font-display font-semibold text-slate-900 text-sm mb-4">
              Team ({members?.length ?? 0})
            </h3>
            <div className="space-y-2.5">
              {(members ?? []).map((member) => (
                <div key={member.id} className="flex items-center gap-2.5">
                  <div className="w-7 h-7 bg-slate-200 flex items-center justify-center flex-shrink-0">
                    <span className="text-slate-600 text-xs font-semibold">
                      {member.user.full_name.charAt(0).toUpperCase()}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-slate-900 truncate">{member.user.full_name}</p>
                    <p className="text-[11px] text-slate-400 truncate">{member.user.email}</p>
                  </div>
                  <span className={`text-[10px] px-1.5 py-0.5 font-medium flex-shrink-0 ${ROLE_COLORS[member.role]}`}>
                    {member.role}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
