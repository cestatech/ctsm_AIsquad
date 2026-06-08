"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  Edge,
  MarkerType,
  MiniMap,
  Node,
  ReactFlowInstance,
  useEdgesState,
  useNodesState,
} from "reactflow";
import "reactflow/dist/style.css";
import { graphApi } from "@/lib/api/graph";
import { GRAPH_LANE_NODE_TYPES } from "@/components/intelligence/GraphLaneNode";
import {
  COL_W,
  ROW_H,
  filterNodesForView,
  getConnectedEdgeIds,
  layoutWorkflowNodes,
} from "@/components/intelligence/graphLayout";
import { GRAPH_NODE_TYPES, TYPE_COLORS } from "@/components/intelligence/GraphNodeCard";
import { GraphEdgeLegend } from "@/components/intelligence/GraphEdgeLegend";
import { GraphNodeDetailPanel } from "@/components/intelligence/GraphNodeDetailPanel";
import type { GraphEdge, GraphNode } from "@/types";

const NODE_TYPES = { ...GRAPH_LANE_NODE_TYPES, ...GRAPH_NODE_TYPES };

function layoutEdges(
  apiEdges: GraphEdge[],
  options: {
    aiOnly: boolean;
    highlightedEdgeIds: Set<string>;
    showAllLabels: boolean;
  }
): Edge[] {
  const { aiOnly, highlightedEdgeIds, showAllLabels } = options;
  const filtered = aiOnly ? apiEdges.filter((e) => e.is_ai_generated) : apiEdges;

  return filtered.map((e) => {
    const highlighted = highlightedEdgeIds.has(e.id);
    const isAi = e.is_ai_generated;
    const stroke = isAi ? "#6366f1" : "#cbd5e1";
    const showLabel = showAllLabels || highlighted;

    return {
      id: e.id,
      source: e.source_node_id,
      target: e.target_node_id,
      type: "smoothstep",
      animated: isAi && highlighted,
      markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 12,
        height: 12,
        color: highlighted ? (isAi ? "#4f46e5" : "#64748b") : stroke,
      },
      style: {
        stroke: highlighted ? (isAi ? "#4f46e5" : "#64748b") : stroke,
        strokeWidth: highlighted ? 2 : 1,
        opacity: highlighted ? 1 : 0.55,
      },
      label: showLabel ? e.edge_type.replace(/_/g, " ") : undefined,
      labelStyle: { fontSize: 9, fill: "#475569", fontWeight: 500 },
      labelBgStyle: { fill: "#ffffff", fillOpacity: 0.92 },
      labelBgPadding: [4, 6] as [number, number],
      labelBgBorderRadius: 4,
      zIndex: highlighted ? 2 : 0,
    };
  });
}

function mergeGraphNodes(existing: GraphNode[], incoming: GraphNode[]): GraphNode[] {
  const byId = new Map(existing.map((n) => [n.id, n]));
  for (const node of incoming) {
    byId.set(node.id, node);
  }
  return Array.from(byId.values());
}

function mergeGraphEdges(existing: GraphEdge[], incoming: GraphEdge[]): GraphEdge[] {
  const byId = new Map(existing.map((e) => [e.id, e]));
  for (const edge of incoming) {
    byId.set(edge.id, edge);
  }
  return Array.from(byId.values());
}

function getConnectedNodeIds(nodeId: string, edges: GraphEdge[]): Set<string> {
  const ids = new Set<string>([nodeId]);
  for (const edge of edges) {
    if (edge.source_node_id === nodeId) ids.add(edge.target_node_id);
    if (edge.target_node_id === nodeId) ids.add(edge.source_node_id);
  }
  return ids;
}

// ─── canvas ──────────────────────────────────────────────────────────────────

interface GraphCanvasProps {
  studyId: string;
  token: string;
  onCountsChange?: (nodes: number, edges: number, loading: boolean) => void;
}

export function GraphCanvas({ studyId, token, onCountsChange }: GraphCanvasProps) {
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [summaryView, setSummaryView] = useState(true);
  const [aiEdgesOnly, setAiEdgesOnly] = useState(false);
  const [showEdgeLabels, setShowEdgeLabels] = useState(false);
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([]);
  const [expandedNodeIds, setExpandedNodeIds] = useState<Set<string>>(new Set());
  const [isExpanding, setIsExpanding] = useState(false);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const flowRef = useRef<ReactFlowInstance | null>(null);
  const expandTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const graphNodesRef = useRef(graphNodes);
  const expandedNodeIdsRef = useRef(expandedNodeIds);
  graphNodesRef.current = graphNodes;
  expandedNodeIdsRef.current = expandedNodeIds;

  const {
    data: nodesData,
    isLoading: nodesLoading,
    isFetching: nodesFetching,
    isError: nodesError,
  } = useQuery({
    queryKey: ["graph-nodes", studyId, token],
    queryFn: () => graphApi.listNodes({ study_id: studyId, page_size: 200 }, token),
    enabled: !!token && !!studyId,
    staleTime: 0,
  });

  const {
    data: edgesData,
    isLoading: edgesLoading,
    isFetching: edgesFetching,
    isError: edgesError,
  } = useQuery({
    queryKey: ["graph-edges", studyId, token],
    queryFn: () => graphApi.listEdges({ study_id: studyId, page_size: 500 }, token),
    enabled: !!token && !!studyId,
    staleTime: 0,
  });

  useEffect(() => {
    setGraphNodes([]);
    setGraphEdges([]);
    setExpandedNodeIds(new Set());
    setSelectedNode(null);
    setNodes([]);
    setEdges([]);
  }, [studyId, setNodes, setEdges]);

  useEffect(() => {
    if (nodesData?.items) {
      setGraphNodes(nodesData.items);
      setExpandedNodeIds(new Set());
      setSelectedNode(null);
    }
  }, [nodesData]);

  useEffect(() => {
    if (edgesData?.items) {
      setGraphEdges(edgesData.items);
    }
  }, [edgesData]);

  const visibleGraphNodes = useMemo(
    () => filterNodesForView(graphNodes, summaryView),
    [graphNodes, summaryView]
  );

  const visibleNodeIds = useMemo(
    () => new Set(visibleGraphNodes.map((n) => n.id)),
    [visibleGraphNodes]
  );

  const filteredGraphEdges = useMemo(() => {
    let result = graphEdges.filter(
      (e) => visibleNodeIds.has(e.source_node_id) && visibleNodeIds.has(e.target_node_id)
    );
    if (aiEdgesOnly) {
      result = result.filter((e) => e.is_ai_generated);
    }
    return result;
  }, [graphEdges, visibleNodeIds, aiEdgesOnly]);

  const highlightedEdgeIds = useMemo(() => {
    if (!selectedNode) return new Set<string>();
    return getConnectedEdgeIds(selectedNode.id, filteredGraphEdges);
  }, [selectedNode, filteredGraphEdges]);

  const connectedNodeIds = useMemo(() => {
    if (!selectedNode) return null;
    return getConnectedNodeIds(selectedNode.id, filteredGraphEdges);
  }, [selectedNode, filteredGraphEdges]);

  useEffect(() => {
    const { nodes: laidOut } = layoutWorkflowNodes(visibleGraphNodes, filteredGraphEdges);

    const withHighlight = laidOut.map((node) => {
      if (node.type === "lane") return node;
      const graphNode = node.data.graphNode as GraphNode;
      const dimmed =
        connectedNodeIds !== null && !connectedNodeIds.has(node.id);
      return {
        ...node,
        data: { ...node.data, graphNode, dimmed },
      };
    });

    setNodes(withHighlight);
    setEdges(
      layoutEdges(filteredGraphEdges, {
        aiOnly: aiEdgesOnly,
        highlightedEdgeIds,
        showAllLabels: showEdgeLabels,
      })
    );
  }, [
    visibleGraphNodes,
    filteredGraphEdges,
    aiEdgesOnly,
    highlightedEdgeIds,
    showEdgeLabels,
    connectedNodeIds,
    setNodes,
    setEdges,
  ]);

  const isLoading = nodesLoading || edgesLoading;
  const isSwitchingStudy = nodesFetching || edgesFetching;
  const hasError = nodesError || edgesError;

  useEffect(() => {
    onCountsChange?.(visibleGraphNodes.length, filteredGraphEdges.length, isLoading);
  }, [visibleGraphNodes.length, filteredGraphEdges.length, isLoading, onCountsChange]);

  const expandNodeNeighbors = useCallback(
    async (nodeId: string) => {
      if (expandedNodeIdsRef.current.has(nodeId) || isExpanding) return;

      setIsExpanding(true);
      try {
        const neighbors = await graphApi.getNeighbors(nodeId, {}, token);
        const neighborEdges = [...neighbors.outgoing, ...neighbors.incoming];
        const knownNodes = graphNodesRef.current;
        const unknownIds = new Set<string>();

        for (const edge of neighborEdges) {
          if (!knownNodes.find((n) => n.id === edge.source_node_id)) {
            unknownIds.add(edge.source_node_id);
          }
          if (!knownNodes.find((n) => n.id === edge.target_node_id)) {
            unknownIds.add(edge.target_node_id);
          }
        }

        const fetchedNodes = await Promise.all(
          Array.from(unknownIds).map((id) => graphApi.getNode(id, token))
        );

        setGraphNodes((prev) => mergeGraphNodes(prev, fetchedNodes));
        setGraphEdges((prev) => mergeGraphEdges(prev, neighborEdges));
        setExpandedNodeIds((prev) => new Set(prev).add(nodeId));
      } finally {
        setIsExpanding(false);
      }
    },
    [isExpanding, token]
  );

  const expandVisibleBoundaryNodes = useCallback(() => {
    const instance = flowRef.current;
    if (!instance || isExpanding) return;

    const viewport = instance.getViewport();
    const { x, y, zoom } = viewport;
    const bounds = {
      left: -x / zoom,
      top: -y / zoom,
      right: (-x + window.innerWidth) / zoom,
      bottom: (-y + window.innerHeight) / zoom,
    };
    const margin = 120 / zoom;

    const boundaryNodes = nodes.filter((node) => {
      if (node.type === "lane") return false;
      const px = node.position.x;
      const py = node.position.y;
      const nearEdge =
        px < bounds.left + margin ||
        px > bounds.right - margin - COL_W ||
        py < bounds.top + margin ||
        py > bounds.bottom - margin - ROW_H;
      return nearEdge && !expandedNodeIds.has(node.id);
    });

    if (boundaryNodes.length > 0) {
      void expandNodeNeighbors(boundaryNodes[0].id);
    }
  }, [nodes, expandedNodeIds, isExpanding, expandNodeNeighbors]);

  const onMoveEnd = useCallback(() => {
    if (expandTimerRef.current) clearTimeout(expandTimerRef.current);
    expandTimerRef.current = setTimeout(() => {
      expandVisibleBoundaryNodes();
    }, 400);
  }, [expandVisibleBoundaryNodes]);

  useEffect(() => {
    return () => {
      if (expandTimerRef.current) clearTimeout(expandTimerRef.current);
    };
  }, []);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    if (node.type === "lane") return;
    setSelectedNode(node.data.graphNode as GraphNode);
  }, []);

  const onNodeDoubleClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      if (node.type === "lane") return;
      void expandNodeNeighbors(node.id);
    },
    [expandNodeNeighbors]
  );

  const aiEdgeCount = filteredGraphEdges.filter((e) => e.is_ai_generated).length;
  const humanEdgeCount = filteredGraphEdges.length - aiEdgeCount;

  if (hasError) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-sm text-red-600">Failed to load graph data. Refresh the page.</p>
      </div>
    );
  }

  if (graphNodes.length === 0 && !isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center max-w-sm">
          <p className="font-display font-semibold text-slate-700 mb-1">No graph nodes yet</p>
          <p className="text-slate-400 text-sm">
            Run intake, upload raw data, or generate SDTM/ADaM to populate the context graph.
          </p>
        </div>
      </div>
    );
  }

  if (isLoading && graphNodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-sm text-slate-400">Loading context graph…</p>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full bg-slate-50/50">
      {isSwitchingStudy && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-slate-50/80 backdrop-blur-[1px]">
          <p className="text-sm text-slate-500">Loading context graph…</p>
        </div>
      )}

      <div className="absolute top-3 left-3 z-10 flex flex-wrap items-center gap-2 bg-white border border-slate-200 shadow-sm rounded-lg px-3 py-2">
        <div className="flex rounded-md border border-slate-200 overflow-hidden">
          <button
            type="button"
            onClick={() => setSummaryView(true)}
            className={`px-2.5 py-1 text-[11px] font-medium transition-colors ${
              summaryView
                ? "bg-slate-900 text-white"
                : "bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            Workflow
          </button>
          <button
            type="button"
            onClick={() => setSummaryView(false)}
            className={`px-2.5 py-1 text-[11px] font-medium transition-colors ${
              !summaryView
                ? "bg-slate-900 text-white"
                : "bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            Full detail
          </button>
        </div>

        <label className="flex items-center gap-1.5 text-[11px] text-slate-600 cursor-pointer">
          <input
            type="checkbox"
            checked={aiEdgesOnly}
            onChange={(e) => setAiEdgesOnly(e.target.checked)}
            className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
          />
          AI edges only
        </label>

        <label className="flex items-center gap-1.5 text-[11px] text-slate-600 cursor-pointer">
          <input
            type="checkbox"
            checked={showEdgeLabels}
            onChange={(e) => setShowEdgeLabels(e.target.checked)}
            className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
          />
          Edge labels
        </label>

        {isExpanding && <span className="text-[10px] text-slate-400">Expanding…</span>}
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onNodeDoubleClick={onNodeDoubleClick}
        onPaneClick={() => setSelectedNode(null)}
        onMoveEnd={onMoveEnd}
        onInit={(instance) => {
          flowRef.current = instance;
        }}
        nodeTypes={NODE_TYPES}
        nodesDraggable
        nodesConnectable={false}
        elementsSelectable
        fitView
        fitViewOptions={{ padding: 0.15, maxZoom: 1 }}
        minZoom={0.2}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Lines} gap={24} size={1} color="#e2e8f0" />
        <Controls
          style={{ bottom: 16, left: 16 }}
          showInteractive={false}
          className="!shadow-sm !border-slate-200 !rounded-lg"
        />
        <MiniMap
          style={{ bottom: 16, right: 16, width: 140, height: 90 }}
          nodeColor={(n) => {
            if (n.type === "lane") return "transparent";
            const gn = n.data?.graphNode as GraphNode | undefined;
            return gn ? (TYPE_COLORS[gn.node_type]?.border ?? "#94a3b8") : "#94a3b8";
          }}
          maskColor="rgba(248,250,252,0.85)"
          pannable
          zoomable
        />
      </ReactFlow>

      <GraphEdgeLegend aiEdgeCount={aiEdgeCount} humanEdgeCount={humanEdgeCount} />

      {selectedNode && (
        <GraphNodeDetailPanel
          node={selectedNode}
          token={token}
          studyId={studyId}
          onClose={() => setSelectedNode(null)}
        />
      )}
    </div>
  );
}
