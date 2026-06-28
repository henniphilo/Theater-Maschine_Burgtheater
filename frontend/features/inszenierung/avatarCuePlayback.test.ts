import { describe, expect, it } from "vitest";

import {
  avatarSegmentKey,
  avatarSegmentsDueAtPosition,
  effectiveCharOffset,
  resolveSentenceCharStarts
} from "@/features/inszenierung/avatarCuePlayback";
import type { Teil2PerformancePlan } from "@/lib/types/inszenierung";

describe("avatarCuePlayback position helpers", () => {
  const plan: Teil2PerformancePlan = {
    performance_speaker: "narrator",
    sentences: ["Alpha.", "Beta gamma delta."],
    sentence_char_starts: [0, 7],
    avatar_segments: [
      {
        csv_cue_ids: ["a"],
        text_excerpt: "gamma",
        char_offset: 12,
        start_sentence_index: 1,
        end_sentence_index: 1,
        avatar_layers: []
      }
    ],
    dramaturgy: { reason: "t", tags: [], mood: "tension", intensity: 0.5, cue_points: [] },
    anarchy_level_end: 1,
    alignment_warnings: []
  };

  it("resolves sentence char starts from plan", () => {
    expect(resolveSentenceCharStarts(plan, "Alpha. Beta gamma delta.")).toEqual([0, 7]);
  });

  it("returns segments due only after global position reaches char_offset", () => {
    const fired = new Set<string>();
    const starts = plan.sentence_char_starts!;
    expect(avatarSegmentsDueAtPosition(plan, 10, fired, starts)).toHaveLength(0);
    const due = avatarSegmentsDueAtPosition(plan, 12, fired, starts);
    expect(due).toHaveLength(1);
    expect(avatarSegmentKey(due[0])).toBe("offset:12");
    expect(effectiveCharOffset(due[0], starts)).toBe(12);
  });
});
