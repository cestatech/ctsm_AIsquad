"use client";

import Link from "next/link";
import type { GapImpactReport, ImpactedNode } from "@/lib/api/graph";

interface ImpactAnalysisViewerProps {
  studyId?: string;
  sourceNodeId: string;
  sourceLabel?: string;
  report: GapImpactReport;
}

const NODE_TYPE_LABELS: Record<string, string> = {
  OBJECTIVE: "Objective",
  ENDPOINT: "Endpoint",
  ECR_FIELD: "eCRF Field",
  ECR_FORM: "eCRF Form",
  SDTM_VARIABLE: "SDTM Variable",
  SDTM_DOMAIN: "SDTM Domain",
  ADAM_VARIABLE: "ADaM Variable",
  ADAM_DATASET: "ADaM Dataset",
  TLF: "TLF",
  CSR_SECTION: "CSR Section",
  STUDY: "Study",
  INTAKE_SESSION: "Intake Session",
  STUDY_BRIEF: "Study Brief",
  ARTIFACT: "Artifact",
  PROTOCOL: "Protocol",
  RAW_DATASET: "Raw Dataset",
  AI_DECISION: "AI Decision",
};

function formatNodeTypeLabel(nodeType: string): string {
  const normalized = nodeType.includes(".")
    ? (nodeType.split(".").pop() ?? nodeType)
    : nodeType;
  return NODE_TYPE_LABELS[normalized] ?? normalized.replace(/_/g, " ");
}

function severityForDepth(depth: number): { label: string; className: string } {
  if (depth <= 2) {
    return { label: "High", className: "bg-red-100 text-red-700" };
  }
  if (depth <= 5) {
    return { label: "Medium", className: "bg-amber-100 text-amber-700" };
  }
  return { label: "Low", className: "bg-slate-100 text-slate-600" };
}

function groupByType(nodes: ImpactedNode[]): Record<string, ImpactedNode[]> {
  return nodes.reduce<Record<string, ImpactedNode[]>>((acc, node) => {
    const key = node.node_type;
    acc[key] = acc[key] ? [...acc[key], node] : [node];
    return acc;
  }, {});
}

export function ImpactAnalysisViewer({
  studyId,
  sourceNodeId,
  sourceLabel,
  report,
}: ImpactAnalysisViewerProps) {
  const grouped = groupByType(report.impacted_nodes);

  if (report.impacted_nodes.length === 0) {
    return (
      <div className="bg-white border border-slate-200 px-8 py-14 text-center">
        <p className="font-display font-semibold text-slate-900 mb-1">
          No downstream impact detected
        </p>
        <p className="text-slate-500 text-sm">
          This node has no outgoing graph links within the traversal depth.
        </p>
        {studyId && (
          <Link
            href={`/intelligence/traceability?study=${studyId}`}
            className="inline-block mt-4 text-sm text-brand-600 hover:text-brand-700 font-medium"
          >
            Back to traceability matrix
          </Link>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="bg-white border border-slate-200 px-5 py-4">
        <p className="text-xs text-slate-500 uppercase tracking-wide font-semibold">
          Source gap node
        </p>
        <p className="text-sm font-medium text-slate-900 mt-1">
          {sourceLabel ?? sourceNodeId.slice(0, 8) + "…"}
        </p>
        <p className="text-xs text-slate-500 mt-1 font-mono">{sourceNodeId}</p>
        <p className="text-xs text-slate-500 mt-2">
          {report.impacted_nodes.length} downstream node
          {report.impacted_nodes.length !== 1 ? "s" : ""} affected
        </p>
      </div>

      {Object.entries(grouped)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([nodeType, nodes]) => (
          <div key={nodeType} className="bg-white border border-slate-200 overflow-hidden">
            <div className="px-5 py-3 border-b border-slate-100 bg-slate-50">
              <h2 className="text-sm font-semibold text-slate-800">
                {formatNodeTypeLabel(nodeType)}
              </h2>
              <p className="text-[11px] text-slate-500 mt-0.5">
                {nodes.length} affected node{nodes.length !== 1 ? "s" : ""}
              </p>
            </div>
            <div className="divide-y divide-slate-100">
              {nodes
                .sort((a, b) => a.depth - b.depth || a.name.localeCompare(b.name))
                .map((node) => {
                  const severity = severityForDepth(node.depth);
                  return (
                    <div
                      key={node.id}
                      className="px-5 py-3 flex items-center justify-between gap-4"
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-slate-900 truncate">
                          {node.name}
                        </p>
                        <p className="text-[11px] text-slate-400 font-mono mt-0.5">
                          Depth {node.depth}
                        </p>
                      </div>
                      <span
                        className={`text-[11px] px-2 py-0.5 font-semibold shrink-0 ${severity.className}`}
                      >
                        {severity.label}
                      </span>
                    </div>
                  );
                })}
            </div>
          </div>
        ))}
    </div>
  );
}

export function ImpactAnalysisSkeleton() {
  return (
    <div className="space-y-4">
      <div className="bg-white border border-slate-200 px-5 py-4">
        <div className="h-3 w-28 bg-slate-100 animate-pulse rounded-sm mb-2" />
        <div className="h-4 w-64 bg-slate-50 animate-pulse rounded-sm" />
      </div>
      {Array.from({ length: 2 }).map((_, index) => (
        <div key={index} className="bg-white border border-slate-200 p-4 space-y-3">
          <div className="h-3 w-32 bg-slate-100 animate-pulse rounded-sm" />
          <div className="h-8 bg-slate-50 animate-pulse rounded-sm" />
          <div className="h-8 bg-slate-50 animate-pulse rounded-sm" />
        </div>
      ))}
    </div>
  );
}
