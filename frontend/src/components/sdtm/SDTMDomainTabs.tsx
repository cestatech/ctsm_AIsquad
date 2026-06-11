"use client";

import type { SDTMDomain } from "@/lib/api/sdtm";

interface SDTMDomainTabsProps {
  domains: SDTMDomain[];
  activeDomain: string;
  onSelect: (domainCode: string) => void;
}

export function SDTMDomainTabs({
  domains,
  activeDomain,
  onSelect,
}: SDTMDomainTabsProps) {
  if (domains.length === 0) {
    return (
      <div className="border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
        No SDTM domains found in this artifact.
      </div>
    );
  }

  return (
    <div className="border border-slate-200 bg-white overflow-x-auto">
      <div className="flex min-w-max">
        {domains.map((domain) => {
          const code = domain.domain;
          const isActive = code === activeDomain;
          return (
            <button
              key={code}
              type="button"
              onClick={() => onSelect(code)}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                isActive
                  ? "border-brand-600 text-brand-700 bg-brand-50/40"
                  : "border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-50"
              }`}
            >
              <span className="font-mono">{code}</span>
              {domain.domain_label ? (
                <span className="ml-2 text-xs font-normal text-slate-500">
                  {domain.domain_label}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function SDTMDomainTabsSkeleton() {
  return (
    <div className="border border-slate-200 bg-white px-4 py-3 flex gap-3">
      {["DM", "AE", "LB"].map((label) => (
        <div
          key={label}
          className="h-8 w-24 bg-slate-100 animate-pulse rounded-sm"
        />
      ))}
    </div>
  );
}
