"use client";

import { useState } from "react";
import { artifactsApi } from "@/lib/api/artifacts";
import {
  getArtifactDownloadConfig,
  getArtifactDownloadOptions,
  triggerBlobDownload,
  type ArtifactExportFormat,
} from "@/lib/artifactDownload";
import type { Artifact } from "@/types";

export function useArtifactDownload(token: string | null) {
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  async function downloadArtifact(
    artifact: Pick<
      Artifact,
      | "id"
      | "artifact_type"
      | "name"
      | "description"
      | "current_version_id"
      | "current_version_number"
    >,
    formatOverride?: ArtifactExportFormat
  ) {
    if (!token) {
      throw new Error("Not authenticated.");
    }
    if (!artifact.current_version_id) {
      throw new Error("Artifact has no content to download.");
    }

    const config = getArtifactDownloadConfig(artifact.artifact_type, artifact);
    const format = formatOverride ?? config?.format;
    if (!format) {
      throw new Error("Download is not available for this artifact type.");
    }

    setDownloadingId(artifact.id);
    setDownloadError(null);
    try {
      const { blob, filename } = await artifactsApi.exportArtifact(
        artifact.id,
        format,
        token,
        artifact
      );
      triggerBlobDownload(blob, filename);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Download failed.";
      setDownloadError(message);
      throw err;
    } finally {
      setDownloadingId(null);
    }
  }

  function isDownloading(artifactId: string) {
    return downloadingId === artifactId;
  }

  return {
    downloadArtifact,
    isDownloading,
    downloadError,
    setDownloadError,
    getDownloadLabel: (artifact: Pick<Artifact, "artifact_type" | "name" | "description">) => {
      const config = getArtifactDownloadConfig(artifact.artifact_type, artifact);
      if (!config) return null;
      return config.label;
    },
    getDownloadOptions: (artifact: Pick<Artifact, "artifact_type" | "name" | "description">) =>
      getArtifactDownloadOptions(artifact.artifact_type, artifact),
  };
}
