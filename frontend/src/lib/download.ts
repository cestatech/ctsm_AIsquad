/** Trigger a browser download of text content. */
export function downloadTextFile(filename: string, content: string): void {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  triggerBlobDownload(filename, blob);
}

/** Trigger a browser download of a Blob. */
export function triggerBlobDownload(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function parseContentDispositionFilename(disposition: string): string | null {
  const match = disposition.match(/filename="([^"]+)"/);
  return match?.[1] ?? null;
}

function parseApiErrorDetail(response: Response, fallback: string): Promise<string> {
  return response
    .json()
    .then((err: { detail?: string | { message?: string } }) => {
      const raw = err.detail;
      if (typeof raw === "string") return raw;
      return raw?.message ?? fallback;
    })
    .catch(() => fallback);
}

/**
 * Download a binary or text file from an authenticated API endpoint.
 * Returns the blob and resolved filename for callers that need both.
 */
export async function downloadAuthenticatedBlob(
  url: string,
  token: string,
  fallbackFilename: string
): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
    credentials: "include",
  });
  if (!response.ok) {
    const detail = await parseApiErrorDetail(response, "Download failed");
    throw new Error(detail);
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename =
    parseContentDispositionFilename(disposition) ?? fallbackFilename;
  const blob = await response.blob();
  return { blob, filename };
}

/** Download from authenticated API endpoint as text (e.g. R program exports). */
export async function downloadAuthenticatedFile(
  url: string,
  filename: string,
  token: string
): Promise<void> {
  const { blob } = await downloadAuthenticatedBlob(url, token, filename);
  const text = await blob.text();
  downloadTextFile(filename, text);
}
