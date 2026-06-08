"use client";

import { useCallback, useEffect, useState } from "react";
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
import Link from "next/link";
import { graphApi } from "@/lib/api/graph";
import { StudyPicker } from "@/components/intelligence/StudyPicker";
import type { GraphEdge, GraphNode } from "@/types";

// ─── layout constants ────────────────────────────────────────────────────────

const TYPE_COLUMN: Record<string, number> = {
  STUDY: 0,
  INTAKE_SESSION: 0,
  STUDY_BRIEF: 0,
  PROTOCOL: 0,
  ARTIFACT: 1,
  UPLOADED_FILE: 1,
  RAW_DATASET: 1,
  SYNTHETIC_DATA_RUN: 1,
  OBJECTIVE: 2,
  ENDPOINT: 3,
  ECR_FIELD: 4,
  RAW_DATA_FIELD: 4,
  SDTM_DOMAIN: 5,
  SDTM_VARIABLE: 5,
  ADAM_DATASET: 6,
  ADAM_VARIABLE: 6,
  TLF: 7,
  CSR_SECTION: 8,
  AI_DECISION: 9,
  AI_AGENT: 9,
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
  ARTIFACT:       { bg: "#f1f5f9", border: "#64748b", badge: "#e2e8f0", text: "#334155" },
  RAW_DATASET:    { bg: "#fef3c7", border: "#d97706", badge: "#fde68a", text: "#92400e" },
  ADAM_DATASET:   { bg: "#f0fdfa", border: "#0d9488", badge: "#99f6e4", text: "#134e4a" },
  INTAKE_SESSION: { bg: "#fdf4ff", border: "#c026d3", badge: "#f5d0fe", text: "#86198f" },
  STUDY_BRIEF:    { bg: "#fdf4ff", border: "#a21caf", badge: "#f5d0fe", text: "#701a75" },
  AI_DECISION:    { bg: "#eef2ff", border: "#4f46e5", badge: "#c7d2fe", text: "#312e81" },
  SYNTHETIC_DATA_RUN: { bg: "#fffbeb", border: "#b45309", badge: "#fde68a", text: "#78350f" },
};
const DEFAULT_COLORS: NodeColors = { bg: "#f8fafc", border: "#94a3b8", badge: "#e2e8f0", text: "#334155" };

const COL_W = 200;
const COL_GAP = 80;
const ROW_H = 90;

// ─── custom node ─────────────────────────────────────────────────────────────

function ContextGraphNode({ data, selected }: NodeProps) {
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

const NODE_TYPES = { context: ContextGraphNode };

// ─── layout helpers ──────────────────────────────────────────────────────────

function buildNodes(apiNodes: GraphNode[]): Node[] {
  const colCounts: Record<number, number> = {};
  return apiNodes.map((n) => {
    const col = TYPE_COLUMN[n.node_type] ?? 8;
    const row = colCounts[col] ?? 0;
    colCounts[col] = row + 1;
    return {
      id: n.id,
      type: "context",
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

function NodeDetail({
  node,
  token,
  studyId,
  onClose,
}: {
  node: GraphNode;
  token: string;
  studyId: string | null;
  onClose: () => void;
}) {
  const c = TYPE_COLORS[node.node_type] ?? DEFAULT_COLORS;

  const { data: context, isLoading: contextLoading } = useQuery({
    queryKey: ["graph-context", node.id, token],
    queryFn: () => graphApi.getNodeContext(node.id, token),
    enabled: !!token && !!node.id,
  });

  const { data: impact, isLoading: impactLoading } = useQuery({
    queryKey: ["graph-impact", node.id, token],
    queryFn: () => graphApi.getImpact(node.id, token),
    enabled: !!token && !!node.id,
  });

  const artifactLink =
    node.external_type === "artifact" && node.external_id && studyId
      ? `/studies/${studyId}/artifacts/${node.external_id}`
      : null;

  return (
    <div className="absolute top-4 right-4 w-96 max-h-[85vh] overflow-y-auto bg-white border border-slate-200 shadow-lg z-10 rounded-sm">
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
      {artifactLink && (
        <div className="px-4 py-2.5 border-b border-slate-100">
          <Link
            href={artifactLink}
            className="text-xs text-brand-600 hover:text-brand-700 font-medium"
          >
            Open artifact →
          </Link>
        </div>
      )}
      {Object.keys(node.properties ?? {}).length > 0 && (
        <div className="px-4 py-3 border-b border-slate-100">
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
      <div className="px-4 py-3 border-b border-slate-100">
        <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-2">
          AI reasoning
        </p>
        {contextLoading ? (
          <p className="text-[11px] text-slate-400">Loading reasoning…</p>
        ) : context?.ai_decisions.length ? (
          <div className="space-y-2 max-h-40 overflow-y-auto">
            {context.ai_decisions.map((d) => (
              <div key={d.id} className="bg-indigo-50 border border-indigo-100 px-2.5 py-2 rounded-sm">
                <p className="text-[10px] font-semibold text-indigo-900">
                  {d.agent_name} · {d.decision_type}
                </p>
                {d.edge_type && (
                  <p className="text-[10px] text-indigo-600 mt-0.5">
                    via {d.edge_type.replace(/_/g, " ")}
                  </p>
                )}
                <p className="text-[11px] text-slate-700 mt-1 leading-relaxed">
                  {d.reasoning ?? "No reasoning recorded."}
                </p>
                <Link
                  href={`/intelligence/decisions`}
                  className="text-[10px] text-brand-600 hover:text-brand-700 mt-1 inline-block"
                >
                  View in decisions →
                </Link>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-[11px] text-slate-400">No linked AI decisions for this node.</p>
        )}
      </div>
      <div className="px-4 py-3 border-b border-slate-100">
        <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-2">
          Relationships
        </p>
        {contextLoading ? (
          <p className="text-[11px] text-slate-400">Loading…</p>
        ) : (
          <div className="space-y-1 text-[11px] text-slate-600">
            <p>
              <span className="font-semibold">{context?.outgoing.length ?? 0}</span> outgoing ·{" "}
              <span className="font-semibold">{context?.incoming.length ?? 0}</span> incoming
            </p>
            {(context?.outgoing ?? []).slice(0, 3).map((e) => (
              <p key={e.id} className="truncate">
                → {e.edge_type.replace(/_/g, " ")}
                {e.is_ai_generated && (
                  <span className="text-indigo-600 ml-1">(AI)</span>
                )}
              </p>
            ))}
          </div>
        )}
      </div>
      <div className="px-4 py-3 border-b border-slate-100">
        <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-2">
          Downstream impact
        </p>
        {impactLoading ? (
          <p className="text-[11px] text-slate-400">Analyzing…</p>
        ) : impact ? (
          <div className="space-y-2">
            <p className="text-[11px] text-slate-600">
              <span className="font-semibold text-slate-900">
                {impact.affected_downstream_count}
              </span>{" "}
              downstream node{impact.affected_downstream_count !== 1 ? "s" : ""} affected
            </p>
            {impact.affected_nodes.length > 0 ? (
              <ul className="space-y-1 max-h-28 overflow-y-auto">
                {impact.affected_nodes.slice(0, 8).map((n) => (
                  <li key={n.id} className="text-[11px] text-slate-600 flex justify-between gap-2">
                    <span className="truncate">{n.label}</span>
                    <span className="text-slate-400 shrink-0 font-mono text-[10px]">
                      {n.node_type}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-[11px] text-slate-400">No downstream dependencies.</p>
            )}
          </div>
        ) : (
          <p className="text-[11px] text-slate-400">Impact data unavailable.</p>
        )}
      </div>
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

  const {
    data: nodesData,
    isLoading: nodesLoading,
    isError: nodesError,
  } = useQuery({
    queryKey: ["graph-nodes", studyId, token],
    queryFn: () => graphApi.listNodes({ study_id: studyId!, page_size: 200 }, token!),
    enabled: !!token && !!studyId,
    staleTime: 60_000,
  });

  const {
    data: edgesData,
    isLoading: edgesLoading,
    isError: edgesError,
  } = useQuery({
    queryKey: ["graph-edges", studyId, token],
    queryFn: () => graphApi.listEdges({ study_id: studyId!, page_size: 500 }, token!),
    enabled: !!token && !!studyId,
    staleTime: 60_000,
  });

  useEffect(() => {
    if (nodesData?.items) {
      setNodes(buildNodes(nodesData.items));
    }
  }, [nodesData, setNodes]);

  useEffect(() => {
    if (edgesData?.items) {
      setEdges(buildEdges(edgesData.items));
    }
  }, [edgesData, setEdges]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      setSelectedNode((node.data as { graphNode: GraphNode }).graphNode);
    },
    []
  );

  const isLoading = nodesLoading || edgesLoading;
  const hasError = nodesError || edgesError;
  const nodeCount = nodesData?.items.length ?? nodes.length;
  const edgeCount = edgesData?.items.length ?? edges.length;

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="px-8 py-5 border-b border-slate-200 bg-white shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display text-xl font-bold text-slate-900">Context Graph</h1>
            <p className="text-slate-500 text-sm mt-0.5">
              {nodeCount} nodes · {edgeCount} edges
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
        ) : hasError ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm text-red-600">Failed to load graph data. Refresh the page.</p>
          </div>
        ) : nodeCount === 0 && !isLoading ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center max-w-sm">
              <p className="font-display font-semibold text-slate-700 mb-1">No graph nodes yet</p>
              <p className="text-slate-400 text-sm">
                Run intake, upload raw data, or generate SDTM/ADaM to populate the context graph.
              </p>
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

        {selectedNode && token && (
          <NodeDetail
            node={selectedNode}
            token={token}
            studyId={studyId}
            onClose={() => setSelectedNode(null)}
          />
        )}
      </div>
    </div>
  );
}
