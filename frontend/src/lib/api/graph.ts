import { apiClient } from "./client";
import type { GraphEdge, GraphNode, PaginatedResponse } from "@/types";

interface NodeListParams {
  study_id?: string;
  node_type?: string;
  page?: number;
  page_size?: number;
}

export const graphApi = {
  listNodes: (params: NodeListParams, token: string) =>
    apiClient.get<PaginatedResponse<GraphNode>>("/graph", {
      params: params as Record<string, string | number | boolean | undefined>,
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
};
