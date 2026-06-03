"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { usePermissions } from "@/hooks/usePermissions";
import { studiesApi } from "@/lib/api/studies";

const PHASES = [
  { value: "PHASE_1", label: "Phase 1" },
  { value: "PHASE_1_2", label: "Phase 1/2" },
  { value: "PHASE_2", label: "Phase 2" },
  { value: "PHASE_2_3", label: "Phase 2/3" },
  { value: "PHASE_3", label: "Phase 3" },
  { value: "PHASE_3_4", label: "Phase 3/4" },
  { value: "PHASE_4", label: "Phase 4" },
  { value: "OBSERVATIONAL", label: "Observational" },
  { value: "OTHER", label: "Other" },
];

const REGIONS = ["FDA", "EMA", "PMDA", "Health Canada", "TGA", "ANVISA", "NMPA"];

export default function NewStudyPage() {
  const router = useRouter();
  const { token, role } = useAuthStore();
  const perms = usePermissions(role);

  const [form, setForm] = useState({
    protocol_number: "",
    name: "",
    short_name: "",
    description: "",
    indication: "",
    therapeutic_area: "",
    phase: "",
    sponsor: "",
    regulatory_region: [] as string[],
    start_date: "",
    end_date: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!perms.isAdmin) {
    return (
      <div className="px-8 py-16 text-center">
        <p className="text-slate-500">Only Admins can create studies.</p>
      </div>
    );
  }

  function set(field: string, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function toggleRegion(r: string) {
    setForm((prev) => ({
      ...prev,
      regulatory_region: prev.regulatory_region.includes(r)
        ? prev.regulatory_region.filter((x) => x !== r)
        : [...prev.regulatory_region, r],
    }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.protocol_number.trim() || !form.name.trim()) {
      setError("Protocol number and study name are required.");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const study = await studiesApi.create(
        {
          ...form,
          phase: form.phase || undefined,
          short_name: form.short_name || undefined,
          description: form.description || undefined,
          indication: form.indication || undefined,
          therapeutic_area: form.therapeutic_area || undefined,
          sponsor: form.sponsor || undefined,
          regulatory_region: form.regulatory_region.length ? form.regulatory_region : undefined,
          start_date: form.start_date || undefined,
          end_date: form.end_date || undefined,
        },
        token!
      );
      router.push(`/studies/${study.id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create study. Please try again.";
      setError(msg);
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <div className="flex items-center gap-3 mb-1">
          <button
            onClick={() => router.back()}
            className="text-slate-400 hover:text-slate-700 text-sm transition-colors"
          >
            ← Studies
          </button>
        </div>
        <h1 className="font-display text-xl font-bold text-slate-900">New Study</h1>
        <p className="text-slate-500 text-sm mt-0.5">Create a new clinical trial workspace</p>
      </div>

      <div className="px-8 py-8 max-w-2xl">
        <form onSubmit={handleSubmit} className="space-y-6">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3">
              {error}
            </div>
          )}

          {/* Identifiers */}
          <div className="bg-white border border-slate-200 p-6 space-y-4">
            <h2 className="font-display font-semibold text-slate-900 text-sm border-b border-slate-100 pb-3">
              Study Identifiers
            </h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">
                  Protocol Number <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={form.protocol_number}
                  onChange={(e) => set("protocol_number", e.target.value)}
                  placeholder="e.g. CTG-2024-001"
                  className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 font-mono"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Short Name</label>
                <input
                  type="text"
                  value={form.short_name}
                  onChange={(e) => set("short_name", e.target.value)}
                  placeholder="e.g. NOVA-1"
                  className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1.5">
                Study Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => set("name", e.target.value)}
                placeholder="Full study title"
                className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1.5">Description</label>
              <textarea
                value={form.description}
                onChange={(e) => set("description", e.target.value)}
                rows={3}
                placeholder="Brief study description"
                className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 resize-none"
              />
            </div>
          </div>

          {/* Clinical Details */}
          <div className="bg-white border border-slate-200 p-6 space-y-4">
            <h2 className="font-display font-semibold text-slate-900 text-sm border-b border-slate-100 pb-3">
              Clinical Details
            </h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Indication</label>
                <input
                  type="text"
                  value={form.indication}
                  onChange={(e) => set("indication", e.target.value)}
                  placeholder="e.g. Non-Small Cell Lung Cancer"
                  className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Therapeutic Area</label>
                <input
                  type="text"
                  value={form.therapeutic_area}
                  onChange={(e) => set("therapeutic_area", e.target.value)}
                  placeholder="e.g. Oncology"
                  className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Phase</label>
                <select
                  value={form.phase}
                  onChange={(e) => set("phase", e.target.value)}
                  className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 bg-white"
                >
                  <option value="">Select phase</option>
                  {PHASES.map((p) => (
                    <option key={p.value} value={p.value}>{p.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Sponsor</label>
                <input
                  type="text"
                  value={form.sponsor}
                  onChange={(e) => set("sponsor", e.target.value)}
                  placeholder="Sponsoring organization"
                  className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                />
              </div>
            </div>

            {/* Regulatory Regions */}
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-2">Regulatory Regions</label>
              <div className="flex flex-wrap gap-2">
                {REGIONS.map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => toggleRegion(r)}
                    className={`text-xs px-3 py-1.5 border font-medium transition-colors ${
                      form.regulatory_region.includes(r)
                        ? "bg-brand-600 border-brand-600 text-white"
                        : "bg-white border-slate-200 text-slate-600 hover:border-brand-400"
                    }`}
                  >
                    {r}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Timeline */}
          <div className="bg-white border border-slate-200 p-6 space-y-4">
            <h2 className="font-display font-semibold text-slate-900 text-sm border-b border-slate-100 pb-3">
              Timeline
            </h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Start Date</label>
                <input
                  type="date"
                  value={form.start_date}
                  onChange={(e) => set("start_date", e.target.value)}
                  className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Estimated End Date</label>
                <input
                  type="date"
                  value={form.end_date}
                  onChange={(e) => set("end_date", e.target.value)}
                  className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                />
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={submitting}
              className="bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white text-sm font-semibold font-display px-6 py-2.5 transition-colors"
            >
              {submitting ? "Creating…" : "Create study"}
            </button>
            <button
              type="button"
              onClick={() => router.back()}
              className="text-slate-500 hover:text-slate-700 text-sm transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
