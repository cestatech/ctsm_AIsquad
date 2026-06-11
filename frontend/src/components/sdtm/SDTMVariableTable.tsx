"use client";

import {
  buildDerivationIndex,
  normalizeSdtmVariable,
  type SDTMDomain,
  type SDTMArtifactContent,
} from "@/lib/api/sdtm";

interface SDTMVariableTableProps {
  domain: SDTMDomain | undefined;
  content: SDTMArtifactContent;
}

const ORIGIN_STYLES: Record<string, string> = {
  Collected: "bg-blue-50 text-blue-700",
  Derived: "bg-purple-50 text-purple-700",
  Assigned: "bg-slate-100 text-slate-700",
  Protocol: "bg-amber-50 text-amber-700",
  Predecessor: "bg-teal-50 text-teal-700",
};

export function SDTMVariableTable({ domain, content }: SDTMVariableTableProps) {
  if (!domain) {
    return (
      <div className="border border-slate-200 bg-white px-5 py-10 text-center text-sm text-slate-500">
        Select a domain tab to inspect variables.
      </div>
    );
  }

  const derivationIndex = buildDerivationIndex(content);
  const variables = domain.variables.map((spec) =>
    normalizeSdtmVariable(spec, domain.domain, derivationIndex)
  );

  if (variables.length === 0) {
    return (
      <div className="border border-slate-200 bg-white px-5 py-10 text-center text-sm text-slate-500">
        No variables documented for {domain.domain}.
      </div>
    );
  }

  return (
    <div className="border border-slate-200 bg-white overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
        <div>
          <h2 className="font-display font-semibold text-slate-900 text-sm">
            {domain.domain} — {domain.domain_label ?? "Domain Variables"}
          </h2>
          {domain.class ? (
            <p className="text-xs text-slate-500 mt-0.5">Class: {domain.class}</p>
          ) : null}
        </div>
        <span className="text-xs text-slate-400">{variables.length} variables</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50">
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Variable
              </th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Label
              </th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Data Type
              </th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Origin
              </th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Derivation
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {variables.map((variable) => (
              <tr key={variable.name} className="hover:bg-slate-50 transition-colors">
                <td className="px-4 py-3 font-mono text-xs text-slate-900">
                  {variable.name}
                </td>
                <td className="px-4 py-3 text-slate-700">{variable.label}</td>
                <td className="px-4 py-3 text-xs text-slate-600">{variable.dataType}</td>
                <td className="px-4 py-3">
                  <span
                    className={`text-[11px] px-2 py-0.5 font-medium ${
                      ORIGIN_STYLES[variable.origin] ?? "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {variable.origin}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-slate-600 max-w-md">
                  {variable.derivation ? (
                    <span className="leading-relaxed">{variable.derivation}</span>
                  ) : (
                    <span className="text-slate-300 italic">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function SDTMVariableTableSkeleton() {
  return (
    <div className="border border-slate-200 bg-white overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-100">
        <div className="h-4 w-48 bg-slate-100 animate-pulse rounded-sm" />
      </div>
      <div className="p-4 space-y-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <div key={index} className="h-8 bg-slate-50 animate-pulse rounded-sm" />
        ))}
      </div>
    </div>
  );
}
