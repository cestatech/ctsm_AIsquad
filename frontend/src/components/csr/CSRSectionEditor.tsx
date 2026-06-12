"use client";

import { useEffect, useRef } from "react";
import { isSectionProseComplete, type CSRSection } from "@/lib/api/csr";

interface CSRSectionEditorProps {
  sections: CSRSection[];
  activeSectionId: string | null;
  readOnly: boolean;
  onSectionProseChange: (sectionId: string, prose: string) => void;
  onSectionBlur: () => void;
  onRegenerate: (sectionId: string) => void;
  regeneratingSectionId: string | null;
}

export function CSRSectionEditor({
  sections,
  activeSectionId,
  readOnly,
  onSectionProseChange,
  onSectionBlur,
  onRegenerate,
  regeneratingSectionId,
}: CSRSectionEditorProps) {
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({});

  useEffect(() => {
    if (!activeSectionId) return;
    const node = sectionRefs.current[activeSectionId];
    node?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [activeSectionId]);

  if (sections.length === 0) {
    return (
      <div className="bg-white border border-slate-200 px-8 py-14 text-center">
        <p className="font-display font-semibold text-slate-900 mb-1">
          No sections to edit
        </p>
        <p className="text-slate-500 text-sm">
          Generate a CSR from a TLF package to populate ICH E3 sections.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {sections.map((section) => {
        const complete = isSectionProseComplete(section);
        const isRegenerating = regeneratingSectionId === section.number;
        return (
          <section
            key={section.number}
            id={`csr-section-${section.number}`}
            ref={(node) => {
              sectionRefs.current[section.number] = node;
            }}
            className={`bg-white border scroll-mt-24 ${
              section.number === activeSectionId
                ? "border-brand-300 ring-1 ring-brand-100"
                : "border-slate-200"
            }`}
          >
            <div className="px-5 py-4 border-b border-slate-100 flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-mono text-slate-400 mb-0.5">
                  Section {section.number}
                  {section.ich_e3_reference ? ` · ${section.ich_e3_reference}` : ""}
                </p>
                <h3 className="font-display font-semibold text-slate-900">
                  {section.title}
                </h3>
                {section.content_outline ? (
                  <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                    {section.content_outline}
                  </p>
                ) : null}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span
                  className={`text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 ${
                    complete
                      ? "bg-emerald-100 text-emerald-700"
                      : "bg-amber-100 text-amber-700"
                  }`}
                >
                  {complete ? "Prose complete" : "Shell"}
                </span>
                {!readOnly ? (
                  <button
                    type="button"
                    onClick={() => onRegenerate(section.number)}
                    disabled={isRegenerating}
                    className="text-xs font-medium px-3 py-1.5 border border-slate-200 text-slate-700 hover:border-brand-300 hover:text-brand-700 transition-colors disabled:opacity-50"
                  >
                    {isRegenerating ? "Regenerating…" : "Regenerate"}
                  </button>
                ) : null}
              </div>
            </div>
            <div className="p-5">
              {readOnly ? (
                <div className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap min-h-[8rem]">
                  {section.prose?.trim() || (
                    <span className="text-slate-400 italic">
                      No prose generated for this section yet.
                    </span>
                  )}
                </div>
              ) : (
                <textarea
                  value={section.prose ?? ""}
                  onChange={(event) =>
                    onSectionProseChange(section.number, event.target.value)
                  }
                  onBlur={onSectionBlur}
                  placeholder="Section prose will appear here after generation or manual entry…"
                  rows={12}
                  className="w-full text-sm text-slate-800 leading-relaxed border border-slate-200 px-3 py-2 focus:outline-none focus:ring-1 focus:ring-brand-400 focus:border-brand-400 resize-y min-h-[12rem]"
                />
              )}
            </div>
          </section>
        );
      })}
    </div>
  );
}

export function CSRSectionEditorSkeleton() {
  return (
    <div className="space-y-4">
      {Array.from({ length: 3 }).map((_, index) => (
        <div
          key={index}
          className="bg-white border border-slate-200 p-5 space-y-3"
        >
          <div className="h-4 w-48 bg-slate-100 animate-pulse rounded-sm" />
          <div className="h-32 bg-slate-50 animate-pulse rounded-sm" />
        </div>
      ))}
    </div>
  );
}
