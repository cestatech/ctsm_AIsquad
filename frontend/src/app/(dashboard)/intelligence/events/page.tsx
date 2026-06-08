"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { useIntelligenceStudy } from "@/hooks/useIntelligenceStudy";
import { graphApi } from "@/lib/api/graph";
import { StudyPicker } from "@/components/intelligence/StudyPicker";
import type { GraphEvent } from "@/types";

function EventRow({ event }: { event: GraphEvent }) {
  const payload = event.payload ?? {};
  const action = (payload.action as string) ?? event.event_type;
  const entityType = (payload.entity_type as string) ?? "—";
  const actor =
    (payload.actor_id as string) ??
    event.actor_agent_id ??
    (event.actor_user_id ? event.actor_user_id.slice(0, 8) : "system");

  return (
    <tr className="hover:bg-slate-50">
      <td className="px-4 py-2.5 text-[11px] text-slate-400 whitespace-nowrap">
        {new Date(event.created_at).toLocaleString()}
      </td>
      <td className="px-4 py-2.5 text-xs font-mono text-slate-700">{event.event_type}</td>
      <td className="px-4 py-2.5 text-xs text-violet-700 font-medium">{action}</td>
      <td className="px-4 py-2.5 text-xs text-slate-600">{entityType}</td>
      <td className="px-4 py-2.5 text-[11px] font-mono text-slate-500 truncate max-w-[140px]">
        {actor}
      </td>
      <td className="px-4 py-2.5 text-[11px] text-slate-500">
        {payload.reason ? String(payload.reason).slice(0, 60) : "—"}
      </td>
    </tr>
  );
}

export default function GraphEventsPage() {
  const { token } = useAuthStore();
  const { studyId } = useIntelligenceStudy();
  const [actionFilter, setActionFilter] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["graph-events", studyId, actionFilter, token],
    queryFn: () =>
      graphApi.listEvents(
        {
          study_id: studyId ?? undefined,
          action: actionFilter || undefined,
          page_size: 100,
        },
        token!
      ),
    enabled: !!token,
  });

  return (
    <div className="px-8 py-6 max-w-6xl">
      <div className="mb-6">
        <h1 className="text-lg font-semibold text-slate-900 font-display">
          Graph Event Log
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Standardized, append-only context graph events for audit and debugging.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-4 mb-5">
        <StudyPicker />
        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="text-xs border border-slate-200 px-3 py-1.5 bg-white text-slate-700"
        >
          <option value="">All actions</option>
          {["created", "generated", "uploaded", "mapped", "approved", "overridden", "linked"].map(
            (a) => (
              <option key={a} value={a}>
                {a}
              </option>
            )
          )}
        </select>
      </div>

      <div className="bg-white border border-slate-200 rounded-sm overflow-hidden">
        {isLoading ? (
          <div className="px-4 py-12 text-center text-sm text-slate-400">Loading events…</div>
        ) : !data?.items.length ? (
          <div className="px-4 py-12 text-center text-sm text-slate-400">
            No graph events found for this filter.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50">
                  {["Time", "Event Type", "Action", "Entity", "Actor", "Reason"].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-2 text-[10px] uppercase tracking-wide text-slate-400 font-semibold"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {data.items.map((event) => (
                  <EventRow key={event.id} event={event} />
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && (
          <div className="px-4 py-2 border-t border-slate-100 text-[11px] text-slate-400">
            {data.total} event{data.total !== 1 ? "s" : ""} total
          </div>
        )}
      </div>
    </div>
  );
}
