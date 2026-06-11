"use client";

import { useState } from "react";
import { Copy, Check } from "lucide-react";
import { deriveFileGrade } from "@/lib/submissionStatus";
import type { SubmissionManifestFile } from "@/types";

interface ManifestTableProps {
  files: SubmissionManifestFile[];
}

function truncateHash(hash: string): string {
  if (hash.length <= 16) return hash;
  return `${hash.slice(0, 8)}…${hash.slice(-8)}`;
}

export function ManifestTable({ files }: ManifestTableProps) {
  const [copiedPath, setCopiedPath] = useState<string | null>(null);

  async function copyHash(path: string, hash: string) {
    await navigator.clipboard.writeText(hash);
    setCopiedPath(path);
    window.setTimeout(() => setCopiedPath(null), 2000);
  }

  return (
    <div className="overflow-x-auto border border-slate-200">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3 font-medium">Path</th>
            <th className="px-4 py-3 font-medium">Size</th>
            <th className="px-4 py-3 font-medium">SHA-256</th>
            <th className="px-4 py-3 font-medium">Grade</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {files.map((file) => {
            const grade = deriveFileGrade(file);
            return (
              <tr key={file.path} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-mono text-xs text-slate-800">{file.path}</td>
                <td className="px-4 py-3 text-slate-600">
                  {file.size_bytes.toLocaleString()} B
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-slate-500" title={file.sha256}>
                      {truncateHash(file.sha256)}
                    </span>
                    <button
                      type="button"
                      onClick={() => copyHash(file.path, file.sha256)}
                      className="text-slate-400 hover:text-slate-700"
                      aria-label={`Copy checksum for ${file.path}`}
                    >
                      {copiedPath === file.path ? (
                        <Check className="h-3.5 w-3.5 text-emerald-600" />
                      ) : (
                        <Copy className="h-3.5 w-3.5" />
                      )}
                    </button>
                  </div>
                </td>
                <td className="px-4 py-3">
                  {grade === "placeholder" ? (
                    <span className="inline-flex items-center rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                      PLACEHOLDER — not regulatory-grade
                    </span>
                  ) : (
                    <span className="inline-flex items-center rounded bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800">
                      Generated
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
