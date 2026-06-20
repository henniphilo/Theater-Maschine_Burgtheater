import { afterEach, describe, expect, it, vi } from "vitest";

import type { ProductionScript } from "@/lib/types/script";
import {
  bufferStatusLabel,
  cancelScriptBuffer,
  getScriptBufferState,
  isPlaybackBuffered,
  startScriptBuffer,
  subscribeScriptBuffer
} from "./performanceBuffer";

vi.mock("@/features/show/scriptPlayback", () => ({
  warmScriptPlayback: vi.fn(
    async (
      _script: ProductionScript,
      _options: unknown,
      onProgress?: (progress: { loaded: number; total: number }) => void
    ) => {
      onProgress?.({ loaded: 0, total: 2 });
      onProgress?.({ loaded: 1, total: 2 });
      onProgress?.({ loaded: 2, total: 2 });
    }
  )
}));

const script: ProductionScript = {
  id: "script-1",
  title: "Test",
  status: "ready",
  beats: [],
  has_rendered_audio: false
};

afterEach(() => {
  cancelScriptBuffer();
  vi.clearAllMocks();
});

describe("performanceBuffer", () => {
  it("marks rendered audio as ready immediately", () => {
    startScriptBuffer(script, {
      ttsAvailable: false,
      scriptId: script.id,
      hasRenderedAudio: true
    });
    expect(getScriptBufferState().status).toBe("ready");
    expect(isPlaybackBuffered(script.id, { ttsAvailable: false, hasRenderedAudio: true })).toBe(true);
  });

  it("reports error when TTS is unavailable", () => {
    startScriptBuffer(script, {
      ttsAvailable: false,
      scriptId: script.id,
      hasRenderedAudio: false
    });
    expect(getScriptBufferState().status).toBe("error");
  });

  it("buffers script and notifies subscribers", async () => {
    const states: string[] = [];
    subscribeScriptBuffer((state) => states.push(state.status));

    startScriptBuffer(script, {
      ttsAvailable: true,
      scriptId: script.id,
      hasRenderedAudio: false
    });

    await vi.waitFor(() => {
      expect(getScriptBufferState().status).toBe("ready");
    });

    expect(states).toContain("buffering");
    expect(states).toContain("ready");
    expect(isPlaybackBuffered(script.id, { ttsAvailable: true, hasRenderedAudio: false })).toBe(true);
  });

  it("does not restart an active buffer for the same script", async () => {
    const { warmScriptPlayback } = await import("@/features/show/scriptPlayback");
    startScriptBuffer(script, { ttsAvailable: true, scriptId: script.id, hasRenderedAudio: false });
    await vi.waitFor(() => {
      expect(getScriptBufferState().status).toBe("ready");
    });
    startScriptBuffer(script, { ttsAvailable: true, scriptId: script.id, hasRenderedAudio: false });
    expect(warmScriptPlayback).toHaveBeenCalledTimes(1);
  });

  it("formats buffering status label", () => {
    expect(bufferStatusLabel({ scriptId: "x", status: "buffering", loaded: 3, total: 10 })).toContain("3/10");
    expect(bufferStatusLabel({ scriptId: "x", status: "ready", loaded: 10, total: 10 })).toBe("Stimmen bereit");
  });
});
