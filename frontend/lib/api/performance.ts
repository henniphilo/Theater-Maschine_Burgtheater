import { apiBaseUrl, apiFetch } from "@/lib/api/base";

export function performanceAudioUrl(
  scriptId: string,
  beatId: string,
  kind: "discussion" | "performance",
  turnIndex?: number,
  sentenceIndex?: number
): string {
  let asset: string;
  if (kind === "performance") {
    asset = sentenceIndex !== undefined ? `performance-${sentenceIndex}` : "performance";
  } else {
    asset = `discussion-${turnIndex ?? 0}`;
  }
  return `${apiBaseUrl()}/scripts/${scriptId}/performance/audio/${beatId}/${asset}`;
}

const prerenderCache = new Map<string, Promise<Blob>>();

export function prefetchPrerenderedSpeech(url: string): Promise<Blob> {
  let pending = prerenderCache.get(url);
  if (!pending) {
    pending = fetch(url).then((res) => {
      if (!res.ok) throw new Error("Vorgespeicherte Audio-Datei nicht gefunden");
      return res.blob();
    });
    prerenderCache.set(url, pending);
  }
  return pending;
}

export function clearPrerenderedCache(): void {
  prerenderCache.clear();
}

export async function exportPerformance(scriptId: string): Promise<{ blob: Blob; filename: string }> {
  const res = await apiFetch(`/scripts/${scriptId}/performance/export`, { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Export fehlgeschlagen" }));
    throw new Error(body.detail ?? "Export fehlgeschlagen");
  }
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match?.[1] ?? "auffuehrung.tmshow.zip";
  const blob = await res.blob();
  return { blob, filename };
}

export async function importPerformance(file: File) {
  const form = new FormData();
  form.append("file", file);
  const res = await apiFetch("/scripts/performance/import", {
    method: "POST",
    body: form
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Import fehlgeschlagen" }));
    throw new Error(body.detail ?? "Import fehlgeschlagen");
  }
  return res.json();
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
