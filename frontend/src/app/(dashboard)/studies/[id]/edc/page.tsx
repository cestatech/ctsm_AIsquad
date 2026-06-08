"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { artifactsApi } from "@/lib/api/artifacts";
import { studiesApi } from "@/lib/api/studies";
import type { Artifact } from "@/types";

type EdcTab =
  | "soa"
  | "visits"
  | "forms"
  | "fields"
  | "checks"
  | "screens"
  | "sdtm"
  | "mock";

interface LegacyField {
  field_id: string;
  label: string;
  type: string;
  required?: boolean;
  options?: string[];
}

interface LegacyForm {
  form_id: string;
  form_name: string;
  visit: string;
  status: string;
  fields: LegacyField[];
}

interface EdcField {
  field_id: string;
  form_id: string;
  visit_ids?: string[];
  label: string;
  data_type?: string;
  type?: string;
  required?: boolean;
  controlled_terminology?: string | null;
  edit_checks?: string[];
  sdtm_mapping?: string;
  context_graph_hint?: string;
}

interface EdcContent {
  title?: string;
  edc_vendor?: string;
  build_status?: string;
  schedule_of_assessments?: Array<{
    visit_id: string;
    visit_label: string;
    assessments: Array<{ assessment_id: string; field_id: string; form_id: string; label: string }>;
  }>;
  visit_schedule?: Array<{ visit_id: string; label: string; day: number | null; window_days: number }>;
  forms?: Array<{
    form_id: string;
    form_name: string;
    visit_ids?: string[];
    visit?: string;
    status: string;
    fields?: LegacyField[];
  }>;
  fields?: EdcField[];
  edit_checks?: Array<{ check_id: string; field_id: string; form_id: string; rule: string; severity: string }>;
  controlled_terminology?: Array<{ codelist_id: string; name: string; used_by_fields: string[] }>;
  mock_screens?: Array<{
    screen_id: string;
    form_id: string;
    form_name: string;
    visit_ids: string[];
    field_ids: string[];
  }>;
  legacy_forms?: LegacyForm[];
}

const TABS: { id: EdcTab; label: string }[] = [
  { id: "soa", label: "Schedule of Assessments" },
  { id: "visits", label: "Visit Schedule" },
  { id: "forms", label: "Forms" },
  { id: "fields", label: "Fields" },
  { id: "checks", label: "Edit Checks" },
  { id: "screens", label: "Mock Screens" },
  { id: "sdtm", label: "SDTM Mapping" },
  { id: "mock", label: "Screen Preview" },
];

const MOCK_VALUES: Record<string, string> = {
  SUBJECT_ID: "STUDY-001",
  VISIT_DATE: "2026-01-15",
  SEX: "F",
  RACE: "White",
  ETHNICITY: "Not Hispanic",
  AGE: "52",
  BMI: "28.4",
  HBA1C: "6.1",
  FASTING_GLUCOSE: "112",
  SYSBP: "128",
  DIABP: "82",
  HR: "72",
  AE_TERM: "Nausea",
  AE_SEVERITY: "2",
  COMPLIANCE_PERCENT: "94",
  BRTHDTC: "1961-04-12",
  ETHNIC: "Not Hispanic or Latino",
};

function normalizeEdcContent(raw: Record<string, unknown>): EdcContent {
  const content = raw as EdcContent;
  if (!content.forms?.length && content.legacy_forms?.length) {
    content.forms = content.legacy_forms.map((f) => ({
      form_id: f.form_id,
      form_name: f.form_name,
      visit: f.visit,
      status: f.status,
      fields: f.fields,
    }));
  }
  if (!content.fields?.length && content.forms?.length) {
    content.fields = content.forms.flatMap((form) =>
      (form.fields ?? []).map((f) => ({
        field_id: f.field_id,
        form_id: form.form_id,
        label: f.label,
        data_type: f.type,
        required: f.required,
      }))
    );
  }
  return content;
}

function parseEdcContent(
  artifact: Artifact | null,
  versions: { content: Record<string, unknown> }[] | undefined
): EdcContent | null {
  if (!artifact || !versions?.length) return null;
  const current = versions.find((v) => v.content) ?? versions[0];
  return normalizeEdcContent(current.content);
}

function FieldPreview({ field }: { field: LegacyField | EdcField }) {
  const fieldId = field.field_id;
  const dataType = "data_type" in field && field.data_type ? field.data_type : (field as LegacyField).type;
  const value = MOCK_VALUES[fieldId] ?? (dataType === "yesno" ? "—" : "");
  return (
    <div className="space-y-1">
      <label className="text-[11px] font-medium text-slate-600 flex items-center gap-1">
        {field.label}
        {field.required && <span className="text-red-500">*</span>}
      </label>
      {"context_graph_hint" in field && field.context_graph_hint && (
        <p className="text-[10px] text-slate-400 italic leading-snug">{field.context_graph_hint}</p>
      )}
      {dataType === "select" || dataType === "yesno" ? (
        <select
          disabled
          className="w-full text-xs border border-slate-200 bg-slate-50 text-slate-700 px-2 py-1.5 rounded-sm"
          value={value}
        >
          <option>{value || "Select…"}</option>
        </select>
      ) : (
        <input
          disabled
          type={dataType === "date" ? "date" : dataType === "number" ? "number" : "text"}
          className="w-full text-xs border border-slate-200 bg-slate-50 text-slate-700 px-2 py-1.5 rounded-sm"
          value={value}
        />
      )}
    </div>
  );
}

export default function EdcMockScreensPage() {
  const params = useParams<{ id: string }>();
  const studyId = params.id;
  const { token } = useAuthStore();
  const [activeTab, setActiveTab] = useState<EdcTab>("mock");
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

  const edcArtifact =
    (artifactsData?.items ?? []).find((a) => a.artifact_type === "EDC_CRF") ?? null;

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
  const fields = content?.fields ?? [];
  const activeForm = forms.find((f) => f.form_id === activeFormId) ?? forms[0] ?? null;
  const previewFields: (LegacyField | EdcField)[] =
    activeForm?.fields ??
    fields.filter((f) => f.form_id === activeForm?.form_id);

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
            <h1 className="font-display text-xl font-bold text-slate-900">EDC / eCRF Specification</h1>
            <p className="text-slate-500 text-sm mt-0.5">
              {study?.name ?? "Study"} — {content?.edc_vendor ?? content?.title ?? "eCRF preview"}
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
        {content && (
          <div className="flex flex-wrap gap-1 mt-4">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`px-3 py-1.5 text-[11px] font-medium rounded-sm transition-colors ${
                  activeTab === tab.id
                    ? "bg-slate-900 text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        )}
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
              Generate an EDC_CRF artifact from the study workspace after Protocol is created,
              or run the demo program seed.
            </p>
            <Link
              href={`/studies/${studyId}`}
              className="text-sm text-brand-600 hover:text-brand-700 font-medium"
            >
              Go to study workspace →
            </Link>
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-8">
          {activeTab === "soa" && (
            <div className="bg-white border border-slate-200 p-6 space-y-4 max-w-4xl">
              {(content.schedule_of_assessments ?? []).map((row) => (
                <div key={row.visit_id} className="border-b border-slate-100 pb-4 last:border-0">
                  <h3 className="text-sm font-semibold text-slate-900">
                    {row.visit_label} <span className="font-mono text-slate-400 text-xs">({row.visit_id})</span>
                  </h3>
                  <ul className="mt-2 space-y-1">
                    {row.assessments.map((a) => (
                      <li key={a.assessment_id} className="text-xs text-slate-600">
                        {a.label} — <span className="font-mono text-slate-400">{a.field_id}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
              {!content.schedule_of_assessments?.length && (
                <p className="text-sm text-slate-400">No schedule of assessments in this artifact.</p>
              )}
            </div>
          )}

          {activeTab === "visits" && (
            <div className="bg-white border border-slate-200 overflow-hidden max-w-3xl">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-100">
                    <th className="text-left px-4 py-2 text-xs text-slate-500">Visit ID</th>
                    <th className="text-left px-4 py-2 text-xs text-slate-500">Label</th>
                    <th className="text-left px-4 py-2 text-xs text-slate-500">Day</th>
                    <th className="text-left px-4 py-2 text-xs text-slate-500">Window</th>
                  </tr>
                </thead>
                <tbody>
                  {(content.visit_schedule ?? []).map((v) => (
                    <tr key={v.visit_id} className="border-b border-slate-50">
                      <td className="px-4 py-2 font-mono text-xs">{v.visit_id}</td>
                      <td className="px-4 py-2">{v.label}</td>
                      <td className="px-4 py-2 text-slate-500">{v.day ?? "—"}</td>
                      <td className="px-4 py-2 text-slate-500">±{v.window_days}d</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {activeTab === "forms" && (
            <div className="grid gap-3 max-w-3xl">
              {forms.map((form) => (
                <div key={form.form_id} className="bg-white border border-slate-200 px-4 py-3">
                  <p className="font-semibold text-sm text-slate-900">
                    {form.form_id} — {form.form_name}
                  </p>
                  <p className="text-xs text-slate-500 mt-1">
                    Visits: {(form.visit_ids ?? [form.visit]).filter(Boolean).join(", ")} · Status: {form.status}
                  </p>
                </div>
              ))}
            </div>
          )}

          {activeTab === "fields" && (
            <div className="bg-white border border-slate-200 overflow-hidden max-w-5xl">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-100">
                    <th className="text-left px-3 py-2 text-slate-500">Field</th>
                    <th className="text-left px-3 py-2 text-slate-500">Form</th>
                    <th className="text-left px-3 py-2 text-slate-500">Type</th>
                    <th className="text-left px-3 py-2 text-slate-500">Context / reason</th>
                  </tr>
                </thead>
                <tbody>
                  {fields.map((f) => (
                    <tr key={f.field_id} className="border-b border-slate-50 align-top">
                      <td className="px-3 py-2 font-mono">{f.field_id}</td>
                      <td className="px-3 py-2">{f.form_id}</td>
                      <td className="px-3 py-2">{f.data_type ?? f.type ?? "—"}</td>
                      <td className="px-3 py-2 text-slate-500 leading-relaxed">
                        {f.context_graph_hint ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {activeTab === "checks" && (
            <div className="space-y-2 max-w-3xl">
              {(content.edit_checks ?? []).map((c) => (
                <div key={c.check_id} className="bg-white border border-slate-200 px-4 py-3 text-xs">
                  <span className="font-mono text-slate-400">{c.check_id}</span>
                  <span className="mx-2 text-slate-300">·</span>
                  <span className="font-medium">{c.rule}</span>
                  <span className="text-slate-400 ml-2">({c.field_id})</span>
                </div>
              ))}
            </div>
          )}

          {activeTab === "screens" && (
            <div className="grid gap-3 max-w-3xl">
              {(content.mock_screens ?? []).map((s) => (
                <div key={s.screen_id} className="bg-white border border-slate-200 px-4 py-3">
                  <p className="font-semibold text-sm">{s.form_name}</p>
                  <p className="text-xs text-slate-500 mt-1">
                    Screen {s.screen_id} · Fields: {s.field_ids.join(", ")}
                  </p>
                </div>
              ))}
            </div>
          )}

          {activeTab === "sdtm" && (
            <div className="bg-white border border-slate-200 overflow-hidden max-w-4xl">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-100">
                    <th className="text-left px-3 py-2">eCRF Field</th>
                    <th className="text-left px-3 py-2">SDTM Variable</th>
                  </tr>
                </thead>
                <tbody>
                  {fields
                    .filter((f) => f.sdtm_mapping)
                    .map((f) => (
                      <tr key={f.field_id} className="border-b border-slate-50">
                        <td className="px-3 py-2 font-mono">{f.field_id}</td>
                        <td className="px-3 py-2 font-mono text-brand-700">{f.sdtm_mapping}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}

          {activeTab === "mock" && (
            <div className="flex min-h-0 gap-0 max-w-5xl">
              <aside className="w-64 bg-white border border-slate-200 shrink-0">
                <nav className="py-2">
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
                    </button>
                  ))}
                </nav>
              </aside>
              <main className="flex-1 bg-white border border-l-0 border-slate-200 p-6">
                {activeForm && (
                  <div className="space-y-4 max-w-xl">
                    <h2 className="font-display font-semibold text-slate-900">{activeForm.form_name}</h2>
                    {previewFields.map((field) => (
                      <FieldPreview key={field.field_id} field={field} />
                    ))}
                  </div>
                )}
              </main>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
