"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { graphApi } from "@/lib/api/graph";
import { MOCK_GRAPH_EDGES, MOCK_GRAPH_NODES } from "@/lib/mockData";
import type { GraphEdge, GraphNode } from "@/types";

const NODE_TYPE_COLORS: Record<string, string> = {
  STUDY_OBJECTIVE: "bg-violet-100 text-violet-800",
  STUDY_ENDPOINT: "bg-blue-100 text-blue-800",
  ECR_FIELD: "bg-cyan-100 text-cyan-800",
  SDTM_VARIABLE: "bg-emerald-100 text-emerald-800",
  ADAM_VARIABLE: "bg-teal-100 text-teal-800",
  TLF_OUTPUT: "bg-amber-100 text-amber-800",
  CSR_SECTION: "bg-orange-100 text-orange-800",
};

function EdgeRow({ edge, nodes }: { edge: GraphEdge; nodes: GraphNode[] }) {
  const source = nodes.find((n) => n.id === edge.source_node_id);
  const target = nodes.find((n) => n.id === edge.target_node_id);
  return (
    <div className="flex items-start gap-2 text-xs py-2 border-b border-slate-50 last:border-0">
      <div className="flex-1 text-slate-700 truncate" title={source?.label}>
        {source?.label ?? edge.source_node_id.slice(0, 8) + "…"}
      </div>
      <div className="shrink-0 text-slate-400 font-mono text-[11px] bg-slate-50 px-1.5 py-0.5 border border-slate-200">
        {edge.edge_type.replace(/_/g, "→")}
      </div>
      <div className="flex-1 text-slate-700 truncate text-right" title={target?.label}>
        {target?.label ?? edge.target_node_id.slice(0, 8) + "…"}
      </div>
      {edge.is_ai_generated && (
        <span className="shrink-0 text-[10px] px-1.5 py-0.5 bg-blue-100 text-blue-700 font-semibold">AI</span>
      )}
      {edge.confidence !== null && (
        <span className="shrink-0 text-[10px] font-mono text-slate-400">
          {Math.round(edge.confidence * 100)}%
        </span>
      )}
    </div>
  );
}

export default function ContextGraphPage() {
  const { token } = useAuthStore();
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [nodeTypeFilter, setNodeTypeFilter] = useState<string>("ALL");

  const { data: nodes = MOCK_GRAPH_NODES } = useQuery({
    queryKey: ["graph-nodes"],
    queryFn: async () => {
      if (!token) return MOCK_GRAPH_NODES;
      try {
        const res = await graphApi.listNodes({ study_id: "study-001" }, token);
        return res.items;
      } catch {
        return MOCK_GRAPH_NODES;
      }
    },
  });

  const { data: edges = MOCK_GRAPH_EDGES } = useQuery({
    queryKey: ["graph-edges"],
    queryFn: async () => MOCK_GRAPH_EDGES,
  });

  const nodeTypes = ["ALL", ...Array.from(new Set(nodes.map((n) => n.node_type)))];

  const filteredNodes =
    nodeTypeFilter === "ALL" ? nodes : nodes.filter((n) => n.node_type === nodeTypeFilter);

  const adjacentEdges = selectedNode
    ? edges.filter(
        (e) => e.source_node_id === selectedNode.id || e.target_node_id === selectedNode.id
      )
    : [];

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <h1 className="font-display text-xl font-bold text-slate-900">Context Graph Explorer</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Browse the intelligence graph — {nodes.length} nodes, {edges.length} edges. Click a node to inspect its connections.
        </p>
      </div>

      <div className="px-8 py-6">
        <div className="bg-blue-50 border border-blue-200 px-4 py-2.5 mb-4 text-xs text-blue-800">
          Graph visualization (React Flow / Cytoscape) is planned for Phase 7. This view provides
          tabular node and edge browsing with adjacency inspection.
        </div>

        <div className="flex gap-6">
          {/* Node list */}
          <div className="w-80 shrink-0">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold text-slate-700">Nodes</p>
              <select
                value={nodeTypeFilter}
                onChange={(e) => setNodeTypeFilter(e.target.value)}
                className="text-xs border border-slate-200 px-2 py-1 text-slate-600 focus:outline-none focus:border-brand-500 bg-white"
              >
                {nodeTypes.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>

            <div className="bg-white border border-slate-200 overflow-hidden divide-y divide-slate-100">
              {filteredNodes.map((node) => (
                <button
                  key={node.id}
                  onClick={() => setSelectedNode(selectedNode?.id === node.id ? null : node)}
                  className={`w-full text-left px-3 py-2.5 transition-colors ${
                    selectedNode?.id === node.id
                      ? "bg-brand-50 border-l-2 border-brand-400"
                      : "hover:bg-slate-50 border-l-2 border-transparent"
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <span
                      className={`text-[10px] px-1.5 py-0.5 font-semibold mt-0.5 shrink-0 ${
                        NODE_TYPE_COLORS[node.node_type] ?? "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {node.node_type.replace(/_/g, " ")}
                    </span>
                  </div>
                  <p className="text-xs text-slate-800 font-medium mt-1 leading-snug">
                    {node.label}
                  </p>
                </button>
              ))}
            </div>
          </div>

          {/* Node detail */}
          <div className="flex-1">
            {!selectedNode ? (
              <div className="bg-white border border-dashed border-slate-300 px-8 py-16 text-center">
                <p className="font-display font-semibold text-slate-700 mb-1">Select a node</p>
                <p className="text-slate-400 text-sm">
                  Click any node in the list to inspect its properties and connections.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="bg-white border border-slate-200 px-5 py-4">
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div>
                      <span
                        className={`text-[11px] px-2 py-0.5 font-semibold ${
                          NODE_TYPE_COLORS[selectedNode.node_type] ?? "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {selectedNode.node_type}
                      </span>
                      <h2 className="font-display font-semibold text-slate-900 mt-1.5">
                        {selectedNode.label}
                      </h2>
                      {selectedNode.description && (
                        <p className="text-xs text-slate-500 mt-1">{selectedNode.description}</p>
                      )}
                    </div>
                    <p className="text-[11px] text-slate-400 font-mono shrink-0">{selectedNode.id.slice(0, 8)}…</p>
                  </div>

                  {Object.keys(selectedNode.properties).length > 0 && (
                    <div>
                      <p className="text-[11px] text-slate-400 uppercase tracking-wide mb-1.5">Properties</p>
                      <div className="grid grid-cols-2 gap-1.5">
                        {Object.entries(selectedNode.properties).map(([k, v]) => (
                          <div key={k} className="bg-slate-50 border border-slate-100 px-2 py-1.5">
                            <p className="text-[10px] text-slate-400 uppercase tracking-wide">{k}</p>
                            <p className="text-xs font-mono text-slate-700">{String(v)}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <div className="bg-white border border-slate-200 px-5 py-4">
                  <p className="text-xs font-semibold text-slate-700 mb-3">
                    Connections ({adjacentEdges.length})
                  </p>
                  {adjacentEdges.length === 0 ? (
                    <p className="text-xs text-slate-400">No edges connected to this node.</p>
                  ) : (
                    <div>
                      {adjacentEdges.map((edge) => (
                        <EdgeRow key={edge.id} edge={edge} nodes={nodes} />
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
