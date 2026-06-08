"use client";

import { useState } from "react";

interface GraphEdgeLegendProps {
  aiEdgeCount: number;
  humanEdgeCount: number;
}

export function GraphEdgeLegend({ aiEdgeCount, humanEdgeCount }: GraphEdgeLegendProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="absolute bottom-4 right-52 z-10">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="bg-white/95 border border-slate-200 shadow-sm rounded-sm px-3 py-1.5 text-[10px] font-medium text-slate-500 hover:text-slate-700"
      >
        {open ? "Hide legend" : "Legend"}
      </button>
      {open && (
        <div className="mt-1.5 bg-white/95 border border-slate-200 shadow-sm rounded-sm px-3 py-2.5 w-44">
          <div className="space-y-2 text-[11px] text-slate-600">
            <span className="flex items-center gap-2">
              <span className="inline-block w-6 h-px bg-slate-300" />
              Human ({humanEdgeCount})
            </span>
            <span className="flex items-center gap-2">
              <span className="inline-block w-6 h-px bg-brand-500" />
              <span className="text-brand-600">AI ({aiEdgeCount})</span>
            </span>
          </div>
          <p className="text-[10px] text-slate-400 mt-2 leading-relaxed">
            Click a node to highlight its connections. Double-click to expand neighbors.
          </p>
        </div>
      )}
    </div>
  );
}
