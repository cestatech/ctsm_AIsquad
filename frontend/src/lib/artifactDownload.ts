import type { Artifact, ArtifactType } from "@/types";

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

const TYPE_FILENAME_PREFIX: Partial<Record<ArtifactType, string>> = {
  PROTOCOL: "protocol",
  SAP: "sap",
  CSR: "csr",
  ICF: "icf",
  TLF: "tlf",
  EDC_CRF: "edc_ecrf",
  SDTM_DATASET: "sdtm",
  ADAM_DATASET: "adam",
  OTHER: "synthetic_raw",
  VALIDATION_REPORT: "validation_report",
  TRACEABILITY_MATRIX: "traceability_matrix",
  SUBMISSION_PACKAGE: "submission_package",
};

function slugify(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || "study";
}

export function buildArtifactFallbackFilename(
  artifact: Pick<Artifact, "artifact_type" | "name" | "current_version_number">,
  format: ArtifactExportFormat
): string {
  const prefix = TYPE_FILENAME_PREFIX[artifact.artifact_type] ?? slugify(artifact.artifact_type);
  const slug = slugify(artifact.name);
  const version = artifact.current_version_number ?? 1;
  if (format === "xml") {
    return `${prefix}_${slug}_v${version}_define.xml`;
  }
  return `${prefix}_${slug}_v${version}.${format}`;
}

export function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
