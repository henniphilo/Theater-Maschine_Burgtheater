import type { AvatarTextSegment, CompositionMoment, CompositionPlan, Teil2PerformancePlan } from "@/lib/types/inszenierung";
import type { DramaturgyDecision, OscCommand } from "@/lib/types/director";
import type { VisualCue } from "@/lib/types/visual";
import { isDirectorPerformanceAborted, postDirectorExecuteLayered } from "@/lib/api/director";
import { waitWhilePlaybackPaused } from "@/lib/api/client";

export async function executeAvatarVisualCue(
  visual: VisualCue,
  anarchyLevel: number,
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean,
  textExcerpt?: string
): Promise<boolean> {
  if (shouldAbort() || isDirectorPerformanceAborted()) return false;
  const decision: DramaturgyDecision = {
    reason: "Avatar-Sprache",
    tags: ["teil2", "avatar"],
    mood: "tension",
    intensity: anarchyLevel,
    visual,
    timestamp: Date.now()
  };
  try {
    const result = await postDirectorExecuteLayered(decision, {
      anarchy_level: anarchyLevel,
      stack: true,
      skip_interval_check: true,
      stagger: false,
      text_excerpt: textExcerpt
    });
    if (shouldAbort() || isDirectorPerformanceAborted()) return false;
    if (result.osc_commands.length > 0) {
      void onCommands(result.osc_commands).catch((err) => {
        console.warn("Avatar cue highlight failed (playback continues):", err);
      });
    }
    return result.executed;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") return false;
    console.warn("Avatar cue failed (playback continues):", err);
    return false;
  }
}

export function avatarVisualCuesForMoment(moment: CompositionMoment): VisualCue[] {
  const fromLayers = (moment.avatar_layers ?? [])
    .map((layer) => layer.visual_cue)
    .filter((cue): cue is VisualCue => Boolean(cue));
  if (fromLayers.length > 0) return fromLayers;
  if (moment.avatar_video_cue) return [moment.avatar_video_cue];
  return [];
}

export async function fireAvatarSegmentCues(
  segment: AvatarTextSegment,
  anarchyLevel: number,
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean
): Promise<void> {
  for (const layer of segment.avatar_layers) {
    if (!layer.visual_cue) continue;
    if (shouldAbort()) return;
    if (!(await waitWhilePlaybackPaused(shouldAbort))) return;
    await executeAvatarVisualCue(
      layer.visual_cue,
      anarchyLevel,
      onCommands,
      shouldAbort,
      segment.text_excerpt
    );
  }
}

export async function fireAvatarMomentCues(
  moment: CompositionMoment,
  anarchyLevel: number,
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean
): Promise<void> {
  for (const visual of avatarVisualCuesForMoment(moment)) {
    if (shouldAbort()) return;
    await executeAvatarVisualCue(visual, anarchyLevel, onCommands, shouldAbort, moment.text_excerpt);
  }
}

export function momentNeedsAvatarVisualRefresh(moment: CompositionMoment): boolean {
  if ((moment.speech_mode ?? "tts") !== "avatar_video") return false;
  if (!moment.avatar_layers?.length && !moment.avatar_speech_id && !moment.avatar_video_clip_id) {
    return false;
  }
  return avatarVisualCuesForMoment(moment).length === 0;
}

export function planNeedsAvatarVisualRefresh(plan: CompositionPlan): boolean {
  return plan.moments.some((moment) => momentNeedsAvatarVisualRefresh(moment));
}

export function planRequiresTts(plan: CompositionPlan): boolean {
  return plan.moments.some((moment) => (moment.speech_mode ?? "tts") === "tts");
}

export function teil2PlanRequiresTts(): boolean {
  return true;
}

export function avatarSegmentKey(segment: AvatarTextSegment): string {
  if (segment.char_offset != null) return `offset:${segment.char_offset}`;
  return `sentence:${segment.start_sentence_index}:${segment.csv_cue_ids.join(",")}`;
}

export function resolveSentenceCharStarts(plan: Teil2PerformancePlan, scriptText: string): number[] {
  if (
    plan.sentence_char_starts?.length === plan.sentences.length &&
    plan.sentence_char_starts.length > 0
  ) {
    return plan.sentence_char_starts;
  }
  const starts: number[] = [];
  let searchFrom = 0;
  for (const sentence of plan.sentences) {
    const stripped = sentence.trim();
    let start = scriptText.indexOf(stripped, searchFrom);
    if (start < 0 && stripped.length > 12) {
      start = scriptText.indexOf(stripped.slice(0, Math.min(32, stripped.length)), searchFrom);
    }
    if (start < 0) start = searchFrom;
    starts.push(start);
    searchFrom = Math.max(searchFrom, start + stripped.length);
  }
  return starts;
}

export function effectiveCharOffset(segment: AvatarTextSegment, sentenceCharStarts: number[]): number {
  if (segment.char_offset != null) return segment.char_offset;
  return sentenceCharStarts[segment.start_sentence_index] ?? 0;
}

export function avatarSegmentsDueAtPosition(
  plan: Teil2PerformancePlan,
  globalPos: number,
  fired: Set<string>,
  sentenceCharStarts: number[]
): AvatarTextSegment[] {
  return plan.avatar_segments
    .filter((segment) => {
      if (fired.has(avatarSegmentKey(segment))) return false;
      return globalPos >= effectiveCharOffset(segment, sentenceCharStarts);
    })
    .sort(
      (a, b) =>
        effectiveCharOffset(a, sentenceCharStarts) - effectiveCharOffset(b, sentenceCharStarts)
    );
}

export async function fireAvatarSegmentsAtPosition(
  plan: Teil2PerformancePlan,
  globalPos: number,
  fired: Set<string>,
  sentenceCharStarts: number[],
  anarchyLevelFor: (segment: AvatarTextSegment) => number,
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean,
  onSegmentFired?: (segment: AvatarTextSegment) => void
): Promise<void> {
  const due = avatarSegmentsDueAtPosition(plan, globalPos, fired, sentenceCharStarts);
  for (const segment of due) {
    if (shouldAbort()) return;
    fired.add(avatarSegmentKey(segment));
    onSegmentFired?.(segment);
    await fireAvatarSegmentCues(segment, anarchyLevelFor(segment), onCommands, shouldAbort);
  }
}

export async function fireRemainingSentenceSegments(
  plan: Teil2PerformancePlan,
  sentenceIndex: number,
  fired: Set<string>,
  anarchyLevel: number,
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean,
  onSegmentFired?: (segment: AvatarTextSegment) => void
): Promise<void> {
  for (const segment of plan.avatar_segments) {
    if (segment.start_sentence_index !== sentenceIndex) continue;
    if (fired.has(avatarSegmentKey(segment))) continue;
    if (shouldAbort()) return;
    fired.add(avatarSegmentKey(segment));
    onSegmentFired?.(segment);
    await fireAvatarSegmentCues(segment, anarchyLevel, onCommands, shouldAbort);
  }
}
