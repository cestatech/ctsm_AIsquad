"use client";

import { useMemo, useState } from "react";
import { isOpenValidationFinding } from "@/lib/api/sdtm";
import type { ValidationEvidence } from "@/types";

interface SDTMValidationPanelProps {
  evidence: ValidationEvidence[];
  activeDomain?: string;
}

const STATUS_STYLES: Record<string, string> = {
  FAIL: "bg-red-100 text-red-700",
  WARNING: "bg-amber-100 text-amber-700",
  PENDING: "bg-slate-100 text-slate-600",
  PASS: "bg-emerald-100 text-emerald-700",
  WAIVED: "bg-purple-100 text-purple-700",
};

const SEVERITY_STYLES: Record<string, string> = {
  ERROR: "text-red-600 font-semibold",
  WARNING: "text-amber-600",
  INFO: "text-slate-500",
};

function matchesDomain(
  item: ValidationEvidence,
  domainCode: string | undefined
): boolean {
  if (!domainCode) return true;
  const field = item.subject_field ?? "";
  if (field.startsWith(`${domainCode}.`)) return true;
  if (field.toUpperCase() === domainCode.toUpperCase()) return true;
  const detailsDomain = item.finding_details?.domain;
  return typeof detailsDomain === "string" && detailsDomain.toUpperCase() === domainCode.toUpperCase();
}

export function SDTMValidationPanel({
  evidence,
  activeDomain,
}: SDTMValidationPanelProps) {
  const [expanded, setExpanded] = useState(false);

  const scopedEvidence = useMemo(
    () => evidence.filter((item) => matchesDomain(item, activeDomain)),
    [evidence, activeDomain]
  );

  const openFindings = scopedEvidence.filter(isOpenValidationFinding);
  const openCount = openFindings.length;

  return (
    <div className="border border-slate-200 bg-white">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="w-full px-5 py-4 flex items-center justify-between text-left hover:bg-slate-50 transition-colors"
      >
        <div>
          <h2 className="font-display font-semibold text-slate-900 text-sm">
            CDISC Validation Findings
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {activeDomain
              ? `Findings scoped to ${activeDomain} where available`
              : "Internal CDISC validation evidence for this artifact"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`text-xs px-2.5 py-1 font-semibold ${
              openCount > 0
                ? "bg-red-100 text-red-700"
                : "bg-emerald-100 text-emerald-700"
            }`}
          >
            {openCount} open
          </span>
          <span className="text-xs text-slate-400">{expanded ? "Hide" : "Show"}</span>
        </div>
      </button>

      {expanded ? (
        <div className="border-t border-slate-100">
          {scopedEvidence.length === 0 ? (
            <div className="px-5 py-8 text-center text-sm text-slate-500">
              No validation findings recorded for this artifact yet.
            </div>
          ) : (
            <div className="divide-y divide-slate-100 max-h-96 overflow-y-auto">
              {scopedEvidence.map((item) => (
                <div key={item.id} className="px-5 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <code className="text-[11px] font-mono text-slate-700 bg-slate-100 px-1.5 py-0.5">
                          {item.rule_id ?? "RULE"}
                        </code>
                        <span
                          className={`text-[10px] px-1.5 py-0.5 font-semibold ${
                            STATUS_STYLES[item.status] ?? "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {item.status}
                        </span>
                        {item.finding_severity ? (
                          <span
                            className={`text-[11px] ${
                              SEVERITY_STYLES[item.finding_severity] ??
                              "text-slate-500"
                            }`}
                          >
                            {item.finding_severity}
                          </span>
                        ) : null}
                      </div>
                      <p className="text-sm font-medium text-slate-900">
                        {item.rule_name ?? "Validation rule"}
                      </p>
                      <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                        {item.finding_message ?? "No message provided."}
                      </p>
                      {item.subject_field ? (
                        <p className="text-[11px] text-slate-400 mt-1 font-mono">
                          Field: {item.subject_field}
                        </p>
                      ) : null}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

export function SDTMValidationPanelSkeleton() {
  return (
    <div className="border border-slate-200 bg-white px-5 py-4">
      <div className="h-4 w-56 bg-slate-100 animate-pulse rounded-sm mb-2" />
      <div className="h-3 w-40 bg-slate-50 animate-pulse rounded-sm" />
    </div>
  );
}
