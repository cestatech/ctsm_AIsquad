"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { artifactsApi } from "@/lib/api/artifacts";
import { studiesApi } from "@/lib/api/studies";
import type { Artifact } from "@/types";

interface CrfField {
  field_id: string;
  label: string;
  type: string;
  required?: boolean;
  options?: string[];
}

interface CrfForm {
  form_id: string;
  form_name: string;
  visit: string;
  status: string;
  fields: CrfField[];
}

interface VisitScheduleItem {
  visit_id: string;
  label: string;
  day: number | null;
  window_days: number;
}

interface EdcContent {
  title?: string;
  edc_vendor?: string;
  build_status?: string;
  visit_schedule?: VisitScheduleItem[];
  forms?: CrfForm[];
}

const MOCK_VALUES: Record<string, string> = {
  BRTHDTC: "1961-04-12",
  SEX: "F",
  RACE: "White",
  ETHNIC: "Not Hispanic or Latino",
  IEYN: "Yes",
  PDL1TPS: "35",
  ECOG: "1",
  MHTERM: "NSCLC — adenocarcinoma",
  MHSTDTC: "2024-08-01",
  MHONGO: "Yes",
  EXSTDTC: "2025-01-15",
  EXDOSE: "10",
  EXROUTE: "IV",
  AETERM: "Fatigue",
  AESTDTC: "2025-02-01",
  AESEV: "2",
  AESER: "No",
  TUDTC: "2025-03-10",
  TUMETHOD: "CT",
  TUORRES: "SD",
  DSDECOD: "Completed",
  DSSTDTC: "2025-06-01",
};

function FieldPreview({ field }: { field: CrfField }) {
  const value = MOCK_VALUES[field.field_id] ?? (field.type === "yesno" ? "—" : "");
  return (
    <div className="space-y-1">
      <label className="text-[11px] font-medium text-slate-600 flex items-center gap-1">
        {field.label}
        {field.required && <span className="text-red-500">*</span>}
      </label>
      {field.type === "select" || field.type === "yesno" ? (
        <select
          disabled
          className="w-full text-xs border border-slate-200 bg-slate-50 text-slate-700 px-2 py-1.5 rounded-sm"
          value={value}
        >
          <option>{value || "Select…"}</option>
        </select>
      ) : field.type === "multiselect" ? (
        <input
          disabled
          className="w-full text-xs border border-slate-200 bg-slate-50 text-slate-700 px-2 py-1.5 rounded-sm"
          value={value}
        />
      ) : (
        <input
          disabled
          type={field.type === "date" ? "date" : field.type === "number" ? "number" : "text"}
          className="w-full text-xs border border-slate-200 bg-slate-50 text-slate-700 px-2 py-1.5 rounded-sm"
          value={value}
        />
      )}
    </div>
  );
}

function parseEdcContent(artifact: Artifact | null, versions: { content: Record<string, unknown> }[] | undefined): EdcContent | null {
  if (!artifact || !versions?.length) return null;
  const current = versions.find((v) => v.content) ?? versions[0];
  return current.content as EdcContent;
}

export default function EdcMockScreensPage() {
  const params = useParams<{ id: string }>();
  const studyId = params.id;
  const { token } = useAuthStore();
  const [activeFormId, setActiveFormId] = useState<string | null>(null);

  const { data: study } = useQuery({
    queryKey: ["study", studyId, token],
    queryFn: () => studiesApi.get(studyId, token!),
    enabled: !!token,
  });

  const { data: artifactsData, isLoading } = useQuery({
    queryKey: ["edc-artifact", studyId, token],
    queryFn: () => artifactsApi.list({ study_id: studyId, page_size: 50 }, token!),
    enabled: !!token,
  });

  const edcArtifact = (artifactsData?.items ?? []).find(
    (a) => a.artifact_type === "EDC_CRF"
  ) ?? null;

  const { data: versions } = useQuery({
    queryKey: ["edc-versions", edcArtifact?.id, token],
    queryFn: () => artifactsApi.getVersions(edcArtifact!.id, token!),
    enabled: !!token && !!edcArtifact,
  });

  const content = useMemo(
    () => parseEdcContent(edcArtifact, versions),
    [edcArtifact, versions]
  );

  const forms = content?.forms ?? [];
  const visits = content?.visit_schedule ?? [];
  const activeForm = forms.find((f) => f.form_id === activeFormId) ?? forms[0] ?? null;
  const allComplete = forms.length > 0 && forms.every((f) => f.status === "COMPLETE");

  return (
    <div className="flex flex-col h-screen bg-slate-100">
      <div className="px-8 py-5 border-b border-slate-200 bg-white shrink-0">
        <Link
          href={`/studies/${studyId}`}
          className="text-xs text-brand-600 hover:text-brand-700 flex items-center gap-1 mb-3"
        >
          ← Back to study
        </Link>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="font-display text-xl font-bold text-slate-900">EDC Mock Screens</h1>
            <p className="text-slate-500 text-sm mt-0.5">
              {study?.name ?? "Study"} — {content?.edc_vendor ?? "eCRF preview"}
            </p>
          </div>
          {edcArtifact && (
            <Link
              href={`/studies/${studyId}/artifacts/${edcArtifact.id}`}
              className="text-xs border border-slate-200 text-slate-700 hover:bg-slate-50 px-3 py-2 transition-colors shrink-0"
            >
              Open eCRF artifact →
            </Link>
          )}
        </div>
      </div>

      {isLoading ? (
        <div className="flex-1 flex items-center justify-center text-sm text-slate-400">
          Loading EDC specification…
        </div>
      ) : !edcArtifact || !content ? (
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center max-w-md">
            <p className="font-display font-semibold text-slate-900 mb-1">No eCRF specification yet</p>
            <p className="text-slate-500 text-sm mb-4">
              Run the demo program seed or generate an EDC_CRF artifact from the Study Brief.
            </p>
            <Link
              href={`/studies/${studyId}/intake`}
              className="text-sm text-brand-600 hover:text-brand-700 font-medium"
            >
              Go to intake →
            </Link>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex min-h-0">
          <aside className="w-72 bg-white border-r border-slate-200 flex flex-col shrink-0">
            <div className="px-4 py-3 border-b border-slate-100">
              <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">
                Visit schedule
              </p>
              <div className="mt-2 space-y-1">
                {visits.map((v) => (
                  <p key={v.visit_id} className="text-[11px] text-slate-600">
                    <span className="font-mono text-slate-400 mr-1">{v.visit_id}</span>
                    {v.label}
                  </p>
                ))}
              </div>
            </div>
            <div className="px-4 py-3 border-b border-slate-100">
              {allComplete && (
                <span className="text-[10px] px-2 py-0.5 bg-emerald-100 text-emerald-800 font-semibold">
                  All screens complete
                </span>
              )}
              <p className="text-[10px] text-slate-400 mt-2">
                Build status: {content.build_status ?? "—"}
              </p>
            </div>
            <nav className="flex-1 overflow-y-auto py-2">
              {forms.map((form) => (
                <button
                  key={form.form_id}
                  type="button"
                  onClick={() => setActiveFormId(form.form_id)}
                  className={`w-full text-left px-4 py-2.5 border-l-2 transition-colors ${
                    (activeForm?.form_id ?? forms[0]?.form_id) === form.form_id
                      ? "border-brand-500 bg-brand-50"
                      : "border-transparent hover:bg-slate-50"
                  }`}
                >
                  <p className="text-xs font-semibold text-slate-800">
                    {form.form_id} — {form.form_name}
                  </p>
                  <p className="text-[10px] text-slate-400 mt-0.5">{form.visit}</p>
                  <span
                    className={`inline-block mt-1 text-[9px] px-1.5 py-0.5 font-semibold ${
                      form.status === "COMPLETE"
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-amber-100 text-amber-700"
                    }`}
                  >
                    {form.status}
                  </span>
                </button>
              ))}
            </nav>
          </aside>

          <main className="flex-1 overflow-y-auto p-8">
            {activeForm && (
              <div className="max-w-2xl mx-auto bg-white border border-slate-200 shadow-sm">
                <div className="px-6 py-4 border-b border-slate-100 bg-slate-50">
                  <p className="text-[10px] font-mono text-slate-400">{activeForm.form_id}</p>
                  <h2 className="font-display font-semibold text-slate-900 mt-0.5">
                    {activeForm.form_name}
                  </h2>
                  <p className="text-xs text-slate-500 mt-1">
                    Visit: {activeForm.visit} · Subject DEMO-001-001
                  </p>
                </div>
                <div className="px-6 py-5 space-y-4">
                  {activeForm.fields.map((field) => (
                    <FieldPreview key={field.field_id} field={field} />
                  ))}
                </div>
                <div className="px-6 py-4 border-t border-slate-100 bg-slate-50 flex justify-between items-center">
                  <span className="text-[10px] text-slate-400">
                    Mock data entry — read-only preview
                  </span>
                  <button
                    type="button"
                    disabled
                    className="text-xs bg-brand-600 text-white font-semibold px-4 py-2 opacity-60 cursor-not-allowed"
                  >
                    Save (mock)
                  </button>
                </div>
              </div>
            )}
          </main>
        </div>
      )}
    </div>
  );
}
