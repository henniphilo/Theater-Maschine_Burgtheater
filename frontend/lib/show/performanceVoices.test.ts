import { describe, expect, it } from "vitest";

import { speakerForPerformanceSentence } from "@/lib/show/performanceVoices";

describe("speakerForPerformanceSentence", () => {
  it("rotates Stimme A, B, Erzähler per sentence", () => {
    const speakers = Array.from({ length: 6 }, (_, i) =>
      speakerForPerformanceSentence("AI_A", i, 0)
    );
    expect(speakers).toEqual(["AI_A", "AI_B", "narrator", "AI_A", "AI_B", "narrator"]);
  });

  it("never returns dramaturg speaker ids", () => {
    for (let i = 0; i < 5; i++) {
      const speaker = speakerForPerformanceSentence("narrator", i, 2);
      expect(speaker).not.toBe("openai");
      expect(speaker).not.toBe("anthropic");
    }
  });
});
