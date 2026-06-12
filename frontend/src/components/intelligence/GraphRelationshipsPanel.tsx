"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { graphApi } from "@/lib/api/graph";

interface GraphRelationshipsPanelProps {
  externalType: string;
  externalId: string;
  studyId?: string;
  token: string;
  title?: string;
}

export function GraphRelationshipsPanel({
  externalType,
  externalId,
  studyId,
  token,
  title = "Context Graph Relationships",
}: GraphRelationshipsPanelProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["graph-entity", externalType, externalId, token],
    queryFn: () => graphApi.getEntityRelationships(externalType, externalId, token),
    enabled: !!token && !!externalId,
  });

  const nodeId = data?.node?.id;
  const { data: impact } = useQuery({
    queryKey: ["graph-impact", nodeId, token],
    queryFn: () => graphApi.getImpact(nodeId!, token),
    enabled: !!token && !!nodeId,
  });

  if (isLoading) {
    return (
      <div className="text-xs text-slate-400 py-2">Loading graph relationships…</div>
    );
  }

  if (isError || !data) {
    return (
      <div className="text-xs text-slate-400 py-2">No graph data available.</div>
    );
  }

  if (!data.node) {
    return (
      <div className="text-xs text-slate-400 py-2">
        Not yet registered in the context graph.
      </div>
    );
  }

  const outgoing = data.outgoing ?? [];
  const incoming = data.incoming ?? [];

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-slate-700 uppercase tracking-wide">
          {title}
        </h3>
        {studyId && (
          <Link
            href={`/intelligence/graph?study=${studyId}`}
            className="text-[11px] text-brand-600 hover:text-brand-700 font-medium"
          >
            Open graph explorer →
          </Link>
        )}
      </div>

      <div className="text-[11px] text-slate-500">
        Node: <span className="font-mono text-slate-700">{data.node.label}</span>
        <span className="ml-2 text-slate-400">({data.node.node_type})</span>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-[10px] uppercase tracking-wide text-slate-400 mb-1">
            Outgoing ({outgoing.length})
          </p>
          {outgoing.length === 0 ? (
            <p className="text-[11px] text-slate-300">None</p>
          ) : (
            <ul className="space-y-1">
              {outgoing.slice(0, 6).map((edge) => (
                <li key={edge.id} className="text-[11px] text-slate-600 font-mono">
                  → {edge.edge_type}
                  {edge.is_ai_generated && (
                    <span className="ml-1 text-violet-600">AI</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wide text-slate-400 mb-1">
            Incoming ({incoming.length})
          </p>
          {incoming.length === 0 ? (
            <p className="text-[11px] text-slate-300">None</p>
          ) : (
            <ul className="space-y-1">
              {incoming.slice(0, 6).map((edge) => (
                <li key={edge.id} className="text-[11px] text-slate-600 font-mono">
                  ← {edge.edge_type}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {impact && (
        <div className="border-t border-slate-100 pt-3">
          <p className="text-[10px] uppercase tracking-wide text-slate-400 mb-1">
            Downstream impact ({impact.impacted_nodes.length})
          </p>
          {impact.impacted_nodes.length === 0 ? (
            <p className="text-[11px] text-slate-300">No downstream dependencies.</p>
          ) : (
            <ul className="space-y-1">
              {impact.impacted_nodes.slice(0, 5).map((n) => (
                <li key={n.id} className="text-[11px] text-slate-600">
                  {n.name}{" "}
                  <span className="text-slate-400 font-mono text-[10px]">
                    ({n.node_type} · d{n.depth})
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
