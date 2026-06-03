"use client";

import Link from "next/link";
import { useAuthStore } from "@/store/authStore";
import { usePermissions } from "@/hooks/usePermissions";
import { MOCK_AI_DECISIONS, MOCK_VALIDATION_EVIDENCE } from "@/lib/mockData";

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
    description: "Reproducible synthetic patient data runs. Every distributional assumption documented with source citation.",
    badge: null,
    alwaysShow: true,
  },
];

export default function IntelligencePage() {
  const { role } = useAuthStore();
  const perms = usePermissions(role);

  const pendingDecisions = MOCK_AI_DECISIONS.filter((d) => d.status === "PENDING_REVIEW").length;
  const failingEvidence = MOCK_VALIDATION_EVIDENCE.filter((e) => e.status === "FAIL").length;

  const badgeCounts: Record<string, number> = {
    pending: pendingDecisions,
    issues: failingEvidence,
  };

  const visibleScreens = INTELLIGENCE_SCREENS.filter((s) => {
    if (s.alwaysShow) return true;
    if (s.permission) return perms[s.permission];
    return false;
  });

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <h1 className="font-display text-xl font-bold text-slate-900">Celerius Intelligence Platform</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Every AI action is explainable, auditable, and traceable. Human oversight at every step.
        </p>
      </div>

      <div className="px-8 py-6">
        <div className="grid grid-cols-2 gap-4">
          {visibleScreens.map((screen) => {
            const count = screen.badge ? badgeCounts[screen.badge] : 0;
            return (
              <Link
                key={screen.href}
                href={screen.href}
                className="bg-white border border-slate-200 px-5 py-4 hover:border-brand-400 hover:shadow-sm transition-all group"
              >
                <div className="flex items-start justify-between gap-3 mb-2">
                  <h2 className="font-display font-semibold text-slate-900 group-hover:text-brand-700 transition-colors">
                    {screen.title}
                  </h2>
                  {screen.badge && count > 0 && (
                    <span className="shrink-0 text-xs px-2 py-0.5 bg-amber-100 text-amber-800 font-semibold">
                      {count} pending
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500 leading-relaxed">{screen.description}</p>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}
