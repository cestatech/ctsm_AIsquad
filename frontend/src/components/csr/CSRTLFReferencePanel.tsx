"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { tlfApi } from "@/lib/api/tlf";
import type {
  CSRArtifactContent,
  CSRSection,
  CSRSectionTLFReference,
  CSRTLFIntegrationEntry,
} from "@/lib/api/csr";

interface CSRTLFReferencePanelProps {
  studyId: string;
  content: CSRArtifactContent | undefined;
  activeSection: CSRSection | null;
}

function integrationForSection(
  integrations: CSRTLFIntegrationEntry[] | undefined,
  sectionId: string
): CSRTLFIntegrationEntry[] {
  if (!integrations) return [];
  return integrations.filter(
    (entry) => String(entry.csr_section) === String(sectionId)
  );
}

export function CSRTLFReferencePanel({
  studyId,
  content,
  activeSection,
}: CSRTLFReferencePanelProps) {
  const { token } = useAuthStore();
  const sectionId = activeSection?.number ?? null;
  const sourceTlfId = content?.source_tlf_artifact_ids?.[0];

  const { data: catalog, isLoading: catalogLoading } = useQuery({
    queryKey: ["tlf-catalog", studyId, sourceTlfId, token],
    queryFn: () => tlfApi.getCatalog(sourceTlfId!, token!),
    enabled: Boolean(token && sourceTlfId),
    staleTime: 60_000,
  });

  const sectionRefs = activeSection?.tlf_references ?? [];
  const integrations = integrationForSection(content?.tlf_integration, sectionId ?? "");

  if (!activeSection) {
    return (
      <div className="bg-white border border-slate-200 p-4">
        <p className="text-sm text-slate-500">
          Select a section to view linked TLF references.
        </p>
      </div>
    );
  }

  return (
    <aside className="bg-white border border-slate-200">
      <div className="px-4 py-3 border-b border-slate-100">
        <h2 className="font-display font-semibold text-slate-900 text-sm">
          TLF References
        </h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Section {activeSection.number}: {activeSection.title}
        </p>
      </div>

      <div className="p-4 space-y-5 max-h-[calc(100vh-16rem)] overflow-y-auto">
        {sectionRefs.length > 0 ? (
          <ReferenceGroup title="Embedded in section" references={sectionRefs} />
        ) : null}

        {integrations.length > 0 ? (
          <div>
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
              Integration map
            </h3>
            <ul className="space-y-2">
              {integrations.map((entry) => (
                <li
                  key={`${entry.table_id}-${entry.insertion_note}`}
                  className="border border-slate-100 bg-slate-50 px-3 py-2 text-sm"
                >
                  <p className="font-mono text-xs text-brand-700">
                    {entry.table_id ?? "—"}
                  </p>
                  {entry.insertion_note ? (
                    <p className="text-xs text-slate-600 mt-1">
                      {entry.insertion_note}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {sectionRefs.length === 0 && integrations.length === 0 ? (
          <p className="text-sm text-slate-500">
            No TLF tables are mapped to this section in the CSR content.
          </p>
        ) : null}

        {sourceTlfId ? (
          <div className="border-t border-slate-100 pt-4">
            <div className="flex items-center justify-between gap-2 mb-2">
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Source TLF catalog
              </h3>
              <Link
                href={`/studies/${studyId}/tlf/${sourceTlfId}/catalog`}
                className="text-xs text-brand-600 hover:text-brand-700 font-medium"
              >
                Full catalog →
              </Link>
            </div>
            {catalogLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, index) => (
                  <div
                    key={index}
                    className="h-10 bg-slate-50 animate-pulse rounded-sm"
                  />
                ))}
              </div>
            ) : catalog && catalog.entries.length > 0 ? (
              <ul className="space-y-2">
                {catalog.entries.slice(0, 8).map((entry) => (
                  <li
                    key={`${entry.sap_section}-${entry.tlf_index}`}
                    className="text-xs border border-slate-100 px-2 py-1.5"
                  >
                    <span className="font-mono text-slate-500">
                      #{entry.tlf_index}
                    </span>{" "}
                    <span className="text-slate-800">{entry.output_title}</span>
                    <span className="ml-1 text-slate-400">({entry.output_type})</span>
                  </li>
                ))}
                {catalog.entries.length > 8 ? (
                  <p className="text-xs text-slate-400">
                    +{catalog.entries.length - 8} more in full catalog
                  </p>
                ) : null}
              </ul>
            ) : (
              <p className="text-xs text-slate-500">
                No SAP traceability catalog entries for the source TLF artifact.
              </p>
            )}
          </div>
        ) : null}
      </div>
    </aside>
  );
}

function ReferenceGroup({
  title,
  references,
}: {
  title: string;
  references: CSRSectionTLFReference[];
}) {
  return (
    <div>
      <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
        {title}
      </h3>
      <ul className="space-y-2">
        {references.map((ref) => (
          <li
            key={ref.table_id ?? ref.title}
            className="border border-slate-100 bg-slate-50 px-3 py-2"
          >
            <p className="font-mono text-xs text-brand-700">
              {ref.table_id ?? "Table"}
            </p>
            {ref.title ? (
              <p className="text-sm text-slate-800 mt-0.5">{ref.title}</p>
            ) : null}
            {ref.population ? (
              <p className="text-xs text-slate-500 mt-1">
                Population: {ref.population}
              </p>
            ) : null}
            {ref.key_result ? (
              <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                {ref.key_result}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function CSRTLFReferencePanelSkeleton() {
  return (
    <div className="bg-white border border-slate-200 p-4 space-y-3">
      <div className="h-4 w-36 bg-slate-100 animate-pulse rounded-sm" />
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="h-14 bg-slate-50 animate-pulse rounded-sm" />
      ))}
    </div>
  );
}
