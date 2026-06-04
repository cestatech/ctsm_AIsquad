import { apiClient } from "./client";
import type { GraphEdge, GraphNode, PaginatedResponse } from "@/types";

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
};
