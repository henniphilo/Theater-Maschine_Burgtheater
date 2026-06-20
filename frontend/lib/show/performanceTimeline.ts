import type { ScriptBeat } from "@/lib/types/script";
import { sentencesForBeat } from "@/features/show/cuePlayback";

export function beatSubstepCount(beat: ScriptBeat): number {
  const discussion = beat.discussion_turns?.length ?? 0;
  const performance = Math.max(1, sentencesForBeat(beat.text).length);
  return Math.max(1, discussion + performance);
}

export function totalSubsteps(beats: ScriptBeat[]): number {
  return beats.reduce((sum, beat) => sum + beatSubstepCount(beat), 0);
}

/** Map overall progress 0–1 to beat index (for scrubbing). */
export function beatIndexFromProgress(progress: number, beatCount: number): number {
  if (beatCount <= 0) return 0;
  const clamped = Math.max(0, Math.min(1, progress));
  return Math.min(beatCount - 1, Math.floor(clamped * beatCount));
}

/** Overall timeline position 0–1 from beat index and fraction within beat. */
export function progressFromBeat(beatIndex: number, beatCount: number, segmentFraction = 0): number {
  if (beatCount <= 0) return 0;
  const clamped = Math.max(0, Math.min(1, segmentFraction));
  return Math.min(1, (beatIndex + clamped) / beatCount);
}

export function formatTimelineLabel(beatIndex: number, beatCount: number): string {
  if (beatCount <= 0) return "—";
  return `Abschnitt ${Math.min(beatIndex + 1, beatCount)} / ${beatCount}`;
}
