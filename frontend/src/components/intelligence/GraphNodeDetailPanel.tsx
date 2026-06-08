"use client";

import { useMemo } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { format } from "date-fns";
import Link from "next/link";
import { graphApi, type GraphAIDecisionSummary } from "@/lib/api/graph";
import { intelligenceApi } from "@/lib/api/intelligence";
import { DEFAULT_COLORS, TYPE_COLORS } from "@/components/intelligence/GraphNodeCard";
import type { AIDecision, AIDecisionStatus, GraphNode } from "@/types";

const STATUS_STYLES: Record<AIDecisionStatus, string> = {
  PENDING_REVIEW: "bg-amber-100 text-amber-800",
  ACCEPTED: "bg-emerald-100 text-emerald-800",
  REJECTED: "bg-red-100 text-red-700",
  OVERRIDDEN: "bg-purple-100 text-purple-800",
};

function ConfidenceBadge({ value }: { value: number | null }) {
  if (value === null) return <span className="text-slate-400 text-[11px]">—</span>;
  const pct = Math.round(value * 100);
  const color = pct >= 90 ? "text-emerald-700" : pct >= 75 ? "text-amber-700" : "text-red-700";
  return <span className={`text-[11px] font-mono font-semibold ${color}`}>{pct}%</span>;
}

function DecisionCard({
  summary,
  full,
  isLoadingFull,
}: {
  summary: GraphAIDecisionSummary;
  full: AIDecision | undefined;
  isLoadingFull: boolean;
}) {
  const status = (full?.status ?? summary.status) as AIDecisionStatus;
  const reasoning = full?.reasoning ?? summary.reasoning;
  const confidence = full?.confidence ?? summary.confidence;

  return (
    <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
      <div className="px-4 py-3 bg-brand-50 border-b border-brand-100 flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wide text-brand-600 mb-1">
            Agent decision
          </p>
          <p className="font-semibold text-slate-900 text-sm">{summary.decision_type}</p>
          <p className="text-[11px] text-slate-500 font-mono mt-0.5">{summary.agent_name}</p>
        </div>
        <span className={`text-[10px] px-2 py-0.5 font-semibold rounded-sm shrink-0 ${STATUS_STYLES[status] ?? "bg-slate-100 text-slate-600"}`}>
          {status.replace(/_/g, " ")}
        </span>
      </div>

      <div className="px-4 py-3 space-y-3">
        <div className="grid grid-cols-2 gap-3 text-[11px]">
          <div>
            <p className="text-slate-400 mb-0.5">Confidence</p>
            <ConfidenceBadge value={confidence} />
          </div>
          {summary.edge_type && (
            <div>
              <p className="text-slate-400 mb-0.5">Via relationship</p>
              <p className="text-slate-700 font-medium">{summary.edge_type.replace(/_/g, " ")}</p>
            </div>
          )}
          {full?.module && (
            <div>
              <p className="text-slate-400 mb-0.5">Module</p>
              <p className="text-slate-700 font-medium">{full.module}</p>
            </div>
          )}
          {full?.created_at && (
            <div>
              <p className="text-slate-400 mb-0.5">Decided</p>
              <p className="text-slate-700">{format(new Date(full.created_at), "MMM d, yyyy HH:mm")}</p>
            </div>
          )}
        </div>

        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 mb-2">
            Reasoning
          </p>
          {isLoadingFull && !reasoning ? (
            <p className="text-[11px] text-slate-400">Loading reasoning…</p>
          ) : reasoning ? (
            <p className="text-[12px] text-slate-700 bg-slate-50 border border-slate-100 rounded-md px-3 py-2.5 leading-relaxed whitespace-pre-wrap">
              {reasoning}
            </p>
          ) : (
            <p className="text-[11px] text-slate-400 italic">No reasoning recorded for this decision.</p>
          )}
        </div>

        {full?.output && Object.keys(full.output).length > 0 && (
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 mb-2">
              Conclusion / output
            </p>
            <pre className="text-[10px] text-slate-600 bg-slate-50 border border-slate-100 rounded-md px-3 py-2 overflow-x-auto font-mono leading-relaxed max-h-32">
              {JSON.stringify(full.output, null, 2)}
            </pre>
          </div>
        )}

        <Link
          href="/intelligence/decisions"
          className="inline-block text-[11px] text-brand-600 hover:text-brand-700 font-medium"
        >
          View full decision record →
        </Link>
      </div>
    </div>
  );
}

interface GraphNodeDetailPanelProps {
  node: GraphNode;
  token: string;
  studyId: string;
  onClose: () => void;
}

export function GraphNodeDetailPanel({
  node,
  token,
  studyId,
  onClose,
}: GraphNodeDetailPanelProps) {
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

  const decisionSummaries = useMemo(
    () => context?.ai_decisions ?? [],
    [context?.ai_decisions]
  );
  const decisionIds = useMemo(
    () => decisionSummaries.map((d) => d.id),
    [decisionSummaries]
  );

  const fullDecisionQueries = useQueries({
    queries: decisionIds.map((id) => ({
      queryKey: ["ai-decision", id, token],
      queryFn: () => intelligenceApi.getDecision(id, token),
      enabled: !!token && !!id,
      staleTime: 60_000,
    })),
  });

  const fullDecisionsById = useMemo(() => {
    const map = new Map<string, AIDecision>();
    decisionIds.forEach((id, i) => {
      const result = fullDecisionQueries[i]?.data;
      if (result) map.set(id, result);
    });
    return map;
  }, [decisionIds, fullDecisionQueries]);

  const artifactLink =
    node.external_type === "artifact" && node.external_id
      ? `/studies/${studyId}/artifacts/${node.external_id}`
      : null;

  return (
    <div className="absolute top-4 right-4 w-[22rem] max-h-[90vh] overflow-y-auto bg-white border border-slate-200 shadow-xl z-10 rounded-lg">
      {/* Node header */}
      <div
        className="px-4 py-3 border-b border-slate-100 flex items-start justify-between gap-2 rounded-t-lg sticky top-0 z-10"
        style={{ background: c.accent }}
      >
        <div>
          <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            {node.node_type.replace(/_/g, " ")}
          </span>
          <p className="font-semibold text-slate-900 mt-1 text-sm leading-snug">{node.label}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-slate-400 hover:text-slate-600 shrink-0 text-lg leading-none"
          aria-label="Close panel"
        >
          &times;
        </button>
      </div>

      {/* Primary: agent decision & reasoning */}
      <div className="px-4 py-4 border-b border-slate-100 bg-slate-50/80">
        <h3 className="text-xs font-semibold text-slate-800 mb-3">Why this node exists</h3>

        {contextLoading ? (
          <div className="space-y-2">
            <div className="h-20 bg-slate-100 rounded-lg animate-pulse" />
            <div className="h-4 bg-slate-100 rounded animate-pulse w-3/4" />
          </div>
        ) : decisionSummaries.length > 0 ? (
          <div className="space-y-3">
            {decisionSummaries.map((summary, index) => (
              <DecisionCard
                key={summary.id}
                summary={summary}
                full={fullDecisionsById.get(summary.id)}
                isLoadingFull={fullDecisionQueries[index]?.isLoading ?? false}
              />
            ))}
          </div>
        ) : (
          <div className="bg-white border border-slate-200 rounded-lg px-4 py-4 text-center">
            <p className="text-sm font-medium text-slate-700 mb-1">No AI decision linked</p>
            <p className="text-[11px] text-slate-500 leading-relaxed">
              This node was not created by an AI agent, or no decision trace has been recorded yet.
            </p>
          </div>
        )}
      </div>

      {/* Secondary metadata */}
      <div className="px-4 py-3 border-b border-slate-100 grid grid-cols-2 gap-3 text-[11px]">
        <div>
          <p className="text-slate-400 mb-0.5">Created</p>
          <p className="text-slate-700 font-medium">
            {format(new Date(node.created_at), "MMM d, yyyy")}
          </p>
        </div>
        <div>
          <p className="text-slate-400 mb-0.5">AI-linked</p>
          <p className={decisionSummaries.length > 0 ? "text-brand-600 font-medium" : "text-slate-600"}>
            {decisionSummaries.length > 0 ? `Yes (${decisionSummaries.length})` : "No"}
          </p>
        </div>
      </div>

      {node.description && (
        <div className="px-4 py-3 border-b border-slate-100">
          <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">
            Description
          </p>
          <p className="text-xs text-slate-600 leading-relaxed">{node.description}</p>
        </div>
      )}

      {artifactLink && (
        <div className="px-4 py-3 border-b border-slate-100">
          <Link href={artifactLink} className="text-xs text-brand-600 hover:text-brand-700 font-medium">
            Open artifact →
          </Link>
        </div>
      )}

      <div className="px-4 py-3 border-b border-slate-100">
        <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-2">
          Relationships
        </p>
        {contextLoading ? (
          <p className="text-[11px] text-slate-400">Loading…</p>
        ) : (
          <div className="space-y-1 text-[11px] text-slate-600">
            <p>
              <span className="font-semibold text-slate-800">{context?.outgoing.length ?? 0}</span>{" "}
              downstream ·{" "}
              <span className="font-semibold text-slate-800">{context?.incoming.length ?? 0}</span>{" "}
              upstream
            </p>
          </div>
        )}
      </div>

      <div className="px-4 py-3">
        <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-2">
          Downstream impact
        </p>
        {impactLoading ? (
          <p className="text-[11px] text-slate-400">Analyzing…</p>
        ) : impact ? (
          <p className="text-[11px] text-slate-600">
            <span className="font-semibold text-slate-900">{impact.affected_downstream_count}</span>{" "}
            node{impact.affected_downstream_count !== 1 ? "s" : ""} affected downstream
          </p>
        ) : (
          <p className="text-[11px] text-slate-400">Unavailable</p>
        )}
      </div>
    </div>
  );
}
