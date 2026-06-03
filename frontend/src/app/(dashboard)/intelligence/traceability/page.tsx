"use client";

import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { MOCK_GRAPH_EDGES, MOCK_GRAPH_NODES } from "@/lib/mockData";
import type { GraphEdge, GraphNode } from "@/types";

const CHAIN_STAGES = [
  { key: "STUDY_OBJECTIVE", label: "Objective", color: "bg-violet-500", text: "text-violet-900", bg: "bg-violet-50", border: "border-violet-200" },
  { key: "STUDY_ENDPOINT", label: "Endpoint", color: "bg-blue-500", text: "text-blue-900", bg: "bg-blue-50", border: "border-blue-200" },
  { key: "ECR_FIELD", label: "eCRF Field", color: "bg-cyan-500", text: "text-cyan-900", bg: "bg-cyan-50", border: "border-cyan-200" },
  { key: "SDTM_VARIABLE", label: "SDTM", color: "bg-emerald-500", text: "text-emerald-900", bg: "bg-emerald-50", border: "border-emerald-200" },
  { key: "ADAM_VARIABLE", label: "ADaM", color: "bg-teal-500", text: "text-teal-900", bg: "bg-teal-50", border: "border-teal-200" },
  { key: "TLF_OUTPUT", label: "TLF", color: "bg-amber-500", text: "text-amber-900", bg: "bg-amber-50", border: "border-amber-200" },
  { key: "CSR_SECTION", label: "CSR", color: "bg-orange-500", text: "text-orange-900", bg: "bg-orange-50", border: "border-orange-200" },
];

function isLinked(
  sourceNode: GraphNode,
  targetNode: GraphNode,
  edges: GraphEdge[]
): GraphEdge | undefined {
  return edges.find(
    (e) => e.source_node_id === sourceNode.id && e.target_node_id === targetNode.id
  );
}

export default function TraceabilityMatrixPage() {
  const { token } = useAuthStore();

  const { data: nodes = MOCK_GRAPH_NODES } = useQuery({
    queryKey: ["graph-nodes-trace"],
    queryFn: async () => {
      if (!token) return MOCK_GRAPH_NODES;
      return MOCK_GRAPH_NODES;
    },
  });

  const { data: edges = MOCK_GRAPH_EDGES } = useQuery({
    queryKey: ["graph-edges-trace"],
    queryFn: async () => MOCK_GRAPH_EDGES,
  });

  const nodesByType = CHAIN_STAGES.reduce<Record<string, GraphNode[]>>((acc, stage) => {
    acc[stage.key] = nodes.filter((n) => n.node_type === stage.key);
    return acc;
  }, {});

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <h1 className="font-display text-xl font-bold text-slate-900">Traceability Matrix</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          End-to-end chain: Objective → Endpoint → eCRF → SDTM → ADaM → TLF → CSR
        </p>
      </div>

      <div className="px-8 py-6">
        {/* Pipeline header */}
        <div className="flex gap-0 mb-6 overflow-x-auto">
          {CHAIN_STAGES.map((stage, i) => (
            <div key={stage.key} className="flex items-center">
              <div className={`flex items-center gap-2 px-3 py-2 ${stage.bg} border ${stage.border}`}>
                <div className={`w-2 h-2 rounded-full ${stage.color}`} />
                <span className={`text-xs font-semibold font-display ${stage.text}`}>{stage.label}</span>
                <span className={`text-[11px] ${stage.text} opacity-60`}>
                  ({nodesByType[stage.key]?.length ?? 0})
                </span>
              </div>
              {i < CHAIN_STAGES.length - 1 && (
                <div className="text-slate-400 text-xs px-0.5 shrink-0">→</div>
              )}
            </div>
          ))}
        </div>

        {/* Chain rows */}
        <div className="space-y-4">
          {CHAIN_STAGES.map((stage, stageIdx) => {
            const stageNodes = nodesByType[stage.key] ?? [];
            if (stageNodes.length === 0) return null;

            return (
              <div key={stage.key} className="bg-white border border-slate-200 overflow-hidden">
                <div className={`px-4 py-2 ${stage.bg} border-b ${stage.border}`}>
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${stage.color}`} />
                    <span className={`text-xs font-semibold font-display ${stage.text}`}>
                      {stage.label}
                    </span>
                  </div>
                </div>

                <div className="divide-y divide-slate-50">
                  {stageNodes.map((node) => {
                    const prevStage = stageIdx > 0 ? CHAIN_STAGES[stageIdx - 1] : null;
                    const nextStage = stageIdx < CHAIN_STAGES.length - 1 ? CHAIN_STAGES[stageIdx + 1] : null;
                    const prevNodes = prevStage ? nodesByType[prevStage.key] ?? [] : [];
                    const nextNodes = nextStage ? nodesByType[nextStage.key] ?? [] : [];

                    const incomingLinks = prevNodes.filter(
                      (prev) => !!isLinked(prev, node, edges)
                    );
                    const outgoingLinks = nextNodes.filter(
                      (next) => !!isLinked(node, next, edges)
                    );

                    const linkEdge =
                      incomingLinks.length > 0
                        ? isLinked(incomingLinks[0], node, edges)
                        : undefined;

                    return (
                      <div key={node.id} className="px-4 py-3 flex items-start gap-4">
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium text-slate-900 leading-snug">
                            {node.label}
                          </p>
                          {node.description && (
                            <p className="text-[11px] text-slate-400 mt-0.5 leading-relaxed">
                              {node.description}
                            </p>
                          )}
                        </div>

                        <div className="flex items-center gap-3 text-[11px] shrink-0">
                          {incomingLinks.length > 0 && (
                            <div className="flex items-center gap-1 text-slate-400">
                              <span className="text-blue-500">←</span>
                              {incomingLinks.length} source{incomingLinks.length !== 1 ? "s" : ""}
                              {linkEdge?.is_ai_generated && (
                                <span className="ml-1 px-1.5 py-0.5 bg-blue-100 text-blue-700 font-semibold text-[10px]">
                                  AI
                                </span>
                              )}
                              {linkEdge?.confidence !== null && linkEdge?.confidence !== undefined && (
                                <span className="text-slate-400 font-mono">
                                  {Math.round(linkEdge.confidence * 100)}%
                                </span>
                              )}
                            </div>
                          )}
                          {outgoingLinks.length > 0 && (
                            <div className="flex items-center gap-1 text-slate-400">
                              <span className="text-emerald-500">→</span>
                              {outgoingLinks.length} derivation{outgoingLinks.length !== 1 ? "s" : ""}
                            </div>
                          )}
                          {incomingLinks.length === 0 && stageIdx > 0 && (
                            <span className="text-amber-600 font-semibold">⚠ No upstream link</span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-4 flex items-center gap-4 text-[11px] text-slate-400">
          <span className="flex items-center gap-1">
            <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 font-semibold text-[10px]">AI</span>
            AI-generated link
          </span>
          <span className="flex items-center gap-1 text-amber-600 font-semibold">
            ⚠ No upstream link — traceability gap
          </span>
        </div>
      </div>
    </div>
  );
}
