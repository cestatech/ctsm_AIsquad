"use client";

import { useCallback, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  Edge,
  Handle,
  MarkerType,
  MiniMap,
  Node,
  NodeProps,
  Position,
  useEdgesState,
  useNodesState,
} from "reactflow";
import "reactflow/dist/style.css";
import { useAuthStore } from "@/store/authStore";
import { useIntelligenceStudy } from "@/hooks/useIntelligenceStudy";
import { graphApi } from "@/lib/api/graph";
import { StudyPicker } from "@/components/intelligence/StudyPicker";
import type { GraphEdge, GraphNode } from "@/types";

// ─── layout constants ────────────────────────────────────────────────────────

const TYPE_COLUMN: Record<string, number> = {
  STUDY: 0,
  PROTOCOL: 0,
  OBJECTIVE: 1,
  ENDPOINT: 2,
  ECR_FIELD: 3,
  SDTM_VARIABLE: 4,
  ADAM_VARIABLE: 5,
  TLF: 6,
  CSR_SECTION: 7,
};

type NodeColors = { bg: string; border: string; badge: string; text: string };

const TYPE_COLORS: Record<string, NodeColors> = {
  STUDY:          { bg: "#f8fafc", border: "#94a3b8", badge: "#e2e8f0", text: "#334155" },
  PROTOCOL:       { bg: "#eef2ff", border: "#6366f1", badge: "#c7d2fe", text: "#312e81" },
  OBJECTIVE:      { bg: "#f5f3ff", border: "#8b5cf6", badge: "#ddd6fe", text: "#4c1d95" },
  ENDPOINT:       { bg: "#eff6ff", border: "#3b82f6", badge: "#bfdbfe", text: "#1e3a8a" },
  ECR_FIELD:      { bg: "#ecfeff", border: "#06b6d4", badge: "#a5f3fc", text: "#164e63" },
  SDTM_VARIABLE:  { bg: "#f0fdf4", border: "#22c55e", badge: "#bbf7d0", text: "#14532d" },
  ADAM_VARIABLE:  { bg: "#f0fdfa", border: "#14b8a6", badge: "#99f6e4", text: "#134e4a" },
  TLF:            { bg: "#fffbeb", border: "#f59e0b", badge: "#fde68a", text: "#78350f" },
  CSR_SECTION:    { bg: "#fff7ed", border: "#f97316", badge: "#fed7aa", text: "#7c2d12" },
};
const DEFAULT_COLORS: NodeColors = { bg: "#f8fafc", border: "#94a3b8", badge: "#e2e8f0", text: "#334155" };

const COL_W = 200;
const COL_GAP = 80;
const ROW_H = 90;

// ─── custom node ─────────────────────────────────────────────────────────────

function CeleriusNode({ data, selected }: NodeProps) {
  const n = data.graphNode as GraphNode;
  const c = TYPE_COLORS[n.node_type] ?? DEFAULT_COLORS;
  return (
    <>
      <Handle
        type="target"
        position={Position.Left}
        style={{ width: 6, height: 6, background: c.border, border: "none" }}
      />
      <div
        style={{
          background: c.bg,
          border: `1.5px solid ${selected ? c.border : c.border + "99"}`,
          borderRadius: 6,
          padding: "7px 10px",
          width: COL_W,
          boxShadow: selected
            ? `0 0 0 2px ${c.border}44, 0 2px 8px rgba(0,0,0,0.12)`
            : "0 1px 3px rgba(0,0,0,0.07)",
        }}
      >
        <div
          style={{
            display: "inline-block",
            background: c.badge,
            color: c.text,
            fontSize: 9,
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            padding: "1px 5px",
            borderRadius: 3,
            marginBottom: 4,
          }}
        >
          {n.node_type.replace(/_/g, " ")}
        </div>
        <div style={{ fontSize: 12, fontWeight: 600, color: "#1e293b", lineHeight: 1.35, wordBreak: "break-word" }}>
          {n.label}
        </div>
        {n.description && (
          <div style={{ fontSize: 10, color: "#64748b", marginTop: 2, lineHeight: 1.3 }}>
            {n.description.length > 60 ? n.description.slice(0, 60) + "…" : n.description}
          </div>
        )}
      </div>
      <Handle
        type="source"
        position={Position.Right}
        style={{ width: 6, height: 6, background: c.border, border: "none" }}
      />
    </>
  );
}

const NODE_TYPES = { celerius: CeleriusNode };

// ─── layout helpers ──────────────────────────────────────────────────────────

function buildNodes(apiNodes: GraphNode[]): Node[] {
  const colCounts: Record<number, number> = {};
  return apiNodes.map((n) => {
    const col = TYPE_COLUMN[n.node_type] ?? 8;
    const row = colCounts[col] ?? 0;
    colCounts[col] = row + 1;
    return {
      id: n.id,
      type: "celerius",
      position: { x: col * (COL_W + COL_GAP), y: row * ROW_H },
      data: { graphNode: n },
    };
  });
}

function buildEdges(apiEdges: GraphEdge[]): Edge[] {
  return apiEdges.map((e) => ({
    id: e.id,
    source: e.source_node_id,
    target: e.target_node_id,
    animated: e.is_ai_generated ?? false,
    markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14, color: e.is_ai_generated ? "#6366f1" : "#94a3b8" },
    style: { stroke: e.is_ai_generated ? "#6366f1" : "#94a3b8", strokeWidth: 1.5 },
    label: e.edge_type.replace(/_/g, " "),
    labelStyle: { fontSize: 9, fill: "#64748b", fontWeight: 500 },
    labelBgStyle: { fill: "#ffffff", fillOpacity: 0.85 },
    labelBgPadding: [3, 4] as [number, number],
    labelBgBorderRadius: 3,
  }));
}

// ─── detail panel ────────────────────────────────────────────────────────────

function NodeDetail({ node, onClose }: { node: GraphNode; onClose: () => void }) {
  const c = TYPE_COLORS[node.node_type] ?? DEFAULT_COLORS;
  return (
    <div className="absolute top-4 right-4 w-72 bg-white border border-slate-200 shadow-lg z-10 rounded-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 flex items-start justify-between gap-2" style={{ background: c.bg }}>
        <div>
          <span className="text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded-sm" style={{ background: c.badge, color: c.text }}>
            {node.node_type.replace(/_/g, " ")}
          </span>
          <p className="font-semibold text-slate-900 mt-1.5 text-sm leading-snug">{node.label}</p>
        </div>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-600 shrink-0 mt-0.5 text-lg leading-none">&times;</button>
      </div>
      {node.description && (
        <div className="px-4 py-2.5 border-b border-slate-100">
          <p className="text-xs text-slate-600 leading-relaxed">{node.description}</p>
        </div>
      )}
      {Object.keys(node.properties ?? {}).length > 0 && (
        <div className="px-4 py-3">
          <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-2">Properties</p>
          <div className="space-y-1.5">
            {Object.entries(node.properties).map(([k, v]) => (
              <div key={k} className="flex gap-2">
                <span className="text-[11px] text-slate-400 shrink-0 w-24 truncate">{k}</span>
                <span className="text-[11px] font-mono text-slate-700 break-all">{String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="px-4 py-2 border-t border-slate-100 bg-slate-50">
        <p className="text-[10px] text-slate-400 font-mono">{node.id}</p>
      </div>
    </div>
  );
}

// ─── page ────────────────────────────────────────────────────────────────────

export default function ContextGraphPage() {
  const { token } = useAuthStore();
  const { studyId } = useIntelligenceStudy();
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const { isLoading: nodesLoading } = useQuery({
    queryKey: ["graph-nodes", studyId, token],
    queryFn: async () => {
      const data = await graphApi.listNodes({ study_id: studyId!, page_size: 500 }, token!);
      setNodes(buildNodes(data.items));
      return data;
    },
    enabled: !!token && !!studyId,
    staleTime: 60_000,
  });

  const { isLoading: edgesLoading } = useQuery({
    queryKey: ["graph-edges", studyId, token],
    queryFn: async () => {
      const data = await graphApi.listEdges({ study_id: studyId!, page_size: 1000 }, token!);
      setEdges(buildEdges(data.items));
      return data;
    },
    enabled: !!token && !!studyId,
    staleTime: 60_000,
  });

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      setSelectedNode((node.data as { graphNode: GraphNode }).graphNode);
    },
    []
  );

  const isLoading = nodesLoading || edgesLoading;

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="px-8 py-5 border-b border-slate-200 bg-white shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display text-xl font-bold text-slate-900">Context Graph</h1>
            <p className="text-slate-500 text-sm mt-0.5">
              {nodes.length} nodes · {edges.length} edges
              {isLoading && " · Loading…"}
            </p>
          </div>
          <StudyPicker />
        </div>
      </div>

      {/* Canvas */}
      <div className="flex-1 relative">
        {!studyId ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <p className="font-display font-semibold text-slate-700 mb-1">Select a study</p>
              <p className="text-slate-400 text-sm">Choose a study above to render its context graph.</p>
            </div>
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            onPaneClick={() => setSelectedNode(null)}
            nodeTypes={NODE_TYPES}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.1}
            maxZoom={2}
            defaultEdgeOptions={{ type: "smoothstep" }}
          >
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#e2e8f0" />
            <Controls
              style={{ bottom: 16, left: 16 }}
              showInteractive={false}
            />
            <MiniMap
              style={{ bottom: 16, right: 16, width: 160, height: 100 }}
              nodeColor={(n) => {
                const gn = (n.data as { graphNode?: GraphNode }).graphNode;
                return gn ? (TYPE_COLORS[gn.node_type]?.border ?? "#94a3b8") : "#94a3b8";
              }}
              maskColor="rgba(248,250,252,0.8)"
            />
          </ReactFlow>
        )}

        {selectedNode && (
          <NodeDetail node={selectedNode} onClose={() => setSelectedNode(null)} />
        )}
      </div>
    </div>
  );
}
