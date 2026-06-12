"use client";

import { isSectionProseComplete, type CSRSection } from "@/lib/api/csr";

interface CSROutlineNavigatorProps {
  sections: CSRSection[];
  activeSectionId: string | null;
  onSelect: (sectionId: string) => void;
}

export function CSROutlineNavigator({
  sections,
  activeSectionId,
  onSelect,
}: CSROutlineNavigatorProps) {
  if (sections.length === 0) {
    return (
      <div className="bg-white border border-slate-200 p-4">
        <p className="text-sm text-slate-500">No ICH E3 sections in this CSR.</p>
      </div>
    );
  }

  return (
    <nav
      className="bg-white border border-slate-200"
      aria-label="ICH E3 section outline"
    >
      <div className="px-4 py-3 border-b border-slate-100">
        <h2 className="font-display font-semibold text-slate-900 text-sm">
          ICH E3 Outline
        </h2>
        <p className="text-xs text-slate-500 mt-0.5">
          {sections.length} sections
        </p>
      </div>
      <ul className="divide-y divide-slate-100 max-h-[calc(100vh-16rem)] overflow-y-auto">
        {sections.map((section) => {
          const complete = isSectionProseComplete(section);
          const isActive = section.number === activeSectionId;
          return (
            <li key={section.number}>
              <button
                type="button"
                onClick={() => onSelect(section.number)}
                className={`w-full text-left px-4 py-3 transition-colors ${
                  isActive
                    ? "bg-brand-50 border-l-2 border-brand-500"
                    : "hover:bg-slate-50 border-l-2 border-transparent"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-xs font-mono text-slate-400">
                      §{section.number}
                    </p>
                    <p className="text-sm font-medium text-slate-900 truncate">
                      {section.title}
                    </p>
                  </div>
                  <span
                    className={`shrink-0 text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 ${
                      complete
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-amber-100 text-amber-700"
                    }`}
                  >
                    {complete ? "Prose" : "Shell"}
                  </span>
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export function CSROutlineNavigatorSkeleton() {
  return (
    <div className="bg-white border border-slate-200 p-4 space-y-3">
      <div className="h-4 w-32 bg-slate-100 animate-pulse rounded-sm" />
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="h-12 bg-slate-50 animate-pulse rounded-sm" />
      ))}
    </div>
  );
}
