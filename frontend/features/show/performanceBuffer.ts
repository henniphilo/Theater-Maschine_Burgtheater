import type { ProductionScript } from "@/lib/types/script";
import {
  warmScriptPlayback,
  type PlaybackAudioOptions,
  type ScriptBufferProgress
} from "@/features/show/scriptPlayback";

export type ScriptBufferStatus = "idle" | "buffering" | "ready" | "error";

export type ScriptBufferState = {
  scriptId: string | null;
  status: ScriptBufferStatus;
  loaded: number;
  total: number;
  error?: string;
};

const INITIAL_STATE: ScriptBufferState = {
  scriptId: null,
  status: "idle",
  loaded: 0,
  total: 0
};

type Listener = (state: ScriptBufferState) => void;

let state: ScriptBufferState = INITIAL_STATE;
let bufferGeneration = 0;
const listeners = new Set<Listener>();

function emit(patch: Partial<ScriptBufferState>): void {
  state = { ...state, ...patch };
  for (const listener of listeners) listener(state);
}

export function getScriptBufferState(): ScriptBufferState {
  return state;
}

export function subscribeScriptBuffer(listener: Listener): () => void {
  listeners.add(listener);
  listener(state);
  return () => listeners.delete(listener);
}

export function isPlaybackBuffered(
  scriptId: string,
  options: PlaybackAudioOptions
): boolean {
  if (options.hasRenderedAudio) return true;
  if (!options.ttsAvailable) return false;
  return state.scriptId === scriptId && state.status === "ready";
}

export function startScriptBuffer(
  script: ProductionScript,
  options: PlaybackAudioOptions
): void {
  if (options.hasRenderedAudio) {
    emit({
      scriptId: script.id,
      status: "ready",
      loaded: 0,
      total: 0,
      error: undefined
    });
    return;
  }

  if (!options.ttsAvailable) {
    emit({
      scriptId: script.id,
      status: "error",
      loaded: 0,
      total: 0,
      error: "Keine Stimmen verfügbar"
    });
    return;
  }

  if (
    state.scriptId === script.id &&
    (state.status === "buffering" || state.status === "ready")
  ) {
    return;
  }

  const generation = ++bufferGeneration;
  emit({
    scriptId: script.id,
    status: "buffering",
    loaded: 0,
    total: 0,
    error: undefined
  });

  void warmScriptPlayback(script, options, (progress: ScriptBufferProgress) => {
    if (generation !== bufferGeneration) return;
    const ready = progress.total === 0 || progress.loaded >= progress.total;
    emit({
      loaded: progress.loaded,
      total: progress.total,
      status: ready ? "ready" : "buffering"
    });
  })
    .then(() => {
      if (generation !== bufferGeneration) return;
      emit({ status: "ready" });
    })
    .catch((err: unknown) => {
      if (generation !== bufferGeneration) return;
      emit({
        status: "error",
        error: err instanceof Error ? err.message : "Stimmen-Puffer fehlgeschlagen"
      });
    });
}

export function cancelScriptBuffer(): void {
  bufferGeneration++;
  emit(INITIAL_STATE);
}

export function bufferStatusLabel(buffer: ScriptBufferState): string {
  if (buffer.status === "buffering") {
    if (buffer.total > 0) {
      return `Stimmen werden geladen … ${buffer.loaded}/${buffer.total}`;
    }
    return "Stimmen werden geladen …";
  }
  if (buffer.status === "ready") return "Stimmen bereit";
  if (buffer.status === "error") return buffer.error ?? "Stimmen konnten nicht geladen werden";
  return "";
}
