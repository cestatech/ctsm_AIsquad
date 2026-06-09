"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { statisticalQcApi, type StatisticalQCRun } from "@/lib/api/statisticalQc";
import { downloadTextFile } from "@/lib/download";

const STATUS_COLORS: Record<string, string> = {
  MATCH: "bg-emerald-100 text-emerald-800",
  MISMATCH: "bg-red-100 text-red-800",
  EXECUTION_FAILED: "bg-amber-100 text-amber-800",
  PREFLIGHT_FAILED: "bg-amber-100 text-amber-900",
  R_UNAVAILABLE: "bg-slate-100 text-slate-600",
  PROGRAMS_GENERATED: "bg-blue-100 text-blue-800",
  PENDING: "bg-slate-100 text-slate-500",
};

interface StatisticalQCPanelProps {
  outputArtifactId: string;
  token: string;
}

export function StatisticalQCPanel({
  outputArtifactId,
  token,
}: StatisticalQCPanelProps) {
  const [expandedRun, setExpandedRun] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["statistical-qc", outputArtifactId, token],
    queryFn: () =>
      statisticalQcApi.listRuns(
        { output_artifact_id: outputArtifactId, page_size: 5 },
        token
      ),
    enabled: !!token && !!outputArtifactId,
  });

  if (isLoading) {
    return (
      <p className="text-xs text-slate-400 py-2">Loading dual-programmer QC…</p>
    );
  }

  const runs = data?.items ?? [];
  if (runs.length === 0) {
    return (
      <p className="text-xs text-slate-400 py-2">
        No dual-programmer R QC run recorded for this artifact.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="text-xs font-semibold text-slate-700 uppercase tracking-wide">
        Dual-Programmer R QC
      </h3>
      {runs.map((run) => (
        <QCRunCard
          key={run.id}
          run={run}
          token={token}
          expanded={expandedRun === run.id}
          onToggle={() =>
            setExpandedRun((id) => (id === run.id ? null : run.id))
          }
        />
      ))}
    </div>
  );
}

function QCRunCard({
  run,
  token,
  expanded,
  onToggle,
}: {
  run: StatisticalQCRun;
  token: string;
  expanded: boolean;
  onToggle: () => void;
}) {
  const statusClass = STATUS_COLORS[run.status] ?? STATUS_COLORS.PENDING;
  const comparison = run.comparison_result;
  const workflowSlug = run.workflow_step.toLowerCase();

  async function downloadPrimary() {
    try {
      await statisticalQcApi.downloadPrimaryProgram(run.id, workflowSlug, token);
    } catch {
      downloadTextFile(`primary_${workflowSlug}.R`, run.primary_r_program);
    }
  }

  async function downloadQc() {
    try {
      await statisticalQcApi.downloadQcProgram(run.id, workflowSlug, token);
    } catch {
      downloadTextFile(`qc_${workflowSlug}.R`, run.qc_r_program);
    }
  }

  return (
    <div className="border border-slate-200 rounded-sm overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        className="w-full px-3 py-2 flex items-center justify-between text-left hover:bg-slate-50"
      >
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-slate-600">
            {run.workflow_step.replace(/_/g, " → ")}
          </span>
          <span className={`text-[10px] px-1.5 py-0.5 font-semibold ${statusClass}`}>
            {run.status}
          </span>
        </div>
        <span className="text-[10px] text-slate-400">
          {new Date(run.created_at).toLocaleString()}
        </span>
      </button>
      {expanded && (
        <div className="px-3 py-2 border-t border-slate-100 bg-slate-50 space-y-2 text-[11px]">
          {comparison && (
            <div className="text-slate-600 space-y-1">
              <p>
                {comparison.r_available === false
                  ? "R not available — programs stored for manual execution and comparison."
                  : run.status === "EXECUTION_FAILED"
                  ? "R execution failed — programs are saved below for manual review. This usually means the generated script could not read input files in the isolated QC workspace."
                  : typeof comparison.message === "string"
                  ? comparison.message
                  : `Comparison: ${String(comparison.status ?? "unknown")}`}
                {comparison.execution_mode === "deterministic_template_fallback" && (
                  <> Reference templates were used after AI execution failed.</>
                )}
                {comparison.execution_mode === "ai_mismatch_template_verified" && (
                  <> AI programs differed; reference templates matched.</>
                )}
                {typeof comparison.file_count === "number" && (
                  <> · {comparison.file_count} output file(s)</>
                )}
              </p>
              {(run.status === "EXECUTION_FAILED" || comparison.status === "PREFLIGHT_FAILED") && (
                <details className="text-[10px]" open>
                  <summary className="cursor-pointer text-amber-700 font-medium">
                    {comparison.status === "PREFLIGHT_FAILED"
                      ? "Preflight validation errors"
                      : "Show R error output"}
                  </summary>
                  {comparison.preflight != null &&
                    Array.isArray((comparison.preflight as { errors?: string[] }).errors) && (
                      <ul className="mt-1 list-disc list-inside text-amber-800">
                        {((comparison.preflight as { errors: string[] }).errors).map((err) => (
                          <li key={err}>{err}</li>
                        ))}
                      </ul>
                    )}
                  {typeof comparison.primary_error_context === "object" &&
                    comparison.primary_error_context !== null && (
                      <pre className="mt-1 p-2 bg-white border border-slate-200 overflow-x-auto font-mono max-h-24">
                        {String(
                          (comparison.primary_error_context as { error_line?: string })
                            .error_line ?? ""
                        )}
                      </pre>
                    )}
                  {typeof comparison.primary_log === "string" && comparison.primary_log && (
                    <pre className="mt-1 p-2 bg-white border border-slate-200 overflow-x-auto font-mono max-h-24">
                      {comparison.primary_log}
                    </pre>
                  )}
                </details>
              )}
              {run.status === "MISMATCH" && comparison.mismatch_report != null ? (
                <details className="text-[10px]" open>
                  <summary className="cursor-pointer text-red-700 font-medium">
                    Mismatch report
                  </summary>
                  <pre className="mt-1 p-2 bg-white border border-red-100 overflow-x-auto font-mono max-h-40 text-[10px]">
                    {JSON.stringify(comparison.mismatch_report, null, 2)}
                  </pre>
                </details>
              ) : null}
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={downloadPrimary}
              className="text-[10px] bg-brand-600 hover:bg-brand-500 text-white font-semibold px-2.5 py-1 transition-colors"
            >
              Download primary.R
            </button>
            <button
              type="button"
              onClick={downloadQc}
              className="text-[10px] bg-violet-600 hover:bg-violet-500 text-white font-semibold px-2.5 py-1 transition-colors"
            >
              Download qc.R
            </button>
          </div>
          <details>
            <summary className="cursor-pointer text-brand-600 font-medium">
              Primary R program
            </summary>
            <pre className="mt-1 p-2 bg-white border border-slate-200 overflow-x-auto text-[10px] font-mono max-h-40">
              {run.primary_r_program}
            </pre>
          </details>
          <details>
            <summary className="cursor-pointer text-violet-600 font-medium">
              QC R program (independent)
            </summary>
            <pre className="mt-1 p-2 bg-white border border-slate-200 overflow-x-auto text-[10px] font-mono max-h-40">
              {run.qc_r_program}
            </pre>
          </details>
        </div>
      )}
    </div>
  );
}
