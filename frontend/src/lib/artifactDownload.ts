import type { ArtifactType } from "@/types";

export type ArtifactExportFormat = "docx" | "pdf" | "csv" | "zip" | "xml";

export interface ArtifactDownloadOption {
  label: string;
  format: ArtifactExportFormat;
  primary?: boolean;
}

const PRIMARY_DOWNLOAD: Partial<Record<ArtifactType, ArtifactDownloadOption>> = {
  PROTOCOL: { label: "Download Word", format: "docx", primary: true },
  SAP: { label: "Download Word", format: "docx", primary: true },
  CSR: { label: "Download Word", format: "docx", primary: true },
  ICF: { label: "Download PDF", format: "pdf", primary: true },
  TLF: { label: "Download PDF", format: "pdf", primary: true },
  EDC_CRF: { label: "Download PDF", format: "pdf", primary: true },
  SDTM_DATASET: { label: "Download ZIP", format: "zip", primary: true },
  ADAM_DATASET: { label: "Download ZIP", format: "zip", primary: true },
  OTHER: { label: "Download CSV", format: "csv", primary: true },
};

const SECONDARY_DOWNLOAD: Partial<Record<ArtifactType, ArtifactDownloadOption[]>> = {
  SDTM_DATASET: [{ label: "Download define.xml", format: "xml" }],
};

function isSyntheticArtifact(artifact?: {
  name?: string;
  description?: string | null;
}): boolean {
  if (!artifact) return false;
  return (
    artifact.name?.includes("Synthetic") ||
    (artifact.description?.includes("SYNTHETIC") ?? false)
  );
}

export function getArtifactDownloadOptions(
  artifactType: ArtifactType,
  artifact?: { name?: string; description?: string | null }
): ArtifactDownloadOption[] {
  if (artifactType === "OTHER" && !isSyntheticArtifact(artifact)) {
    return [];
  }

  const primary = PRIMARY_DOWNLOAD[artifactType];
  if (!primary) {
    return [];
  }

  const secondary = SECONDARY_DOWNLOAD[artifactType] ?? [];
  return [primary, ...secondary];
}

export function getArtifactDownloadConfig(
  artifactType: ArtifactType,
  artifact?: { name?: string; description?: string | null }
): ArtifactDownloadOption | null {
  return getArtifactDownloadOptions(artifactType, artifact).find((o) => o.primary) ?? null;
}

export function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
