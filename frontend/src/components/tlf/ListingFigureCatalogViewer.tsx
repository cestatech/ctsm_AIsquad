"use client";

import Link from "next/link";
import type { ListingFigureCatalog, ListingFigureEntry } from "@/lib/api/tlf";

interface ListingFigureCatalogViewerProps {
  studyId: string;
  artifactId: string;
  catalog: ListingFigureCatalog;
}

const TYPE_STYLES: Record<ListingFigureEntry["output_type"], string> = {
  table: "bg-blue-50 text-blue-700",
  listing: "bg-purple-50 text-purple-700",
  figure: "bg-teal-50 text-teal-700",
};

const STATUS_STYLES: Record<string, string> = {
  programmed: "bg-emerald-100 text-emerald-700",
  specified: "bg-amber-100 text-amber-700",
  pending: "bg-slate-100 text-slate-600",
};

export function ListingFigureCatalogViewer({
  studyId,
  artifactId,
  catalog,
}: ListingFigureCatalogViewerProps) {
  if (catalog.entries.length === 0) {
    return (
      <div className="bg-white border border-slate-200 px-8 py-14 text-center">
        <p className="font-display font-semibold text-slate-900 mb-1">
          No SAP traceability catalog
        </p>
        <p className="text-slate-500 text-sm">
          This TLF artifact has no linked SAP traceability edges yet. Once SAP → TLF
          links exist in the context graph, programmed outputs will appear here.
        </p>
        <Link
          href={`/studies/${studyId}/artifacts/${artifactId}`}
          className="inline-block mt-4 text-sm text-brand-600 hover:text-brand-700 font-medium"
        >
          Open TLF artifact detail
        </Link>
      </div>
    );
  }

  return (
    <div className="bg-white border border-slate-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
        <div>
          <h2 className="font-display font-semibold text-slate-900 text-sm">
            Listing &amp; Figure Catalog
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {catalog.entries.length} outputs mapped from SAP traceability
            {catalog.sap_artifact_id ? (
              <>
                {" "}
                (<span className="font-mono">{catalog.sap_artifact_id.slice(0, 8)}…</span>)
              </>
            ) : null}
          </p>
        </div>
        <Link
          href={`/studies/${studyId}/artifacts/${artifactId}`}
          className="text-xs text-brand-600 hover:text-brand-700 font-medium"
        >
          TLF artifact detail →
        </Link>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50">
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                SAP Section
              </th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Output Title
              </th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Type
              </th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Status
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {catalog.entries.map((entry) => (
              <tr key={`${entry.tlf_index}-${entry.output_title}`} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-mono text-xs text-slate-700">
                  {entry.sap_section}
                </td>
                <td className="px-4 py-3">
                  <Link
                    href={`/studies/${studyId}/artifacts/${artifactId}`}
                    className="text-slate-900 hover:text-brand-700 font-medium"
                  >
                    {entry.output_title}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`text-[11px] px-2 py-0.5 font-medium capitalize ${
                      TYPE_STYLES[entry.output_type]
                    }`}
                  >
                    {entry.output_type}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`text-[11px] px-2 py-0.5 font-medium capitalize ${
                      STATUS_STYLES[entry.status] ?? "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {entry.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function ListingFigureCatalogSkeleton() {
  return (
    <div className="bg-white border border-slate-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-100">
        <div className="h-4 w-56 bg-slate-100 animate-pulse rounded-sm mb-2" />
        <div className="h-3 w-72 bg-slate-50 animate-pulse rounded-sm" />
      </div>
      <div className="p-4 space-y-3">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="h-8 bg-slate-50 animate-pulse rounded-sm" />
        ))}
      </div>
    </div>
  );
}
