/** Trigger a browser download of text content. */
export function downloadTextFile(filename: string, content: string): void {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

/** Download from authenticated API endpoint (e.g. R program exports). */
export async function downloadAuthenticatedFile(
  url: string,
  filename: string,
  token: string
): Promise<void> {
  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error(`Download failed (${response.status})`);
  }
  const text = await response.text();
  downloadTextFile(filename, text);
}
