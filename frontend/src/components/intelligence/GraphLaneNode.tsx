"use client";

import { NodeProps } from "reactflow";

export interface GraphLaneNodeData {
  label: string;
  shortLabel: string;
  color: string;
  height: number;
  width: number;
}

export function GraphLaneNode({ data }: NodeProps<GraphLaneNodeData>) {
  return (
    <div
      style={{
        width: data.width,
        height: data.height,
        background: data.color,
        borderRadius: 8,
        border: "1px solid rgba(148, 163, 184, 0.35)",
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          padding: "10px 12px 8px",
          borderBottom: "1px solid rgba(148, 163, 184, 0.25)",
        }}
      >
        <p
          style={{
            fontSize: 10,
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "#64748b",
            margin: 0,
          }}
        >
          {data.label}
        </p>
      </div>
    </div>
  );
}

export const GRAPH_LANE_NODE_TYPES = { lane: GraphLaneNode };
