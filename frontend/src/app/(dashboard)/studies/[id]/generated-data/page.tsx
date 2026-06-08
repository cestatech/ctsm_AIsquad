"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { artifactsApi } from "@/lib/api/artifacts";
import { downloadTextFile } from "@/lib/download";
import { studiesApi } from "@/lib/api/studies";
import type { Artifact, ArtifactType } from "@/types";

const PIPELINE_TYPES: ArtifactType[] = ["SDTM_DATASET", "ADAM_DATASET", "TLF"];

const TYPE_LABELS: Record<string, string> = {
  SDTM_DATASET: "SDTM Dataset",
  ADAM_DATASET: "ADaM Dataset",
  TLF: "TLF Package",
};

const TYPE_COLORS: Record<string, string> = {
  SDTM_DATASET: "bg-emerald-100 text-emerald-800",
  ADAM_DATASET: "bg-teal-100 text-teal-800",
  TLF: "bg-amber-100 text-amber-800",
};

export default function GeneratedDataPage() {
  const params = useParams<{ id: string }>();
  const studyId = params.id;
  const { token } = useAuthStore();

  const { data: study } = useQuery({
    queryKey: ["study", studyId, token],
    queryFn: () => studiesApi.get(studyId, token!),
    enabled: !!token,
  });

  const { data: artifactsData, isLoading } = useQuery({
    queryKey: ["generated-data", studyId, token],
    queryFn: () => artifactsApi.list({ study_id: studyId, page_size: 100 }, token!),
    enabled: !!token,
  });

  const pipelineArtifacts = (artifactsData?.items ?? []).filter((a) =>
    PIPELINE_TYPES.includes(a.artifact_type)
  );

  const byType = PIPELINE_TYPES.map((type) => ({
    type,
    items: pipelineArtifacts.filter((a) => a.artifact_type === type),
  }));

  async function handleDownloadJson(artifact: Artifact) {
    if (!token) return;
    const versions = await artifactsApi.getVersions(artifact.id, token);
    const current =
      versions.find((v) => v.is_current) ??
      versions.sort((a, b) => b.version_number - a.version_number)[0];
    const content = current?.content ?? {};
    const slug = artifact.name.replace(/[^a-z0-9]+/gi, "_").toLowerCase();
    downloadTextFile(`${slug}.json`, JSON.stringify(content, null, 2));
  }

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <Link
          href={`/studies/${studyId}`}
          className="text-xs text-brand-600 hover:text-brand-700 flex items-center gap-1 mb-3"
        >
          ← Back to study
        </Link>
        <h1 className="font-display text-xl font-bold text-slate-900">
          Generated Data
        </h1>
        <p className="text-slate-500 text-sm mt-0.5">
          {study?.name ?? "Study"} — synthesized SDTM, ADaM, and TLF pipeline outputs
        </p>
      </div>

      <div className="px-8 py-6 space-y-6">
        <div className="bg-blue-50 border border-blue-200 px-4 py-3 text-xs text-blue-900">
          These artifacts are AI-derived from approved raw mappings and upstream datasets.
          Download JSON for inspection, or open the artifact for QC programs and validation.
          Synthetic patient runs (raw eCRF exports, not SDTM) are listed under{" "}
          <Link href="/intelligence/synthetic" className="font-semibold underline">
            Intelligence → Synthetic Data
          </Link>
          .
        </div>

        {isLoading ? (
          <p className="text-sm text-slate-400">Loading generated data…</p>
        ) : pipelineArtifacts.length === 0 ? (
          <div className="bg-white border border-slate-200 px-8 py-14 text-center">
            <p className="font-display font-semibold text-slate-900 mb-1">
              No generated data yet
            </p>
            <p className="text-slate-500 text-sm mb-4">
              Upload raw data, approve mappings, then generate SDTM from the study workspace.
            </p>
            <Link
              href={`/studies/${studyId}`}
              className="text-sm text-brand-600 hover:text-brand-700 font-medium"
            >
              Go to study workspace →
            </Link>
          </div>
        ) : (
          byType.map(({ type, items }) =>
            items.length > 0 ? (
              <section key={type} className="bg-white border border-slate-200">
                <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
                  <h2 className="font-display font-semibold text-slate-900 text-sm">
                    {TYPE_LABELS[type] ?? type}
                  </h2>
                  <span className="text-xs text-slate-500">{items.length} artifact(s)</span>
                </div>
                <div className="divide-y divide-slate-100">
                  {items.map((artifact) => (
                    <div
                      key={artifact.id}
                      className="px-5 py-4 flex items-center justify-between gap-4"
                    >
                      <div className="min-w-0">
                        <Link
                          href={`/studies/${studyId}/artifacts/${artifact.id}`}
                          className="text-sm font-medium text-brand-700 hover:text-brand-800 truncate block"
                        >
                          {artifact.name}
                        </Link>
                        <p className="text-xs text-slate-500 mt-0.5">
                          v{artifact.current_version_number} · {artifact.status.replace("_", " ")}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <span
                          className={`text-[10px] px-2 py-0.5 font-semibold ${
                            TYPE_COLORS[type] ?? "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {TYPE_LABELS[type]}
                        </span>
                        <button
                          type="button"
                          onClick={() => handleDownloadJson(artifact)}
                          className="text-xs border border-slate-200 hover:border-slate-300 text-slate-700 px-3 py-1.5 transition-colors"
                        >
                          Download JSON
                        </button>
                        <Link
                          href={`/studies/${studyId}/artifacts/${artifact.id}`}
                          className="text-xs bg-brand-600 hover:bg-brand-500 text-white font-semibold px-3 py-1.5 transition-colors"
                        >
                          Open
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            ) : null
          )
        )}
      </div>
    </div>
  );
}
