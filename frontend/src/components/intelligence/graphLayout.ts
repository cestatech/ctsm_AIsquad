import type { Node } from "reactflow";
import type { GraphEdge, GraphNode } from "@/types";

export const COL_W = 176;
export const COL_GAP = 100;
export const ROW_H = 68;
export const GROUP_GAP = 20;
export const LANE_TOP = 48;

export interface WorkflowStage {
  id: number;
  label: string;
  shortLabel: string;
  types: string[];
  color: string;
}

/** Left-to-right clinical trial pipeline stages */
export const WORKFLOW_STAGES: WorkflowStage[] = [
  {
    id: 0,
    label: "Study Setup",
    shortLabel: "Setup",
    types: ["STUDY", "INTAKE_SESSION", "STUDY_BRIEF", "PROTOCOL", "PROTOCOL_SECTION"],
    color: "#f1f5f9",
  },
  {
    id: 1,
    label: "Trial Design",
    shortLabel: "Design",
    types: ["OBJECTIVE", "ENDPOINT", "ELIGIBILITY_CRITERION", "VISIT", "ASSESSMENT"],
    color: "#eef2ff",
  },
  {
    id: 2,
    label: "Data Collection",
    shortLabel: "Collection",
    types: [
      "ARTIFACT",
      "UPLOADED_FILE",
      "RAW_DATASET",
      "SYNTHETIC_DATA_RUN",
      "ECR_FORM",
      "ECR_FIELD",
      "RAW_DATA_FIELD",
      "EDIT_CHECK",
    ],
    color: "#ecfeff",
  },
  {
    id: 3,
    label: "SDTM",
    shortLabel: "SDTM",
    types: ["SDTM_DOMAIN", "SDTM_VARIABLE"],
    color: "#f0fdf4",
  },
  {
    id: 4,
    label: "ADaM",
    shortLabel: "ADaM",
    types: ["ADAM_DATASET", "ADAM_VARIABLE"],
    color: "#f0fdfa",
  },
  {
    id: 5,
    label: "Outputs",
    shortLabel: "Outputs",
    types: ["TLF", "TLF_CELL", "CSR_SECTION"],
    color: "#fffbeb",
  },
  {
    id: 6,
    label: "AI & Review",
    shortLabel: "AI",
    types: [
      "AI_DECISION",
      "AI_AGENT",
      "AI_RECOMMENDATION",
      "HUMAN_OVERRIDE",
      "VALIDATION_RUN",
      "APPROVAL",
    ],
    color: "#faf5ff",
  },
];

/** High-level milestone nodes — default view for readability */
export const SUMMARY_NODE_TYPES = new Set([
  "STUDY",
  "PROTOCOL",
  "OBJECTIVE",
  "ENDPOINT",
  "RAW_DATASET",
  "SDTM_DOMAIN",
  "ADAM_DATASET",
  "TLF",
  "CSR_SECTION",
  "AI_DECISION",
]);

const TYPE_TO_STAGE = new Map<string, number>();
for (const stage of WORKFLOW_STAGES) {
  for (const type of stage.types) {
    TYPE_TO_STAGE.set(type, stage.id);
  }
}

export function getStageForType(nodeType: string): number {
  return TYPE_TO_STAGE.get(nodeType) ?? 6;
}

export function getStage(stageId: number): WorkflowStage {
  return WORKFLOW_STAGES[stageId] ?? WORKFLOW_STAGES[6];
}

function compareNodes(a: GraphNode, b: GraphNode): number {
  const stageA = getStageForType(a.node_type);
  const stageB = getStageForType(b.node_type);
  if (stageA !== stageB) return stageA - stageB;
  if (a.node_type !== b.node_type) return a.node_type.localeCompare(b.node_type);
  return a.label.localeCompare(b.label);
}

/** Order nodes within a column: group by type, then alphabetical */
function orderColumnNodes(columnNodes: GraphNode[]): GraphNode[] {
  const byType = new Map<string, GraphNode[]>();
  for (const node of columnNodes) {
    const group = byType.get(node.node_type) ?? [];
    group.push(node);
    byType.set(node.node_type, group);
  }

  const ordered: GraphNode[] = [];
  const types = Array.from(byType.keys()).sort();
  for (const type of types) {
    const group = byType.get(type) ?? [];
    group.sort((a, b) => a.label.localeCompare(b.label));
    ordered.push(...group);
  }
  return ordered;
}

export function filterNodesForView(nodes: GraphNode[], summaryOnly: boolean): GraphNode[] {
  if (!summaryOnly) return nodes;
  return nodes.filter((n) => SUMMARY_NODE_TYPES.has(n.node_type));
}

export function layoutWorkflowNodes(
  apiNodes: GraphNode[],
  apiEdges: GraphEdge[]
): { nodes: Node[]; laneHeight: number } {
  const sorted = [...apiNodes].sort(compareNodes);

  const byStage = new Map<number, GraphNode[]>();
  for (const node of sorted) {
    const stage = getStageForType(node.node_type);
    const group = byStage.get(stage) ?? [];
    group.push(node);
    byStage.set(stage, group);
  }

  // BFS depth from study roots for vertical ordering hints within stage
  const studyIds = new Set(
    apiNodes.filter((n) => n.node_type === "STUDY").map((n) => n.id)
  );
  const depth = new Map<string, number>();
  const queue: string[] = Array.from(studyIds);
  for (const id of Array.from(studyIds)) depth.set(id, 0);

  const adjacency = new Map<string, string[]>();
  for (const edge of apiEdges) {
    const list = adjacency.get(edge.source_node_id) ?? [];
    list.push(edge.target_node_id);
    adjacency.set(edge.source_node_id, list);
  }

  while (queue.length > 0) {
    const current = queue.shift()!;
    const currentDepth = depth.get(current) ?? 0;
    for (const next of adjacency.get(current) ?? []) {
      if (!depth.has(next)) {
        depth.set(next, currentDepth + 1);
        queue.push(next);
      }
    }
  }

  const flowNodes: Node[] = [];
  let maxColumnHeight = 0;

  for (const stage of WORKFLOW_STAGES) {
    const columnNodes = byStage.get(stage.id) ?? [];
    if (columnNodes.length === 0) continue;

    const ordered = orderColumnNodes(columnNodes);
    // Secondary sort by graph depth when available
    ordered.sort((a, b) => {
      const depthA = depth.get(a.id) ?? 0;
      const depthB = depth.get(b.id) ?? 0;
      if (depthA !== depthB) return depthA - depthB;
      return a.label.localeCompare(b.label);
    });

    let y = LANE_TOP;
    let prevType: string | null = null;

    for (const node of ordered) {
      if (prevType && prevType !== node.node_type) {
        y += GROUP_GAP;
      }
      prevType = node.node_type;

      flowNodes.push({
        id: node.id,
        type: "context",
        position: { x: stage.id * (COL_W + COL_GAP) + 12, y },
        data: { graphNode: node, stageId: stage.id },
        zIndex: 1,
      });
      y += ROW_H;
    }

    maxColumnHeight = Math.max(maxColumnHeight, y);
  }

  // Swimlane background nodes (non-interactive)
  for (const stage of WORKFLOW_STAGES) {
    const columnNodes = byStage.get(stage.id) ?? [];
    if (columnNodes.length === 0) continue;

    flowNodes.unshift({
      id: `lane-${stage.id}`,
      type: "lane",
      position: { x: stage.id * (COL_W + COL_GAP), y: 0 },
      data: {
        label: stage.label,
        shortLabel: stage.shortLabel,
        color: stage.color,
        height: maxColumnHeight + 32,
        width: COL_W + 24,
      },
      draggable: false,
      selectable: false,
      focusable: false,
      zIndex: 0,
    });
  }

  return { nodes: flowNodes, laneHeight: maxColumnHeight + 48 };
}

export function getConnectedEdgeIds(
  nodeId: string,
  edges: GraphEdge[]
): Set<string> {
  const ids = new Set<string>();
  for (const edge of edges) {
    if (edge.source_node_id === nodeId || edge.target_node_id === nodeId) {
      ids.add(edge.id);
    }
  }
  return ids;
}
