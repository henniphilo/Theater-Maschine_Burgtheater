import type { DramaturgyDecision, OscCommand } from "@/lib/types/director";

export type ScriptSpeaker = "AI_A" | "AI_B" | "narrator";
export type ScriptStatus = "draft" | "review" | "ready";
export type DramaturgSpeaker = "openai" | "anthropic";

export type DiscussionTurn = {
  speaker: DramaturgSpeaker;
  content: string;
  proposed_decision?: DramaturgyDecision | null;
};

export type ScriptBeat = {
  id: string;
  order: number;
  text: string;
  scene_title?: string | null;
  speaker: ScriptSpeaker;
  dramaturgy: DramaturgyDecision | null;
  planned_commands: OscCommand[];
  discussion_turns?: DiscussionTurn[];
  discussion_summary: string | null;
};

export type ProductionScript = {
  id: string;
  title: string;
  source_text: string;
  beats: ScriptBeat[];
  status: ScriptStatus;
  has_rendered_audio?: boolean;
};

export type WorkshopStreamEvent = {
  type:
    | "thinking"
    | "discussion_turn"
    | "dramaturgy_decision"
    | "beat_done"
    | "error"
    | "done"
    | "script_updated";
  beat_id?: string;
  beat_order?: number;
  speaker?: DramaturgSpeaker;
  content?: string;
  dramaturgy?: DramaturgyDecision;
  planned_commands?: OscCommand[];
  discussion_turns?: DiscussionTurn[];
  discussion_summary?: string;
  detail?: string;
  script?: ProductionScript;
};

export function speakerLabel(speaker: ScriptSpeaker): string {
  if (speaker === "AI_A") return "Stimme A";
  if (speaker === "AI_B") return "Stimme B";
  return "Erzähler";
}

export function dramaturgSpeakerLabel(speaker: DramaturgSpeaker): string {
  if (speaker === "openai") return "Dramaturg A (GPT)";
  return "Dramaturg B (Claude)";
}
