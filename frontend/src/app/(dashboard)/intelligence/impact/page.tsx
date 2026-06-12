"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { useIntelligenceStudy } from "@/hooks/useIntelligenceStudy";
import { graphApi } from "@/lib/api/graph";
import { StudyPicker } from "@/components/intelligence/StudyPicker";
import {
  ImpactAnalysisSkeleton,
  ImpactAnalysisViewer,
} from "@/components/intelligence/ImpactAnalysisViewer";

export default function ImpactAnalysisPage() {
  const { token } = useAuthStore();
  const { studyId } = useIntelligenceStudy();
  const searchParams = useSearchParams();
  const nodeId = searchParams.get("node");
  const sourceLabel = searchParams.get("label") ?? undefined;

  const { data: report, isLoading, isError } = useQuery({
    queryKey: ["graph-impact", nodeId, token],
    queryFn: () => graphApi.getImpact(nodeId!, token!),
    enabled: Boolean(token && nodeId),
    staleTime: 30_000,
  });

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Link
                href={
                  studyId
                    ? `/intelligence/traceability?study=${studyId}`
                    : "/intelligence/traceability"
                }
                className="text-slate-400 hover:text-slate-700 text-sm transition-colors"
              >
                ← Traceability
              </Link>
            </div>
            <h1 className="font-display text-xl font-bold text-slate-900">
              Impact Analysis
            </h1>
            <p className="text-slate-500 text-sm mt-0.5">
              Downstream nodes at risk when a traceability gap is unresolved
            </p>
          </div>
          <StudyPicker />
        </div>
      </div>

      <div className="px-8 py-6">
        {!nodeId ? (
          <div className="bg-white border border-dashed border-slate-300 px-8 py-16 text-center">
            <p className="font-display font-semibold text-slate-700 mb-1">
              Select a gap node
            </p>
            <p className="text-slate-400 text-sm">
              Open the traceability matrix and choose a gap row to view downstream impact.
            </p>
            <Link
              href={
                studyId
                  ? `/intelligence/traceability?study=${studyId}`
                  : "/intelligence/traceability"
              }
              className="inline-block mt-4 text-sm text-brand-600 hover:text-brand-700 font-medium"
            >
              Go to traceability matrix
            </Link>
          </div>
        ) : isLoading ? (
          <ImpactAnalysisSkeleton />
        ) : isError || !report ? (
          <div className="bg-white border border-slate-200 px-8 py-14 text-center">
            <p className="font-display font-semibold text-slate-900 mb-1">
              Unable to load impact analysis
            </p>
            <p className="text-slate-500 text-sm">
              Confirm you have Reviewer or Admin access and the node still exists.
            </p>
          </div>
        ) : (
          <ImpactAnalysisViewer
            studyId={studyId ?? undefined}
            sourceNodeId={nodeId!}
            sourceLabel={sourceLabel}
            report={report}
          />
        )}
      </div>
    </div>
  );
}
