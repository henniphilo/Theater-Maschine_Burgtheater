import type {
  AnalyseStreamEvent,
  KompositionStreamEvent,
  SceneCorpus,
  Teil2ScriptResponse
} from "@/lib/types/inszenierung";
import type { PerformanceSpeaker } from "@/lib/types/director";
import { apiBaseUrl, apiFetch, apiFetchJson } from "@/lib/api/base";

const PREPARE_TIMEOUT_MS = 180_000;

export async function fetchScript(): Promise<Teil2ScriptResponse> {
  return apiFetchJson<Teil2ScriptResponse>("/inszenierung/script");
}

export async function createCorpus(title: string): Promise<SceneCorpus> {
  return apiFetchJson<SceneCorpus>("/inszenierung", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title })
  });
}

export async function fetchCorpus(corpusId: string): Promise<SceneCorpus> {
  return apiFetchJson<SceneCorpus>(`/inszenierung/${corpusId}`);
}

export async function patchCorpus(
  corpusId: string,
  payload: { title?: string; script_text?: string }
): Promise<SceneCorpus> {
  return apiFetchJson<SceneCorpus>(`/inszenierung/${corpusId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function prepareCorpus(
  corpusId: string,
  options?: { openai_model?: string; performance_speaker?: PerformanceSpeaker }
): Promise<SceneCorpus> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), PREPARE_TIMEOUT_MS);
  try {
    return await apiFetchJson<SceneCorpus>(`/inszenierung/${corpusId}/prepare`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        openai_model: options?.openai_model ?? "gpt-4o",
        performance_speaker: options?.performance_speaker ?? "narrator"
      }),
      signal: controller.signal
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("Vorbereiten dauert zu lange (>3 Min.) — bitte erneut versuchen.");
    }
    throw err;
  } finally {
    clearTimeout(timeout);
  }
}

export async function composeScript(corpusId: string): Promise<SceneCorpus> {
  return apiFetchJson<SceneCorpus>(`/inszenierung/${corpusId}/compose-script`, {
    method: "POST"
  });
}

export async function exportTeil2(corpusId: string): Promise<{ blob: Blob; filename: string }> {
  const res = await apiFetch(`/inszenierung/${corpusId}/export`, { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Export fehlgeschlagen" }));
    throw new Error(body.detail ?? "Export fehlgeschlagen");
  }
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match?.[1] ?? "teil2.tmteil2.zip";
  const blob = await res.blob();
  return { blob, filename };
}

export async function importTeil2(file: File): Promise<SceneCorpus> {
  const form = new FormData();
  form.append("file", file);
  const res = await apiFetch("/inszenierung/import", {
    method: "POST",
    body: form
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Import fehlgeschlagen" }));
    throw new Error(body.detail ?? "Import fehlgeschlagen");
  }
  return res.json();
}

type StreamHandlers<T> = {
  onEvent: (event: T) => void;
  onError: (detail: string) => void;
};

async function consumeSse<T>(
  url: string,
  body: object,
  handlers: StreamHandlers<T>
): Promise<void> {
  const res = await apiFetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => ({ detail: "Stream fehlgeschlagen" }));
    throw new Error(err.detail ?? "Stream fehlgeschlagen");
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      const raw = line.slice(5).trim();
      if (!raw) continue;
      const event = JSON.parse(raw) as T & { type: string; detail?: string };
      if (event.type === "error") {
        handlers.onError((event as { detail?: string }).detail ?? "Stream fehlgeschlagen");
      } else {
        handlers.onEvent(event);
      }
    }
  }
}

export async function streamAnalyse(
  corpusId: string,
  options: { openai_model?: string; anthropic_model?: string },
  handlers: StreamHandlers<AnalyseStreamEvent>
): Promise<void> {
  await consumeSse(
    `${apiBaseUrl()}/inszenierung/${corpusId}/analyse/stream`,
    {
      openai_model: options.openai_model ?? "gpt-4o",
      anthropic_model: options.anthropic_model ?? "claude-sonnet-4-6"
    },
    handlers
  );
}

export async function streamKomposition(
  corpusId: string,
  options: { openai_model?: string; moment_count?: number },
  handlers: StreamHandlers<KompositionStreamEvent>
): Promise<void> {
  await consumeSse(
    `${apiBaseUrl()}/inszenierung/${corpusId}/komposition/stream`,
    {
      openai_model: options.openai_model ?? "gpt-4o",
      moment_count: options.moment_count ?? 12
    },
    handlers
  );
}
