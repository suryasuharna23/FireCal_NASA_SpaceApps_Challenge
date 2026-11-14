import { ApiError, BASE_URL } from '../api/client';

export type ExportKind = 'monthly' | 'points';

export interface ExportProgress {
  bytes: number;
  rows: number;
}

/** Filename from a Content-Disposition header, with a fallback. */
export function filenameFrom(header: string | null, fallback: string): string {
  const match = header?.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
  return match?.[1] ? decodeURIComponent(match[1]) : fallback;
}

/** Trigger a browser download for a Blob. */
export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * POST /export and stream the CSV, reporting received bytes and data rows so large
 * point exports show progress (NFR-02). Resolves with the saved filename.
 */
export async function downloadExport(
  kind: ExportKind,
  body: Record<string, unknown>,
  onProgress?: (p: ExportProgress) => void,
  signal?: AbortSignal,
): Promise<string> {
  const response = await fetch(`${BASE_URL}/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...body, kind }),
    signal,
  });
  if (!response.ok) {
    let detail = `Export failed (${response.status})`;
    try {
      const err = await response.json();
      if (typeof err?.detail === 'string') detail = err.detail;
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(detail, response.status);
  }

  const chunks: BlobPart[] = [];
  let bytes = 0;
  let lines = 0;
  const reader = response.body?.getReader();
  if (reader) {
    const decoder = new TextDecoder();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      bytes += value.byteLength;
      lines += (decoder.decode(value, { stream: true }).match(/\n/g) ?? []).length;
      onProgress?.({ bytes, rows: Math.max(lines - 5, 0) });
    }
  } else {
    const text = await response.text();
    chunks.push(text);
    bytes = text.length;
  }

  const filename = filenameFrom(response.headers.get('Content-Disposition'), `firecal_${kind}.csv`);
  saveBlob(new Blob(chunks, { type: 'text/csv' }), filename);
  return filename;
}
