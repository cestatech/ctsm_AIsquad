"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { useStudyPermissions } from "@/hooks/useStudyPermissions";
import { studiesApi } from "@/lib/api/studies";
import { artifactsApi } from "@/lib/api/artifacts";
import { uploadsApi } from "@/lib/api/uploads";
import { getApiErrorMessage } from "@/lib/api/errors";
import { rawDataApi } from "@/lib/api/rawData";
import { adamApi } from "@/lib/api/adam";
import { csrApi } from "@/lib/api/csr";
import { graphApi } from "@/lib/api/graph";
import { intakeApi } from "@/lib/api/intake";
import { generationApi } from "@/lib/api/generation";
import { intelligenceApi } from "@/lib/api/intelligence";
import type { UploadedFile } from "@/types";

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

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function StudyWorkspacePage({ params }: { params: { id: string } }) {
  const studyId = params.id;
  const { token } = useAuthStore();
  const perms = useStudyPermissions(studyId);
  const queryClient = useQueryClient();
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

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

  const { data: graphSummary } = useQuery({
    queryKey: ["study-graph-summary", studyId, token],
    queryFn: () => graphApi.getStudySummary(studyId, token!),
    enabled: !!token && !!studyId,
  });

  const { data: intakeSessions } = useQuery({
    queryKey: ["intakes", studyId, token],
    queryFn: () => intakeApi.list(studyId, token!),
    enabled: !!token,
  });

  const { data: members } = useQuery({
    queryKey: ["study-members", studyId, token],
    queryFn: () => studiesApi.getMembers(studyId, token!),
    enabled: !!token,
  });

  const { data: uploadsData } = useQuery({
    queryKey: ["uploads", studyId, token],
    queryFn: () => uploadsApi.list(studyId, token!),
    enabled: !!token,
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadsApi.upload(studyId, file, undefined, token!),
    onSuccess: () => {
      setUploadError(null);
      queryClient.invalidateQueries({ queryKey: ["uploads", studyId] });
      queryClient.invalidateQueries({ queryKey: ["sdtm-readiness", studyId] });
    },
    onError: (err) => setUploadError(getApiErrorMessage(err, "Upload failed.")),
  });

  const { data: sdtmReadiness } = useQuery({
    queryKey: ["sdtm-readiness", studyId, token],
    queryFn: () => rawDataApi.getStudySdtmReadiness(studyId, token!),
    enabled: !!token && (uploadsData?.total ?? 0) > 0,
  });

  const hasSdtmArtifacts = (artifactsData?.items ?? []).some(
    (a) => a.artifact_type === "SDTM_DATASET"
  );
  const hasTlfArtifacts = (artifactsData?.items ?? []).some(
    (a) => a.artifact_type === "TLF"
  );

  const latestIntake = intakeSessions?.[0] ?? null;
  const compiledIntake =
    intakeSessions?.find((session) => session.status === "COMPILED") ?? null;
  const intakeCompiled = !!compiledIntake;
  const intakeDomains = latestIntake?.domains_completed.length ?? 0;
  const hasProtocol = (artifactsData?.items ?? []).some((a) => a.artifact_type === "PROTOCOL");
  const hasIcf = (artifactsData?.items ?? []).some((a) => a.artifact_type === "ICF");
  const hasSap = (artifactsData?.items ?? []).some((a) => a.artifact_type === "SAP");
  const hasEdc = (artifactsData?.items ?? []).some((a) => a.artifact_type === "EDC_CRF");
  const protocolArtifact = (artifactsData?.items ?? []).find((a) => a.artifact_type === "PROTOCOL");
  const sapArtifact = (artifactsData?.items ?? []).find((a) => a.artifact_type === "SAP");

  const { data: studyBrief } = useQuery({
    queryKey: ["study-brief", compiledIntake?.id, token],
    queryFn: () => intakeApi.getBrief(compiledIntake!.id, token!),
    enabled: !!compiledIntake && !!token,
  });

  const [syntheticN, setSyntheticN] = useState(50);
  const [syntheticSeed, setSyntheticSeed] = useState(42);
  const [generationError, setGenerationError] = useState<string | null>(null);

  const { data: adamReadiness } = useQuery({
    queryKey: ["adam-readiness", studyId, token],
    queryFn: () => adamApi.getStudyReadiness(studyId, token!),
    enabled: !!token && hasSdtmArtifacts,
  });

  const generateStudyAdamMutation = useMutation({
    mutationFn: () => adamApi.generateFromStudy(studyId, token!),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["artifacts", studyId] });
      queryClient.invalidateQueries({ queryKey: ["adam-readiness", studyId] });
      router.push(`/studies/${studyId}/artifacts/${result.artifact_id}`);
    },
  });

  const { data: csrReadiness } = useQuery({
    queryKey: ["csr-readiness", studyId, token],
    queryFn: () => csrApi.getStudyReadiness(studyId, token!),
    enabled: !!token && hasTlfArtifacts,
  });

  const generateStudyCsrMutation = useMutation({
    mutationFn: () => csrApi.generateFromStudy(studyId, token!),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["artifacts", studyId] });
      queryClient.invalidateQueries({ queryKey: ["csr-readiness", studyId] });
      router.push(`/studies/${studyId}/artifacts/${result.artifact_id}`);
    },
  });

  const generateEdcMutation = useMutation({
    mutationFn: () =>
      generationApi.createJob(
        {
          study_id: studyId,
          artifact_type: "EDC_CRF",
          model_id: "deterministic",
          input_context: {
            protocol_artifact_id: protocolArtifact?.id,
            sap_artifact_id: sapArtifact?.id,
          },
        },
        token!
      ),
    onSuccess: () => {
      setGenerationError(null);
      queryClient.invalidateQueries({ queryKey: ["artifacts", studyId] });
      queryClient.invalidateQueries({ queryKey: ["generation-jobs", studyId] });
      router.push(`/studies/${studyId}/generation`);
    },
    onError: (err) => setGenerationError(getApiErrorMessage(err, "EDC generation failed.")),
  });

  const generateSapMutation = useMutation({
    mutationFn: () =>
      generationApi.generateFromBrief(
        {
          brief_id: studyBrief!.id,
          artifact_type: "SAP",
          model_id: "claude-sonnet-4-6",
        },
        token!
      ),
    onSuccess: () => {
      setGenerationError(null);
      queryClient.invalidateQueries({ queryKey: ["artifacts", studyId] });
      queryClient.invalidateQueries({ queryKey: ["generation-jobs", studyId] });
      router.push(`/studies/${studyId}/generation`);
    },
    onError: (err) => setGenerationError(getApiErrorMessage(err, "SAP generation failed.")),
  });

  const generateSyntheticMutation = useMutation({
    mutationFn: () =>
      intelligenceApi.createSyntheticRun(
        {
          study_id: studyId,
          target_n: syntheticN,
          random_seed: syntheticSeed,
        },
        token!
      ),
    onSuccess: (run) => {
      setGenerationError(null);
      queryClient.invalidateQueries({ queryKey: ["artifacts", studyId] });
      queryClient.invalidateQueries({ queryKey: ["synthetic-runs", studyId] });
      if (run.output_artifact_id) {
        router.push(`/studies/${studyId}/artifacts/${run.output_artifact_id}`);
      } else {
        router.push("/intelligence/synthetic");
      }
    },
    onError: (err) =>
      setGenerationError(getApiErrorMessage(err, "Synthetic data generation failed.")),
  });

  const generateStudySdtmMutation = useMutation({
    mutationFn: () => rawDataApi.generateStudySdtm(studyId, token!),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["artifacts", studyId] });
      queryClient.invalidateQueries({ queryKey: ["sdtm-readiness", studyId] });
      router.push(`/studies/${studyId}/artifacts/${result.artifact_id}`);
    },
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
              className="border border-slate-200 text-slate-700 hover:bg-slate-50 text-sm font-medium px-4 py-2 transition-colors"
            >
              Intake
            </Link>
            <Link
              href={`/studies/${study.id}/generation`}
              className="border border-slate-200 text-slate-700 hover:bg-slate-50 text-sm font-medium px-4 py-2 transition-colors"
            >
              Generation
            </Link>
            <Link
              href={`/studies/${study.id}/edc`}
              className="border border-slate-200 text-slate-700 hover:bg-slate-50 text-sm font-medium px-4 py-2 transition-colors"
            >
              EDC Screens
            </Link>
            <Link
              href={`/studies/${study.id}/generated-data`}
              className="border border-slate-200 text-slate-700 hover:bg-slate-50 text-sm font-medium px-4 py-2 transition-colors"
            >
              Generated Data
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

      <div className="px-8 py-6 space-y-6">
        {perms.canTriggerGeneration &&
          (intakeCompiled || hasProtocol || hasEdc) && (
          <div className="bg-white border border-slate-200">
            <div className="px-5 py-4 border-b border-slate-100">
              <h2 className="font-display font-semibold text-slate-900 text-sm">AI Generation</h2>
              <p className="text-xs text-slate-500 mt-1">
                Generate SAP, EDC/eCRF, and synthetic data (after SAP). All runs appear in the context graph.
              </p>
            </div>
            <div className="divide-y divide-slate-100">
              {intakeCompiled && !hasSap && studyBrief && (
                <div className="px-5 py-4 flex items-start justify-between gap-4">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">Statistical Analysis Plan (SAP)</p>
                    <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                      Generate a draft SAP artifact from the compiled Study Brief.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => generateSapMutation.mutate()}
                    disabled={generateSapMutation.isPending}
                    className="shrink-0 text-xs bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white font-semibold px-4 py-2 transition-colors"
                  >
                    {generateSapMutation.isPending ? "Starting…" : "Generate SAP"}
                  </button>
                </div>
              )}
              {hasProtocol && !hasEdc && (
                <div className="px-5 py-4 flex items-start justify-between gap-4">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">EDC / eCRF specification</p>
                    <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                      Generate structured eCRF forms, fields, edit checks, and mock screens
                      {hasSap ? " from protocol and SAP." : " from the protocol."}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => generateEdcMutation.mutate()}
                    disabled={generateEdcMutation.isPending}
                    className="shrink-0 text-xs bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white font-semibold px-4 py-2 transition-colors"
                  >
                    {generateEdcMutation.isPending ? "Starting…" : "Generate EDC/eCRF"}
                  </button>
                </div>
              )}
              {hasSap && (
                <div className="px-5 py-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">Synthetic clinical data</p>
                      <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                        Generate reproducible patient-level CSV labeled SYNTHETIC from the SAP.
                        Also uses Protocol and EDC artifacts when available.
                      </p>
                    </div>
                    <div className="flex items-end gap-3 shrink-0">
                      <div>
                        <label className="block text-[10px] font-medium text-slate-500 mb-1">Subjects (N)</label>
                        <input
                          type="number"
                          min={1}
                          max={500}
                          value={syntheticN}
                          onChange={(e) => setSyntheticN(Number(e.target.value))}
                          className="w-20 border border-slate-200 px-2 py-1.5 text-xs text-slate-900 focus:outline-none focus:border-brand-500"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] font-medium text-slate-500 mb-1">Seed</label>
                        <input
                          type="number"
                          value={syntheticSeed}
                          onChange={(e) => setSyntheticSeed(Number(e.target.value))}
                          className="w-24 border border-slate-200 px-2 py-1.5 text-xs text-slate-900 focus:outline-none focus:border-brand-500"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={() => generateSyntheticMutation.mutate()}
                        disabled={generateSyntheticMutation.isPending}
                        className="text-xs bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white font-semibold px-4 py-2 transition-colors"
                      >
                        {generateSyntheticMutation.isPending ? "Generating…" : "Generate synthetic data"}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
            {generationError && (
              <div className="px-5 py-3 border-t border-red-100 bg-red-50 text-red-700 text-xs">
                {generationError}
              </div>
            )}
          </div>
        )}

        {(!hasProtocol || !hasIcf) && (
          <div className="bg-amber-50 border border-amber-200 px-5 py-4 flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-amber-900">
                {!intakeCompiled
                  ? `Sponsor intake incomplete (${intakeDomains}/9 domains)`
                  : "Study Brief compiled — generate Protocol & ICF"}
              </p>
              <p className="text-xs text-amber-800 mt-1 leading-relaxed">
                {!intakeCompiled
                  ? "Protocol and ICF are not created automatically. Finish all nine intake domains, compile the Study Brief, then generate each document from the brief."
                  : "Open intake to generate Protocol and ICF from the compiled Study Brief. Completed jobs appear under Artifacts and Generation."}
              </p>
              <p className="text-[11px] text-amber-700 mt-2">
                Protocol: {hasProtocol ? "generated" : "not yet"} · ICF: {hasIcf ? "generated" : "not yet"}
              </p>
            </div>
            <Link
              href={`/studies/${studyId}/intake`}
              className="shrink-0 text-xs bg-amber-600 hover:bg-amber-500 text-white font-semibold px-4 py-2 transition-colors"
            >
              {intakeCompiled ? "Generate documents" : "Continue intake"}
            </Link>
          </div>
        )}

      <div className="grid grid-cols-3 gap-6">
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
          {/* CSR pipeline */}
          {hasTlfArtifacts && (
            <div className="bg-white border border-slate-200">
              <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
                <h2 className="font-display font-semibold text-slate-900 text-sm">
                  CSR Assembly
                </h2>
                {csrReadiness?.ready && (
                  <span className="text-[11px] px-2 py-0.5 bg-orange-100 text-orange-700 font-medium">
                    Ready
                  </span>
                )}
              </div>
              <div className="px-5 py-4 space-y-3">
                {csrReadiness ? (
                  <>
                    <p className="text-xs text-slate-600">
                      {csrReadiness.tlf_artifact_count} TLF package(s) available for
                      ICH E3 CSR assembly.
                      {csrReadiness.protocol_artifact_count > 0 &&
                        ` Protocol context included.`}
                    </p>
                    {!csrReadiness.ready && csrReadiness.issues.length > 0 && (
                      <ul className="text-[11px] text-amber-700 bg-amber-50 border border-amber-100 px-3 py-2 space-y-0.5 list-disc list-inside">
                        {csrReadiness.issues.slice(0, 5).map((issue) => (
                          <li key={issue}>{issue}</li>
                        ))}
                      </ul>
                    )}
                    {perms.canCreateArtifact && (
                      <button
                        onClick={() => generateStudyCsrMutation.mutate()}
                        disabled={!csrReadiness.ready || generateStudyCsrMutation.isPending}
                        className="text-xs bg-orange-700 hover:bg-orange-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold px-4 py-2 transition-colors"
                      >
                        {generateStudyCsrMutation.isPending
                          ? "Assembling CSR…"
                          : "Generate Clinical Study Report"}
                      </button>
                    )}
                    {generateStudyCsrMutation.isError && (
                      <p className="text-[11px] text-red-600">
                        {getApiErrorMessage(
                          generateStudyCsrMutation.error,
                          "CSR generation failed."
                        )}
                      </p>
                    )}
                  </>
                ) : (
                  <p className="text-xs text-slate-400">Checking CSR readiness…</p>
                )}
              </div>
            </div>
          )}

          {/* ADaM pipeline */}
          {hasSdtmArtifacts && (
            <div className="bg-white border border-slate-200">
              <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
                <h2 className="font-display font-semibold text-slate-900 text-sm">
                  ADaM Generation
                </h2>
                {adamReadiness?.ready && (
                  <span className="text-[11px] px-2 py-0.5 bg-teal-100 text-teal-700 font-medium">
                    Ready
                  </span>
                )}
              </div>
              <div className="px-5 py-4 space-y-3">
                {adamReadiness ? (
                  <>
                    <p className="text-xs text-slate-600">
                      {adamReadiness.sdtm_artifact_count} SDTM artifact(s) available
                      for ADaM IG 1.3 derivation.
                    </p>
                    {!adamReadiness.ready && adamReadiness.issues.length > 0 && (
                      <ul className="text-[11px] text-amber-700 bg-amber-50 border border-amber-100 px-3 py-2 space-y-0.5 list-disc list-inside">
                        {adamReadiness.issues.slice(0, 5).map((issue) => (
                          <li key={issue}>{issue}</li>
                        ))}
                      </ul>
                    )}
                    {perms.canCreateArtifact && (
                      <button
                        onClick={() => generateStudyAdamMutation.mutate()}
                        disabled={!adamReadiness.ready || generateStudyAdamMutation.isPending}
                        className="text-xs bg-teal-700 hover:bg-teal-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold px-4 py-2 transition-colors"
                      >
                        {generateStudyAdamMutation.isPending
                          ? "Generating ADaM…"
                          : "Generate ADaM analysis package"}
                      </button>
                    )}
                    {generateStudyAdamMutation.isError && (
                      <p className="text-[11px] text-red-600">
                        {getApiErrorMessage(
                          generateStudyAdamMutation.error,
                          "ADaM generation failed."
                        )}
                      </p>
                    )}
                  </>
                ) : (
                  <p className="text-xs text-slate-400">Checking ADaM readiness…</p>
                )}
              </div>
            </div>
          )}

          {/* SDTM pipeline */}
          {(uploadsData?.total ?? 0) > 0 && (
            <div className="bg-white border border-slate-200">
              <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
                <h2 className="font-display font-semibold text-slate-900 text-sm">
                  SDTM Generation
                </h2>
                {sdtmReadiness?.ready && (
                  <span className="text-[11px] px-2 py-0.5 bg-emerald-100 text-emerald-700 font-medium">
                    Ready
                  </span>
                )}
              </div>
              <div className="px-5 py-4 space-y-3">
                {sdtmReadiness ? (
                  <>
                    <p className="text-xs text-slate-600">
                      {sdtmReadiness.approved_fields}/{sdtmReadiness.total_fields} fields approved
                      across {sdtmReadiness.dataset_count} dataset(s).
                    </p>
                    {!sdtmReadiness.ready && sdtmReadiness.issues.length > 0 && (
                      <ul className="text-[11px] text-amber-700 bg-amber-50 border border-amber-100 px-3 py-2 space-y-0.5 list-disc list-inside">
                        {sdtmReadiness.issues.slice(0, 5).map((issue) => (
                          <li key={issue}>{issue}</li>
                        ))}
                      </ul>
                    )}
                    {perms.canCreateArtifact && (
                      <button
                        onClick={() => generateStudySdtmMutation.mutate()}
                        disabled={!sdtmReadiness.ready || generateStudySdtmMutation.isPending}
                        className="text-xs bg-brand-600 hover:bg-brand-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold px-4 py-2 transition-colors"
                      >
                        {generateStudySdtmMutation.isPending
                          ? "Generating full-study SDTM…"
                          : "Generate full-study SDTM package"}
                      </button>
                    )}
                    {generateStudySdtmMutation.isError && (
                      <p className="text-[11px] text-red-600">
                        {getApiErrorMessage(
                          generateStudySdtmMutation.error,
                          "SDTM generation failed."
                        )}
                      </p>
                    )}
                  </>
                ) : (
                  <p className="text-xs text-slate-400">Checking mapping readiness…</p>
                )}
              </div>
            </div>
          )}

          {/* File Uploads */}
          <div className="bg-white border border-slate-200">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
              <h2 className="font-display font-semibold text-slate-900 text-sm">
                Uploaded Files{uploadsData && uploadsData.total > 0 && (
                  <span className="ml-1.5 text-xs text-slate-400 font-normal">({uploadsData.total})</span>
                )}
              </h2>
              <div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.xlsx,.xls,.pdf,.txt"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) uploadMutation.mutate(file);
                    e.target.value = "";
                  }}
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploadMutation.isPending}
                  className="text-xs border border-slate-200 text-slate-600 hover:bg-slate-50 px-3 py-1.5 transition-colors disabled:opacity-50"
                >
                  {uploadMutation.isPending ? "Uploading…" : "+ Upload file"}
                </button>
              </div>
            </div>
            {uploadError && (
              <div className="mx-5 mt-3 bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2">{uploadError}</div>
            )}
            <div className="divide-y divide-slate-100">
              {(uploadsData?.items ?? []).length === 0 ? (
                <p className="px-5 py-4 text-xs text-slate-400">
                  No files uploaded. Upload CSV or XLSX metadata files to attach data to this study.
                </p>
              ) : (
                (uploadsData?.items ?? []).map((f: UploadedFile) => (
                  <div key={f.id} className="px-5 py-3 flex items-center gap-3">
                    <div className="w-7 h-7 bg-slate-100 flex items-center justify-center flex-shrink-0 text-slate-500">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-slate-900 truncate">{f.original_filename}</p>
                      <p className="text-[11px] text-slate-400">
                        {formatBytes(f.file_size_bytes)} · {f.mime_type}
                        {typeof f.extracted_metadata?.row_count === "number" && (
                          <> · {f.extracted_metadata.row_count} rows</>
                        )}
                      </p>
                    </div>
                    <span className="text-[11px] text-slate-400 flex-shrink-0">
                      {new Date(f.created_at).toLocaleDateString()}
                    </span>
                    <Link
                      href={`/studies/${studyId}/uploads/${f.id}`}
                      className="text-[11px] text-brand-600 hover:text-brand-700 font-medium flex-shrink-0"
                      onClick={(e) => e.stopPropagation()}
                    >
                      View →
                    </Link>
                  </div>
                ))
              )}
            </div>
          </div>
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

          {/* Context Graph Summary */}
          <div className="bg-white border border-slate-200 p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-display font-semibold text-slate-900 text-sm">
                Context Graph
              </h3>
              <Link
                href={`/intelligence/graph?study=${studyId}`}
                className="text-[11px] text-brand-600 hover:text-brand-700 font-medium"
              >
                Explorer →
              </Link>
            </div>
            {graphSummary ? (
              <dl className="space-y-3 text-xs">
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { label: "Nodes", value: graphSummary.node_count },
                    { label: "Edges", value: graphSummary.edge_count },
                    { label: "Events", value: graphSummary.event_count },
                  ].map((stat) => (
                    <div key={stat.label} className="bg-slate-50 px-2 py-2 text-center">
                      <dt className="text-[10px] text-slate-400 uppercase">{stat.label}</dt>
                      <dd className="text-sm font-semibold text-slate-800">{stat.value}</dd>
                    </div>
                  ))}
                </div>
                {Object.keys(graphSummary.nodes_by_type).length > 0 && (
                  <div>
                    <dt className="text-slate-400 mb-1">By type</dt>
                    <dd className="text-slate-600 space-y-0.5">
                      {Object.entries(graphSummary.nodes_by_type)
                        .slice(0, 5)
                        .map(([type, count]) => (
                          <div key={type} className="flex justify-between font-mono text-[11px]">
                            <span>{type}</span>
                            <span className="text-slate-400">{count}</span>
                          </div>
                        ))}
                    </dd>
                  </div>
                )}
                {graphSummary.recent_events.length > 0 && (
                  <div>
                    <dt className="text-slate-400 mb-1">Recent events</dt>
                    <dd className="space-y-1">
                      {graphSummary.recent_events.slice(0, 3).map((ev) => (
                        <p key={ev.id} className="text-[11px] text-slate-500 truncate">
                          {(ev.payload?.action as string) ?? ev.event_type}
                        </p>
                      ))}
                    </dd>
                  </div>
                )}
              </dl>
            ) : (
              <p className="text-xs text-slate-400">No graph activity yet.</p>
            )}
            <Link
              href="/intelligence/events"
              className="mt-3 inline-block text-[11px] text-brand-600 hover:text-brand-700 font-medium"
            >
              View event log →
            </Link>
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
    </div>
  );
}
