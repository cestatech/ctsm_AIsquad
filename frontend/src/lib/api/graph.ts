import { apiClient } from "./client";
import type { GraphEdge, GraphEvent, GraphNode, PaginatedResponse } from "@/types";

interface NodeListParams {
  study_id?: string;
  node_type?: string;
  page?: number;
  page_size?: number;
}

interface EdgeListParams {
  study_id: string;
  page?: number;
  page_size?: number;
}

export interface TraceabilityGapItem {
  node_id: string;
  node_label: string;
  node_type: string;
  stage_index: number;
  missing_link_from: string;
  message: string;
}

export interface TraceabilityGapReport {
  study_id: string;
  total_nodes: number;
  nodes_with_gaps: number;
  chain_coverage_pct: number;
  gaps: TraceabilityGapItem[];
}

export const graphApi = {
  listNodes: (params: NodeListParams, token: string) =>
    apiClient.get<PaginatedResponse<GraphNode>>("/graph", {
      params: params as Record<string, string | number | boolean | undefined>,
      token,
    }),

  listEdges: (params: EdgeListParams, token: string) =>
    apiClient.get<PaginatedResponse<GraphEdge>>("/graph/edges", {
      params: params as unknown as Record<string, string | number | boolean | undefined>,
      token,
    }),

  getNode: (nodeId: string, token: string) =>
    apiClient.get<GraphNode>(`/graph/${nodeId}`, { token }),

  getNeighbors: (
    nodeId: string,
    params: { direction?: string; edge_type?: string },
    token: string
  ) =>
    apiClient.get<{ outgoing: GraphEdge[]; incoming: GraphEdge[] }>(
      `/graph/${nodeId}/neighbors`,
      { params: params as Record<string, string | number | boolean | undefined>, token }
    ),

  getLineage: (nodeId: string, params: { max_depth?: number }, token: string) =>
    apiClient.get<{ upstream: GraphEdge[]; downstream: GraphEdge[] }>(
      `/graph/${nodeId}/lineage`,
      { params: params as Record<string, string | number | boolean | undefined>, token }
    ),

  getTraceabilityGaps: (studyId: string, token: string) =>
    apiClient.get<TraceabilityGapReport>("/graph/traceability-gaps", {
      params: { study_id: studyId },
      token,
    }),

  listEvents: (
    params: {
      study_id?: string;
      actor_user_id?: string;
      action?: string;
      entity_type?: string;
      event_type?: string;
      page?: number;
      page_size?: number;
    },
    token: string
  ) =>
    apiClient.get<PaginatedResponse<GraphEvent>>("/graph/events", {
      params: params as Record<string, string | number | boolean | undefined>,
      token,
    }),

  getStudySummary: (studyId: string, token: string) =>
    apiClient.get<{
      study_id: string;
      node_count: number;
      edge_count: number;
      event_count: number;
      nodes_by_type: Record<string, number>;
      recent_events: GraphEvent[];
    }>("/graph/study-summary", {
      params: { study_id: studyId },
      token,
    }),

  getEntityRelationships: (
    externalType: string,
    externalId: string,
    token: string
  ) =>
    apiClient.get<{
      external_type: string;
      external_id: string;
      node: GraphNode | null;
      outgoing: GraphEdge[];
      incoming: GraphEdge[];
    }>("/graph/by-entity", {
      params: { external_type: externalType, external_id: externalId },
      token,
    }),

  getImpact: (nodeId: string, token: string, maxDepth = 5) =>
    apiClient.get<{
      node_id: string;
      affected_downstream_count: number;
      affected_nodes: GraphNode[];
      affected_edges: GraphEdge[];
    }>(`/graph/${nodeId}/impact`, {
      params: { max_depth: maxDepth },
      token,
    }),

  getNodeContext: (nodeId: string, token: string) =>
    apiClient.get<GraphNodeContext>(`/graph/${nodeId}/context`, { token }),
};

export interface GraphAIDecisionSummary {
  id: string;
  agent_name: string;
  decision_type: string;
  reasoning: string | null;
  confidence: number | null;
  status: string;
  link_source: string;
  edge_type: string | null;
  edge_id: string | null;
}

export interface GraphNodeContext {
  node: GraphNode;
  outgoing: GraphEdge[];
  incoming: GraphEdge[];
  ai_decisions: GraphAIDecisionSummary[];
}
