"use client";

import { useState } from "react";
import { AlertTriangle, Download, FileText, Loader2 } from "lucide-react";
import { ManifestTable } from "@/components/submission/ManifestTable";
import { submissionsApi } from "@/lib/api/submissions";
import { derivePackageDisplayState } from "@/lib/submissionStatus";
import type { SubmissionManifest, SubmissionPackage } from "@/types";

interface PackagePanelPermissions {
  canViewSubmissionManifest: boolean;
  canDownloadSubmissionPackage: boolean;
  canCreateSubmissionPackage: boolean;
}

interface PackagePanelProps {
  studyId: string;
  token: string;
  package: SubmissionPackage;
  permissions: PackagePanelPermissions;
  onRecreate?: () => void;
  isRecreating?: boolean;
}

const STATUS_STYLES: Record<string, string> = {
  DRAFT: "bg-slate-100 text-slate-700",
  PACKAGING: "bg-blue-100 text-blue-700",
  READY: "bg-emerald-100 text-emerald-700",
  SUBMITTED: "bg-indigo-100 text-indigo-700",
};

export function PackagePanel({
  studyId,
  token,
  package: pkg,
  permissions,
  onRecreate,
  isRecreating = false,
}: PackagePanelProps) {
  const [manifest, setManifest] = useState<SubmissionManifest | null>(null);
  const [manifestError, setManifestError] = useState<string | null>(null);
  const [manifestLoading, setManifestLoading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  const displayState = derivePackageDisplayState(pkg);
  const showSyntheticBanner =
    manifest?.data_classification === "SYNTHETIC_DEMO" ||
    manifest?.manifest?.data_classification === "SYNTHETIC_DEMO";

  async function loadManifest() {
    if (!permissions.canViewSubmissionManifest) return;
    setManifestLoading(true);
    setManifestError(null);
    try {
      const data = await submissionsApi.getManifest(pkg.id, token);
      setManifest(data);
    } catch (err) {
      setManifestError(err instanceof Error ? err.message : "Failed to load manifest.");
    } finally {
      setManifestLoading(false);
    }
  }

  async function handleDownload() {
    if (!permissions.canDownloadSubmissionPackage) return;
    setDownloading(true);
    setDownloadError(null);
    try {
      await submissionsApi.triggerZipDownload(pkg.id, token);
    } catch (err) {
      setDownloadError(err instanceof Error ? err.message : "Download failed.");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <section className="bg-white border border-slate-200 p-5 space-y-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Submission package
          </p>
          <p className="mt-1 font-mono text-sm text-slate-800">{pkg.id}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span
              className={`text-xs px-2 py-0.5 font-medium ${
                STATUS_STYLES[pkg.status] ?? "bg-slate-100 text-slate-700"
              }`}
            >
              {pkg.status}
            </span>
            {displayState === "packaging" && !pkg.error_message && (
              <span className="inline-flex items-center gap-1 text-xs text-blue-700">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Assembling package…
              </span>
            )}
          </div>
          {pkg.package_checksum && (
            <p className="mt-2 text-xs text-slate-500 font-mono break-all">
              Checksum: {pkg.package_checksum}
            </p>
          )}
          <p className="mt-1 text-xs text-slate-400">
            Updated {new Date(pkg.updated_at).toLocaleString()}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {permissions.canViewSubmissionManifest && (
            <button
              type="button"
              onClick={loadManifest}
              disabled={manifestLoading || pkg.status !== "READY"}
              className="inline-flex items-center gap-2 border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              <FileText className="h-4 w-4" />
              {manifestLoading ? "Loading…" : manifest ? "Refresh manifest" : "View manifest"}
            </button>
          )}
          {permissions.canDownloadSubmissionPackage && (
            <button
              type="button"
              onClick={handleDownload}
              disabled={downloading || pkg.status !== "READY"}
              className="inline-flex items-center gap-2 bg-brand-600 px-3 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
            >
              <Download className="h-4 w-4" />
              {downloading ? "Downloading…" : "Download ZIP"}
            </button>
          )}
        </div>
      </div>

      {pkg.error_message && (
        <div className="rounded border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-semibold">Package assembly failed</p>
              <p className="mt-1">{pkg.error_message}</p>
              {permissions.canCreateSubmissionPackage && onRecreate && (
                <button
                  type="button"
                  onClick={onRecreate}
                  disabled={isRecreating}
                  className="mt-3 bg-red-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-800 disabled:opacity-50"
                >
                  {isRecreating ? "Creating…" : "Create new package"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {downloadError && (
        <p className="text-sm text-red-600">{downloadError}</p>
      )}

      {manifestError && (
        <p className="text-sm text-red-600">{manifestError}</p>
      )}

      {manifest && (
        <div className="space-y-3">
          {showSyntheticBanner && (
            <div className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              <strong>SYNTHETIC DEMO DATA</strong> — This package was assembled from
              synthetic demo seeds. It is demonstrable for workflow review only and is{" "}
              <strong>not for regulatory submission</strong>.
            </div>
          )}
          <ManifestTable files={manifest.manifest.files ?? []} />
        </div>
      )}

      {!permissions.canViewSubmissionManifest && !permissions.canDownloadSubmissionPackage && (
        <p className="text-xs text-slate-500">
          Package status for study {studyId} is visible. Manifest inspection and ZIP export
          require Admin or Reviewer (manifest only) roles.
        </p>
      )}
    </section>
  );
}
