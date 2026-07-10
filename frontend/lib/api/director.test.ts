import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  buildTraceContext,
  getSignalTraceEvents,
  logSignalTraceEvent,
  setFrontendPlaybackContext
} from "@/lib/debug/signalTrace";

const fetchMock = vi.fn();

vi.mock("@/lib/api/base", () => ({
  apiBaseUrl: () => "http://localhost:8000",
  apiFetch: (...args: unknown[]) => fetchMock(...args)
}));

describe("director trace", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    setFrontendPlaybackContext("fe-run-test", 5);
  });

  afterEach(() => {
    vi.resetModules();
  });

  it("includes trace context in execute body", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ executed: true, blocked_reason: null, osc_commands: [] })
    });
    const { postDirectorExecute } = await import("@/lib/api/director");
    await postDirectorExecute(
      {
        reason: "test",
        tags: [],
        mood: "neutral",
        intensity: 0.5,
        timestamp: 0
      },
      { trace: buildTraceContext({ source: "cuePlayback", trigger: "sentence" }) }
    );
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(String(init.body));
    expect(body.trace.frontend_run_id).toBe("fe-run-test");
    expect(body.trace.frontend_generation).toBe(5);
    expect(body.trace.source).toBe("cuePlayback");
  });

  it("logs aborted requests in trace buffer", async () => {
    const abortError = new Error("aborted");
    abortError.name = "AbortError";
    fetchMock.mockRejectedValue(abortError);
    const director = await import("@/lib/api/director");
    const trace = await import("@/lib/debug/signalTrace");
    await expect(
      director.postDirectorExecute({
        reason: "test",
        tags: [],
        mood: "neutral",
        intensity: 0.5,
        timestamp: 0
      })
    ).rejects.toBeTruthy();
    const events = trace.getSignalTraceEvents().map((e) => e.event);
    expect(events).toContain("frontend.request_started");
    expect(events).toContain("frontend.request_aborted");
  });

  it("logs custom signal trace events", () => {
    logSignalTraceEvent("frontend.stop_requested", { frontend_generation: 9 });
    const last = getSignalTraceEvents().at(-1);
    expect(last?.event).toBe("frontend.stop_requested");
    expect(last?.frontend_generation).toBe(9);
  });
});
