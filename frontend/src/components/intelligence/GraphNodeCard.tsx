"use client";

import { Handle, NodeProps, Position } from "reactflow";
import type { GraphNode } from "@/types";
import { getStage, getStageForType } from "@/components/intelligence/graphLayout";

export type NodeColors = { bg: string; border: string; accent: string; text: string };

export const TYPE_COLORS: Record<string, NodeColors> = {
  STUDY: { bg: "#ffffff", border: "#64748b", accent: "#f1f5f9", text: "#334155" },
  PROTOCOL: { bg: "#ffffff", border: "#6366f1", accent: "#eef2ff", text: "#312e81" },
  OBJECTIVE: { bg: "#ffffff", border: "#8b5cf6", accent: "#f5f3ff", text: "#4c1d95" },
  ENDPOINT: { bg: "#ffffff", border: "#3b82f6", accent: "#eff6ff", text: "#1e3a8a" },
  ECR_FIELD: { bg: "#ffffff", border: "#06b6d4", accent: "#ecfeff", text: "#164e63" },
  SDTM_DOMAIN: { bg: "#ffffff", border: "#16a34a", accent: "#f0fdf4", text: "#14532d" },
  SDTM_VARIABLE: { bg: "#ffffff", border: "#22c55e", accent: "#f0fdf4", text: "#14532d" },
  ADAM_VARIABLE: { bg: "#ffffff", border: "#14b8a6", accent: "#f0fdfa", text: "#134e4a" },
  TLF: { bg: "#ffffff", border: "#f59e0b", accent: "#fffbeb", text: "#78350f" },
  CSR_SECTION: { bg: "#ffffff", border: "#f97316", accent: "#fff7ed", text: "#7c2d12" },
  ARTIFACT: { bg: "#ffffff", border: "#64748b", accent: "#f8fafc", text: "#334155" },
  RAW_DATASET: { bg: "#ffffff", border: "#d97706", accent: "#fef3c7", text: "#92400e" },
  ADAM_DATASET: { bg: "#ffffff", border: "#0d9488", accent: "#f0fdfa", text: "#134e4a" },
  INTAKE_SESSION: { bg: "#ffffff", border: "#c026d3", accent: "#fdf4ff", text: "#86198f" },
  STUDY_BRIEF: { bg: "#ffffff", border: "#a21caf", accent: "#fdf4ff", text: "#701a75" },
  AI_DECISION: { bg: "#ffffff", border: "#4f46e5", accent: "#eef2ff", text: "#312e81" },
  SYNTHETIC_DATA_RUN: { bg: "#ffffff", border: "#b45309", accent: "#fffbeb", text: "#78350f" },
};

export const DEFAULT_COLORS: NodeColors = {
  bg: "#ffffff",
  border: "#94a3b8",
  accent: "#f8fafc",
  text: "#334155",
};

export interface GraphNodeCardData {
  graphNode: GraphNode;
  stageId?: number;
  dimmed?: boolean;
}

function formatTypeLabel(nodeType: string): string {
  return nodeType.replace(/_/g, " ");
}

function truncateLabel(label: string, max = 36): string {
  return label.length > max ? `${label.slice(0, max)}…` : label;
}

export function GraphNodeCard({ data, selected }: NodeProps<GraphNodeCardData>) {
  const n = data.graphNode;
  const c = TYPE_COLORS[n.node_type] ?? DEFAULT_COLORS;
  const stage = getStage(data.stageId ?? getStageForType(n.node_type));
  const dimmed = data.dimmed ?? false;

  return (
    <>
      <Handle
        type="target"
        position={Position.Left}
        style={{
          width: 5,
          height: 5,
          background: c.border,
          border: "2px solid #fff",
          opacity: dimmed ? 0.3 : 1,
        }}
      />
      <div
        style={{
          background: c.bg,
          border: `1.5px solid ${selected ? c.border : `${c.border}55`}`,
          borderRadius: 8,
          padding: "8px 10px",
          width: 152,
          opacity: dimmed ? 0.45 : 1,
          boxShadow: selected
            ? `0 0 0 2px ${c.border}33, 0 4px 12px rgba(15,23,42,0.1)`
            : "0 1px 2px rgba(15,23,42,0.06)",
          transition: "box-shadow 0.15s ease, opacity 0.15s ease",
        }}
      >
        <div className="flex items-center gap-1.5 mb-1.5">
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: c.border,
              flexShrink: 0,
            }}
          />
          <span
            style={{
              fontSize: 9,
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "#94a3b8",
            }}
          >
            {stage.shortLabel}
          </span>
        </div>
        <div
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: "#1e293b",
            lineHeight: 1.35,
            wordBreak: "break-word",
          }}
          title={n.label}
        >
          {truncateLabel(n.label)}
        </div>
        <div
          style={{
            fontSize: 9,
            color: "#94a3b8",
            marginTop: 3,
            fontWeight: 500,
          }}
        >
          {formatTypeLabel(n.node_type)}
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Right}
        style={{
          width: 5,
          height: 5,
          background: c.border,
          border: "2px solid #fff",
          opacity: dimmed ? 0.3 : 1,
        }}
      />
    </>
  );
}

export const GRAPH_NODE_TYPES = { context: GraphNodeCard };
