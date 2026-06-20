import type { PerformanceSpeaker } from "@/lib/types/director";
import type { ScriptSpeaker } from "@/lib/types/script";

const DEFAULT_POOL: ScriptSpeaker[] = ["AI_A", "AI_B", "narrator"];

function normalizePool(pool?: PerformanceSpeaker[]): ScriptSpeaker[] {
  if (!pool?.length) return DEFAULT_POOL;
  const valid = pool.filter((speaker): speaker is ScriptSpeaker =>
    DEFAULT_POOL.includes(speaker as ScriptSpeaker)
  );
  return valid.length > 0 ? valid : DEFAULT_POOL;
}

/** Assigns Stimme A / B / Erzähler per sentence — never dramaturg speakers. */
export function speakerForPerformanceSentence(
  beatSpeaker: ScriptSpeaker,
  sentenceIndex: number,
  beatOrder: number,
  pool?: PerformanceSpeaker[]
): ScriptSpeaker {
  const speakers = normalizePool(pool);
  const base = speakers.indexOf(beatSpeaker);
  const start = base >= 0 ? base : beatOrder % speakers.length;
  return speakers[(start + sentenceIndex) % speakers.length];
}
