"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { intelligenceApi } from "@/lib/api/intelligence";
import { MOCK_DATA_LINEAGE } from "@/lib/mockData";
import type { DataLineage } from "@/types";

const EXAMPLE_ENTITIES = [
  { label: "DTHFL (eCRF → SDTM)", type: "ecr_field", id: "00000000-0000-0000-dead-beefdeadbeef" },
  { label: "DSSTDTC (SDTM → ADaM)", type: "sdtm_variable", id: "00000000-0000-0000-dead-beefdeadc0de" },
  { label: "NVX-001 Protocol (Artifact)", type: "artifact", id: "art-001" },
];

function LineageCard({ rec }: { rec: DataLineage }) {
  return (
    <div className="bg-white border border-slate-200 px-4 py-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-mono text-slate-400">{rec.id.slice(0, 8)}…</span>
        <span
          className={`text-[11px] px-2 py-0.5 font-semibold ${
            rec.is_ai_generated
              ? "bg-blue-100 text-blue-700"
              : "bg-slate-100 text-slate-600"
          }`}
        >
          {rec.is_ai_generated ? "AI-generated" : "Manual"}
        </span>
      </div>

      <div className="flex items-center gap-2 text-xs">
        <div className="flex-1 bg-slate-50 border border-slate-200 px-2 py-1.5 text-center">
          <p className="text-[11px] text-slate-400 uppercase tracking-wide mb-0.5">{rec.source_type}</p>
          <p className="font-mono font-medium text-slate-800">
            {rec.source_domain ? `${rec.source_domain}.` : ""}
            {rec.source_field ?? "—"}
          </p>
        </div>
        <div className="text-slate-400 font-semibold shrink-0">→</div>
        <div className="flex-1 bg-slate-50 border border-slate-200 px-2 py-1.5 text-center">
          <p className="text-[11px] text-slate-400 uppercase tracking-wide mb-0.5">{rec.target_type}</p>
          <p className="font-mono font-medium text-slate-800">
            {rec.target_domain ? `${rec.target_domain}.` : ""}
            {rec.target_field ?? "—"}
          </p>
        </div>
      </div>

      {rec.transformation_logic && (
        <div>
          <p className="text-[11px] text-slate-400 uppercase tracking-wide mb-0.5">Transformation Logic</p>
          <code className="text-[11px] text-slate-700 bg-slate-50 border border-slate-100 block px-2 py-1.5 leading-relaxed font-mono">
            {rec.transformation_logic}
          </code>
        </div>
      )}

      <p className="text-[11px] text-slate-400">
        {new Date(rec.created_at).toLocaleDateString()}
      </p>
    </div>
  );
}

export default function LineageExplorerPage() {
  const { token } = useAuthStore();
  const [targetType, setTargetType] = useState("");
  const [targetId, setTargetId] = useState("");
  const [submitted, setSubmitted] = useState<{ type: string; id: string } | null>(null);

  function applyExample(type: string, id: string) {
    setTargetType(type);
    setTargetId(id);
  }

  const { data, isFetching } = useQuery({
    queryKey: ["lineage-chain", submitted?.type, submitted?.id],
    enabled: !!submitted,
    queryFn: async () => {
      if (!submitted) return null;
      if (!token) {
        const up = MOCK_DATA_LINEAGE.filter(
          (r) => r.target_type === submitted.type
        );
        const down = MOCK_DATA_LINEAGE.filter(
          (r) => r.source_type === submitted.type
        );
        return { upstream: up, downstream: down };
      }
      try {
        return await intelligenceApi.getLineageChain(
          { target_type: submitted.type, target_id: submitted.id },
          token
        );
      } catch {
        const up = MOCK_DATA_LINEAGE.filter(
          (r) => r.target_type === submitted.type
        );
        const down = MOCK_DATA_LINEAGE.filter(
          (r) => r.source_type === submitted.type
        );
        return { upstream: up, downstream: down };
      }
    },
  });

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <h1 className="font-display text-xl font-bold text-slate-900">Lineage Explorer</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Trace the upstream sources and downstream derivations for any data entity.
        </p>
      </div>

      <div className="px-8 py-6 space-y-6">
        {/* Query form */}
        <div className="bg-white border border-slate-200 px-6 py-5">
          <p className="text-xs font-semibold text-slate-700 mb-3">Explore Lineage Chain</p>

          <div className="flex gap-3 mb-3">
            <div className="flex-1">
              <label className="block text-xs text-slate-500 mb-1">Entity Type</label>
              <input
                value={targetType}
                onChange={(e) => setTargetType(e.target.value)}
                placeholder="e.g. sdtm_variable, ecr_field, artifact"
                className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-brand-500 font-mono"
              />
            </div>
            <div className="flex-1">
              <label className="block text-xs text-slate-500 mb-1">Entity ID</label>
              <input
                value={targetId}
                onChange={(e) => setTargetId(e.target.value)}
                placeholder="UUID or identifier"
                className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-brand-500 font-mono"
              />
            </div>
            <div className="flex items-end">
              <button
                disabled={!targetType.trim() || !targetId.trim()}
                onClick={() => setSubmitted({ type: targetType.trim(), id: targetId.trim() })}
                className="px-5 py-2 bg-brand-600 hover:bg-brand-500 text-white text-sm font-semibold font-display transition-colors disabled:opacity-50"
              >
                Trace
              </button>
            </div>
          </div>

          <div className="flex gap-2 flex-wrap">
            <span className="text-[11px] text-slate-400">Try:</span>
            {EXAMPLE_ENTITIES.map((ex) => (
              <button
                key={ex.id}
                onClick={() => applyExample(ex.type, ex.id)}
                className="text-[11px] text-brand-600 hover:text-brand-700 underline"
              >
                {ex.label}
              </button>
            ))}
          </div>
        </div>

        {isFetching && (
          <div className="text-center py-8 text-slate-400 text-sm">Loading lineage chain…</div>
        )}

        {data && !isFetching && (
          <div className="grid grid-cols-2 gap-6">
            <div>
              <div className="flex items-center gap-2 mb-3">
                <div className="w-3 h-3 bg-blue-500" />
                <p className="text-sm font-semibold text-slate-800">Upstream Sources</p>
                <span className="text-xs text-slate-400">({data.upstream.length})</span>
              </div>
              {data.upstream.length === 0 ? (
                <div className="bg-slate-50 border border-slate-200 px-4 py-6 text-center">
                  <p className="text-xs text-slate-400">No upstream sources found.</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {data.upstream.map((rec) => (
                    <LineageCard key={rec.id} rec={rec} />
                  ))}
                </div>
              )}
            </div>

            <div>
              <div className="flex items-center gap-2 mb-3">
                <div className="w-3 h-3 bg-emerald-500" />
                <p className="text-sm font-semibold text-slate-800">Downstream Derivations</p>
                <span className="text-xs text-slate-400">({data.downstream.length})</span>
              </div>
              {data.downstream.length === 0 ? (
                <div className="bg-slate-50 border border-slate-200 px-4 py-6 text-center">
                  <p className="text-xs text-slate-400">No downstream derivations found.</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {data.downstream.map((rec) => (
                    <LineageCard key={rec.id} rec={rec} />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {!submitted && !isFetching && (
          <div className="bg-white border border-dashed border-slate-300 px-8 py-12 text-center">
            <p className="font-display font-semibold text-slate-700 mb-1">Enter an entity to trace</p>
            <p className="text-slate-400 text-sm">
              Enter an entity type and ID above to explore its full lineage chain — upstream sources and
              downstream derivations across the entire pipeline.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
