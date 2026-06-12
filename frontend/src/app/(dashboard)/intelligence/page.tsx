"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { useIntelligencePermissions } from "@/hooks/useIntelligencePermissions";
import { useIntelligenceStudy } from "@/hooks/useIntelligenceStudy";
import { intelligenceApi } from "@/lib/api/intelligence";

const INTELLIGENCE_SCREENS = [
  {
    href: "/intelligence/graph",
    title: "Context Graph",
    description: "Browse the intelligence graph — nodes, edges, and relationships across the full clinical pipeline.",
    badge: null,
    alwaysShow: true,
  },
  {
    href: "/intelligence/traceability",
    title: "Traceability Matrix",
    description: "End-to-end chain: Objective → Endpoint → eCRF → SDTM → ADaM → TLF → CSR with link status.",
    badge: null,
    alwaysShow: true,
  },
  {
    href: "/intelligence/impact",
    title: "Impact Analysis",
    description: "Downstream nodes at risk when a traceability gap is left unresolved.",
    badge: null,
    alwaysShow: true,
  },
  {
    href: "/intelligence/decisions",
    title: "AI Decisions",
    description: "Audit and review every AI-generated decision with full provenance: agent, model, reasoning, confidence.",
    badge: "pending",
    alwaysShow: true,
  },
  {
    href: "/intelligence/overrides",
    title: "Human Overrides",
    description: "Immutable log of every human correction to an AI-generated value, with mandatory justification.",
    badge: null,
    alwaysShow: true,
  },
  {
    href: "/intelligence/lineage",
    title: "Lineage Explorer",
    description: "Trace the upstream sources and downstream derivations for any field-level or artifact-level entity.",
    badge: null,
    alwaysShow: true,
  },
  {
    href: "/intelligence/validation",
    title: "Validation Evidence",
    description: "CDISC conformance findings per rule. Filter by severity, waive findings with mandatory justification.",
    badge: "issues",
    permission: "canRunValidation" as const,
    alwaysShow: false,
  },
  {
    href: "/intelligence/synthetic",
    title: "Synthetic Data",
    description: "Reproducible synthetic patient data in raw eCRF format. Every distributional assumption documented with source citation.",
    badge: null,
    alwaysShow: true,
  },
  {
    href: "/generated-data",
    title: "Generated Data",
    description: "Download synthesized SDTM, ADaM, TLF, and CSR pipeline outputs for the active study.",
    badge: null,
    alwaysShow: true,
    studyScoped: true,
  },
];

export default function IntelligencePage() {
  const { token } = useAuthStore();
  const perms = useIntelligencePermissions();
  const { studyId } = useIntelligenceStudy();

  const { data: pendingDecisions = [] } = useQuery({
    queryKey: ["pending-decisions", token],
    queryFn: () => intelligenceApi.listPendingDecisions(token!),
    enabled: !!token,
    staleTime: 30_000,
  });

  const { data: validationData } = useQuery({
    queryKey: ["validation-evidence-hub", studyId, token],
    queryFn: () =>
      intelligenceApi.listValidationEvidence(
        { study_id: studyId!, evidence_status: "FAIL", page_size: 1 },
        token!
      ),
    enabled: !!token && !!studyId,
    staleTime: 30_000,
  });

  const badgeCounts: Record<string, number> = {
    pending: pendingDecisions.length,
    issues: validationData?.total ?? 0,
  };

  const visibleScreens = INTELLIGENCE_SCREENS.filter((s) => {
    if (s.alwaysShow) return true;
    if (s.permission) return perms[s.permission];
    return false;
  });

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <h1 className="font-display text-xl font-bold text-slate-900">TrialGenesis Intelligence Platform</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Every AI action is explainable, auditable, and traceable. Human oversight at every step.
        </p>
      </div>

      <div className="px-8 py-6">
        <div className="grid grid-cols-2 gap-4">
          {visibleScreens.map((screen) => {
            const count = screen.badge ? badgeCounts[screen.badge] : 0;
            const isStudyScoped =
              "studyScoped" in screen && screen.studyScoped === true;
            const needsStudy = isStudyScoped && !studyId;
            const href = isStudyScoped && studyId
              ? `/studies/${studyId}/generated-data`
              : screen.href;
            const cardClass =
              "bg-white border border-slate-200 px-5 py-4 transition-all " +
              (needsStudy
                ? "opacity-60 cursor-not-allowed"
                : "hover:border-brand-400 hover:shadow-sm group");

            const inner = (
              <>
                <div className="flex items-start justify-between gap-3 mb-2">
                  <h2
                    className={
                      "font-display font-semibold text-slate-900 " +
                      (needsStudy ? "" : "group-hover:text-brand-700 transition-colors")
                    }
                  >
                    {screen.title}
                  </h2>
                  {screen.badge && count > 0 && (
                    <span className="shrink-0 text-xs px-2 py-0.5 bg-amber-100 text-amber-800 font-semibold">
                      {count} pending
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500 leading-relaxed">
                  {needsStudy
                    ? "Select a study using the picker above to access generated pipeline outputs."
                    : screen.description}
                </p>
              </>
            );

            if (needsStudy) {
              return (
                <div key={screen.href} className={cardClass} aria-disabled="true">
                  {inner}
                </div>
              );
            }

            return (
              <Link key={screen.href} href={href} className={cardClass}>
                {inner}
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}
