import { describe, expect, it, vi, beforeEach } from "vitest";

import { executeCueSafely } from "@/features/show/cuePlayback";
import type { DramaturgyDecision } from "@/lib/types/director";

vi.mock("@/lib/api/director", () => ({
  postDirectorExecute: vi.fn()
}));

import { postDirectorExecute } from "@/lib/api/director";

const decision: DramaturgyDecision = {
  sound: { action: "trigger_cue", cue_id: "maschinen_grundader" },
  reason: "test",
  tags: [],
  mood: "neutral",
  intensity: 0.5,
  timestamp: 0
};

describe("executeCueSafely", () => {
  beforeEach(() => {
    vi.mocked(postDirectorExecute).mockReset();
  });

  it("continues without throwing when director execute fails", async () => {
    vi.mocked(postDirectorExecute).mockRejectedValue(new Error("Director execute failed"));
    const onCommands = vi.fn();

    const executed = await executeCueSafely(decision, onCommands, () => false);

    expect(executed).toBe(false);
    expect(onCommands).not.toHaveBeenCalled();
  });

  it("forwards osc commands on success", async () => {
    const cmd = {
      bridge: "sound",
      host: "127.0.0.1",
      port: 9000,
      address: "/sound/trigger",
      args: ["maschinen_grundader", 0.6],
      dry_run: false
    };
    vi.mocked(postDirectorExecute).mockResolvedValue({
      executed: true,
      blocked_reason: null,
      osc_commands: [cmd]
    });
    const onCommands = vi.fn().mockResolvedValue(undefined);

    const executed = await executeCueSafely(decision, onCommands, () => false);

    expect(executed).toBe(true);
    expect(onCommands).toHaveBeenCalledWith([cmd]);
  });
});
