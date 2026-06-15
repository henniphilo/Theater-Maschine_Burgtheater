import type { ScriptSpeaker } from "@/lib/types/script";

const PERFORMANCE_POOL: ScriptSpeaker[] = ["AI_A", "AI_B", "narrator"];

/** Assigns Stimme A / B / Erzähler per sentence — never dramaturg speakers. */
export function speakerForPerformanceSentence(
  beatSpeaker: ScriptSpeaker,
  sentenceIndex: number,
  beatOrder: number
): ScriptSpeaker {
  const base = PERFORMANCE_POOL.indexOf(beatSpeaker);
  const start = base >= 0 ? base : beatOrder % PERFORMANCE_POOL.length;
  return PERFORMANCE_POOL[(start + sentenceIndex) % PERFORMANCE_POOL.length];
}
