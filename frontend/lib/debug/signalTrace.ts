/** Frontend signal trace ring buffer (correlates with backend logs/signal_trace.jsonl). */

export type TraceContext = {
  frontend_run_id?: string;
  frontend_generation?: number;
  source?: string;
  trigger?: string;
  cue_point_key?: string;
  segment_key?: string;
  frontend_route?: string;
};

export type SignalTraceEvent = {
  schema_version: number;
  event: string;
  ts_wall: string;
  ts_mono_ms: number;
  status?: string;
  [key: string]: unknown;
};

const RING_CAPACITY = 2000;
const events: SignalTraceEvent[] = [];

let currentFrontendRunId: string | null = null;
let currentFrontendGeneration: number | null = null;

export function createFrontendRunId(): string {
  return `fe-run-${Date.now()}`;
}

export function setFrontendPlaybackContext(runId: string, generation: number): void {
  currentFrontendRunId = runId;
  currentFrontendGeneration = generation;
}

export function clearFrontendPlaybackContext(): void {
  currentFrontendRunId = null;
  currentFrontendGeneration = null;
}

export function getFrontendRunId(): string | null {
  return currentFrontendRunId;
}

export function buildTraceContext(extra?: Partial<TraceContext>): TraceContext | undefined {
  const base: TraceContext = {};
  if (currentFrontendRunId) base.frontend_run_id = currentFrontendRunId;
  if (currentFrontendGeneration != null) base.frontend_generation = currentFrontendGeneration;
  if (extra) Object.assign(base, extra);
  return Object.keys(base).length > 0 ? base : extra;
}

export function logSignalTraceEvent(
  event: string,
  fields: Record<string, unknown> = {},
  options?: { status?: string }
): void {
  const payload: SignalTraceEvent = {
    schema_version: 1,
    event,
    ts_wall: new Date().toISOString(),
    ts_mono_ms: Math.round(performance.now()),
    ...fields
  };
  if (options?.status) payload.status = options.status;
  events.push(payload);
  if (events.length > RING_CAPACITY) {
    events.splice(0, events.length - RING_CAPACITY);
  }
  if (typeof console !== "undefined" && console.debug) {
    console.debug("[signal-trace]", event, payload);
  }
}

export function startFrontendPlaybackTrace(options: {
  generation: number;
  source: string;
  route?: string;
  mode?: string;
}): string {
  const runId = createFrontendRunId();
  setFrontendPlaybackContext(runId, options.generation);
  logSignalTraceEvent(
    "frontend.playback_started",
    {
      frontend_run_id: runId,
      frontend_generation: options.generation,
      source: options.source,
      route: options.route,
      mode: options.mode
    },
    { status: "playback_started" }
  );
  return runId;
}

export function getSignalTraceEvents(): readonly SignalTraceEvent[] {
  return events;
}

export function exportSignalTraceJsonl(): string {
  return events.map((e) => JSON.stringify(e)).join("\n");
}

declare global {
  interface Window {
    __TM_SIGNAL_TRACE__?: {
      events: readonly SignalTraceEvent[];
      exportJsonl: () => string;
    };
  }
}

if (typeof window !== "undefined") {
  window.__TM_SIGNAL_TRACE__ = {
    events,
    exportJsonl: exportSignalTraceJsonl
  };
}
