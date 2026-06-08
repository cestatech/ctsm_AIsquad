"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/store/authStore";
import { useIntelligenceStudy } from "@/hooks/useIntelligenceStudy";
import { StudyPicker } from "@/components/intelligence/StudyPicker";
import { GraphCanvas } from "@/components/intelligence/GraphCanvas";

export default function ContextGraphPage() {
  const { token } = useAuthStore();
  const { studyId } = useIntelligenceStudy();
  const [nodeCount, setNodeCount] = useState(0);
  const [edgeCount, setEdgeCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    setNodeCount(0);
    setEdgeCount(0);
    setIsLoading(!!studyId);
  }, [studyId]);

  return (
    <div className="flex flex-col h-screen">
      <div className="px-8 py-5 border-b border-slate-200 bg-white shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display text-xl font-bold text-slate-900">Context Graph</h1>
            <p className="text-slate-500 text-sm mt-0.5">
              Study workflow · {nodeCount} nodes · {edgeCount} connections
              {isLoading && " · Loading…"}
            </p>
          </div>
          <StudyPicker />
        </div>
      </div>

      <div className="flex-1 relative">
        {!studyId ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <p className="font-display font-semibold text-slate-700 mb-1">Select a study</p>
              <p className="text-slate-400 text-sm">
                Choose a study above to render its context graph.
              </p>
            </div>
          </div>
        ) : token ? (
          <GraphCanvas
            key={studyId}
            studyId={studyId}
            token={token}
            onCountsChange={(nodes, edges, loading) => {
              setNodeCount(nodes);
              setEdgeCount(edges);
              setIsLoading(loading);
            }}
          />
        ) : null}
      </div>
    </div>
  );
}
