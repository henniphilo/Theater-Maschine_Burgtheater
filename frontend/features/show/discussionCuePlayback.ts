import { postDirectorDialogueEvent } from "@/lib/api/director";
import type { DramaturgyDecision, OscCommand } from "@/lib/types/director";
import type { DiscussionTurn, DramaturgSpeaker } from "@/lib/types/script";
import { executeCueSafely, normalizeCuePoints } from "@/features/show/cuePlayback";

function dramaturgToDialogueSpeaker(speaker: DramaturgSpeaker): "AI_A" | "AI_B" {
  return speaker === "anthropic" ? "AI_B" : "AI_A";
}

function decisionSignature(decision: DramaturgyDecision): string {
  return JSON.stringify({
    visual: decision.visual ?? null,
    sound: decision.sound ?? null,
    light: decision.light ?? null,
    cue_points: normalizeCuePoints(decision)
  });
}

function hasExecutableCues(decision: DramaturgyDecision): boolean {
  if (decision.visual || decision.sound || decision.light) return true;
  return normalizeCuePoints(decision).some(
    (point) => point.visual || point.sound || point.light
  );
}

export async function resolveDiscussionDecision(
  turn: DiscussionTurn,
  beatText: string,
  topic: string
): Promise<DramaturgyDecision | null> {
  if (turn.proposed_decision && hasExecutableCues(turn.proposed_decision)) {
    return turn.proposed_decision;
  }

  try {
    const result = await postDirectorDialogueEvent({
      speaker: dramaturgToDialogueSpeaker(turn.speaker),
      text: turn.content,
      topic: topic || beatText.slice(0, 200)
    });
    if (hasExecutableCues(result.decision)) return result.decision;
  } catch {
    /* director unavailable or plan failed */
  }
  return null;
}

export type DiscussionCueContext = {
  lastSignature: string | null;
  onCommands: (commands: OscCommand[]) => Promise<void>;
  shouldAbort: () => boolean;
};

export function createDiscussionCueContext(
  onCommands: (commands: OscCommand[]) => Promise<void>,
  shouldAbort: () => boolean
): DiscussionCueContext {
  return { lastSignature: null, onCommands, shouldAbort };
}

export function scheduleDiscussionCue(
  ctx: DiscussionCueContext,
  turn: DiscussionTurn,
  beatText: string,
  topic: string
): void {
  if (turn.proposed_decision && hasExecutableCues(turn.proposed_decision)) {
    void executeDiscussionCue(ctx, turn.proposed_decision);
    return;
  }
  void resolveDiscussionDecision(turn, beatText, topic).then((decision) => {
    if (decision) void executeDiscussionCue(ctx, decision);
  });
}

export async function executeDiscussionCue(
  ctx: DiscussionCueContext,
  decision: DramaturgyDecision
): Promise<boolean> {
  if (ctx.shouldAbort() || !hasExecutableCues(decision)) return false;

  const signature = decisionSignature(decision);
  if (signature === ctx.lastSignature) return false;
  ctx.lastSignature = signature;

  return executeCueSafely(decision, ctx.onCommands, ctx.shouldAbort);
}
