import { getCachedSpeech, prefetchSpeech } from "@/lib/tts/prefetch";
import { performanceAudioUrl, prefetchPrerenderedSpeech } from "@/lib/api/performance";
import { playBlob, stopPlayback } from "@/lib/api/client";
import { sentenceIndexForProgress } from "@/lib/text/splitSentences";
import { speakerForPerformanceSentence } from "@/lib/show/performanceVoices";
import type { OscCommand, ShowPhase } from "@/lib/types/director";
import type { DiscussionTurn, DramaturgSpeaker, ScriptBeat, ScriptSpeaker } from "@/lib/types/script";
import {
  createCuePlaybackContext,
  fireSentenceCues,
  fireStartCues,
  fireTimeCues,
  sentencesForBeat
} from "@/features/show/cuePlayback";

const OSC_HIGHLIGHT_MS = 150;
const DISCUSSION_FALLBACK_MS = 1500;

export type SegmentPhase = "discussion" | "performance";

export type PlaybackAudioOptions = {
  ttsAvailable: boolean;
  scriptId?: string;
  hasRenderedAudio?: boolean;
};

export type PlaybackState = {
  running: boolean;
  paused: boolean;
  beatIndex: number;
  sentenceIndex: number;
  activeOscBridge: string | null;
  activeOscCommand: OscCommand | null;
  segmentPhase?: SegmentPhase;
  discussionTurnIndex?: number;
  dramaturgSpeaker?: DramaturgSpeaker;
  performanceSpeaker?: ScriptSpeaker;
  showPhase?: ShowPhase;
  completed: boolean;
};

export const INITIAL_PLAYBACK_STATE: PlaybackState = {
  running: false,
  paused: false,
  beatIndex: 0,
  sentenceIndex: 0,
  activeOscBridge: null,
  activeOscCommand: null,
  completed: false
};

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function audioReady(options: PlaybackAudioOptions): boolean {
  return Boolean(options.hasRenderedAudio || options.ttsAvailable);
}

async function resolveDiscussionSpeechBlob(
  options: PlaybackAudioOptions,
  beatId: string,
  turnIndex: number,
  text: string,
  speaker: DramaturgSpeaker
): Promise<Blob> {
  if (options.hasRenderedAudio && options.scriptId) {
    return prefetchPrerenderedSpeech(
      performanceAudioUrl(options.scriptId, beatId, "discussion", turnIndex)
    );
  }
  return getCachedSpeech(text, speaker);
}

async function resolvePerformanceSpeechBlob(
  options: PlaybackAudioOptions,
  beatId: string,
  sentenceIndex: number,
  sentenceText: string,
  speaker: ScriptSpeaker,
  useLegacyWholeBeat: boolean
): Promise<Blob> {
  if (options.hasRenderedAudio && options.scriptId) {
    if (useLegacyWholeBeat) {
      return prefetchPrerenderedSpeech(
        performanceAudioUrl(options.scriptId, beatId, "performance")
      );
    }
    try {
      return await prefetchPrerenderedSpeech(
        performanceAudioUrl(options.scriptId, beatId, "performance", undefined, sentenceIndex)
      );
    } catch {
      if (sentenceIndex === 0) {
        return prefetchPrerenderedSpeech(
          performanceAudioUrl(options.scriptId, beatId, "performance")
        );
      }
      throw new Error("Vorgespeicherte Satz-Audio-Datei nicht gefunden");
    }
  }
  return getCachedSpeech(sentenceText, speaker);
}

function prefetchDiscussionTurn(
  options: PlaybackAudioOptions,
  beatId: string,
  turn: DiscussionTurn,
  turnIndex: number
): void {
  if (options.hasRenderedAudio && options.scriptId) {
    void prefetchPrerenderedSpeech(
      performanceAudioUrl(options.scriptId, beatId, "discussion", turnIndex)
    );
    return;
  }
  if (options.ttsAvailable) prefetchSpeech(turn.content, turn.speaker);
}

function prefetchPerformanceSentences(
  options: PlaybackAudioOptions,
  beat: ScriptBeat,
  beatIndex: number
): void {
  const sentences = sentencesForBeat(beat.text);
  if (sentences.length === 0) return;

  if (options.hasRenderedAudio && options.scriptId) {
    for (let i = 0; i < sentences.length; i++) {
      void prefetchPrerenderedSpeech(
        performanceAudioUrl(options.scriptId, beat.id, "performance", undefined, i)
      ).catch(() => {
        if (i === 0) {
          void prefetchPrerenderedSpeech(
            performanceAudioUrl(options.scriptId!, beat.id, "performance")
          );
        }
      });
    }
    return;
  }

  if (!options.ttsAvailable) return;
  for (let i = 0; i < sentences.length; i++) {
    const speaker = speakerForPerformanceSentence(beat.speaker, i, beat.order);
    prefetchSpeech(sentences[i], speaker);
  }
}

async function highlightOscSequence(
  commands: OscCommand[],
  onHighlight: (cmd: OscCommand | null, bridge: string | null) => void,
  shouldAbort: () => boolean
) {
  for (const cmd of commands) {
    if (shouldAbort()) break;
    onHighlight(cmd, cmd.bridge);
    await sleep(OSC_HIGHLIGHT_MS);
  }
  onHighlight(null, null);
}

async function playDiscussionPhase(
  turns: DiscussionTurn[],
  beat: ScriptBeat,
  beatIndex: number,
  options: PlaybackAudioOptions,
  onState: (state: Partial<PlaybackState>) => void,
  shouldAbort: () => boolean
): Promise<boolean> {
  if (turns.length === 0) return true;

  prefetchDiscussionTurn(options, beat.id, turns[0], 0);
  if (turns.length > 1) prefetchDiscussionTurn(options, beat.id, turns[1], 1);
  prefetchPerformanceSentences(options, beat, beatIndex);

  onState({
    beatIndex,
    sentenceIndex: 0,
    segmentPhase: "discussion",
    showPhase: "dramaturg_discussion",
    performanceSpeaker: undefined,
    activeOscBridge: null,
    activeOscCommand: null,
    paused: false
  });

  for (let turnIndex = 0; turnIndex < turns.length; turnIndex++) {
    if (shouldAbort()) return false;
    const turn = turns[turnIndex];
    const next = turns[turnIndex + 1];
    if (next) prefetchDiscussionTurn(options, beat.id, next, turnIndex + 1);

    onState({
      discussionTurnIndex: turnIndex,
      dramaturgSpeaker: turn.speaker
    });

    if (!audioReady(options)) {
      await sleep(DISCUSSION_FALLBACK_MS);
      continue;
    }

    try {
      const blob = await resolveDiscussionSpeechBlob(
        options,
        beat.id,
        turnIndex,
        turn.content,
        turn.speaker
      );
      if (shouldAbort()) return false;
      await playBlob(blob);
    } catch {
      if (!shouldAbort()) onState({ showPhase: "blocked" });
      return false;
    }
  }

  return !shouldAbort();
}

async function hasPerSentencePrerender(scriptId: string, beatId: string): Promise<boolean> {
  const url = performanceAudioUrl(scriptId, beatId, "performance", undefined, 0);
  const res = await fetch(url, { method: "HEAD" });
  return res.ok;
}

async function playLegacyPerformanceBlob(
  beat: ScriptBeat,
  beatIndex: number,
  sentences: string[],
  options: PlaybackAudioOptions,
  cueCtx: ReturnType<typeof createCuePlaybackContext>,
  onState: (state: Partial<PlaybackState>) => void,
  shouldAbort: () => boolean
): Promise<boolean> {
  let lastSentenceIndex = -1;
  onState({ showPhase: "speaking", performanceSpeaker: beat.speaker });

  try {
    const blob = await resolvePerformanceSpeechBlob(
      options,
      beat.id,
      0,
      beat.text,
      beat.speaker,
      true
    );
    if (shouldAbort()) return false;

    let cuesStarted = false;
    await playBlob(blob, {
      onPlay: () => {
        if (cuesStarted) return;
        cuesStarted = true;
        onState({ showPhase: "cues_active" });
        void fireStartCues(cueCtx).then(() => {
          if (!shouldAbort()) onState({ showPhase: "sent" });
        });
      },
      onTimeUpdate: (current, duration) => {
        if (shouldAbort()) return;
        const sentenceIndex = sentenceIndexForProgress(current, duration, sentences.length);
        onState({ sentenceIndex });
        void fireTimeCues(cueCtx, current);
        if (sentenceIndex !== lastSentenceIndex) {
          lastSentenceIndex = sentenceIndex;
          void fireSentenceCues(cueCtx, sentenceIndex, sentences[sentenceIndex] ?? "");
        }
      }
    });

    if (!cuesStarted) {
      onState({ showPhase: "cues_active" });
      await fireStartCues(cueCtx);
      for (let i = 0; i < sentences.length; i++) {
        await fireSentenceCues(cueCtx, i, sentences[i]);
      }
    }
    return !shouldAbort();
  } catch {
    if (!shouldAbort()) onState({ showPhase: "blocked" });
    return false;
  }
}

async function playPerformancePhase(
  beat: ScriptBeat,
  beatIndex: number,
  options: PlaybackAudioOptions,
  onState: (state: Partial<PlaybackState>) => void,
  shouldAbort: () => boolean
): Promise<boolean> {
  onState({
    beatIndex,
    sentenceIndex: 0,
    segmentPhase: "performance",
    discussionTurnIndex: undefined,
    dramaturgSpeaker: undefined,
    performanceSpeaker: undefined,
    showPhase: "planned",
    activeOscBridge: null,
    activeOscCommand: null,
    paused: false
  });

  const sentences = sentencesForBeat(beat.text);
  if (sentences.length === 0) return !shouldAbort();

  const cueCtx = createCuePlaybackContext(
    beat.dramaturgy!,
    beat.text,
    async (commands) => {
      await highlightOscSequence(
        commands,
        (cmd, bridge) => onState({ activeOscCommand: cmd, activeOscBridge: bridge }),
        shouldAbort
      );
    },
    shouldAbort
  );

  if (!audioReady(options)) {
    onState({ showPhase: "cues_active" });
    await fireStartCues(cueCtx);
    for (let i = 0; i < sentences.length; i++) {
      if (shouldAbort()) return false;
      const speaker = speakerForPerformanceSentence(beat.speaker, i, beat.order);
      onState({ sentenceIndex: i, performanceSpeaker: speaker });
      await fireSentenceCues(cueCtx, i, sentences[i]);
      await sleep(800);
    }
    onState({ showPhase: "sent" });
    return !shouldAbort();
  }

  if (options.hasRenderedAudio && options.scriptId) {
    const perSentence = await hasPerSentencePrerender(options.scriptId, beat.id);
    if (!perSentence) {
      return playLegacyPerformanceBlob(
        beat,
        beatIndex,
        sentences,
        options,
        cueCtx,
        onState,
        shouldAbort
      );
    }
  }

  onState({ showPhase: "speaking" });
  let cumulativeTime = 0;
  let cuesStarted = false;

  for (let i = 0; i < sentences.length; i++) {
    if (shouldAbort()) return false;
    const sentence = sentences[i];
    const speaker = speakerForPerformanceSentence(beat.speaker, i, beat.order);

    onState({ sentenceIndex: i, performanceSpeaker: speaker });

    if (i === 0) {
      onState({ showPhase: "cues_active" });
      await fireStartCues(cueCtx);
      cuesStarted = true;
    }
    await fireSentenceCues(cueCtx, i, sentence);

    const nextSentence = sentences[i + 1];
    if (nextSentence) {
      const nextSpeaker = speakerForPerformanceSentence(beat.speaker, i + 1, beat.order);
      if (options.ttsAvailable) prefetchSpeech(nextSentence, nextSpeaker);
    }

    try {
      const blob = await resolvePerformanceSpeechBlob(
        options,
        beat.id,
        i,
        sentence,
        speaker,
        false
      );
      if (shouldAbort()) return false;

      let lastDuration = 0;
      const sentenceStart = cumulativeTime;
      await playBlob(blob, {
        onTimeUpdate: (current, duration) => {
          if (Number.isFinite(duration)) lastDuration = duration;
          void fireTimeCues(cueCtx, sentenceStart + current);
        }
      });
      cumulativeTime += Number.isFinite(lastDuration) ? lastDuration : 0;
    } catch {
      if (!shouldAbort()) onState({ showPhase: "blocked" });
      return false;
    }
  }

  if (cuesStarted && !shouldAbort()) onState({ showPhase: "sent" });
  return !shouldAbort();
}

async function playBeat(
  beat: ScriptBeat,
  beatIndex: number,
  beats: ScriptBeat[],
  options: PlaybackAudioOptions,
  onState: (state: Partial<PlaybackState>) => void,
  shouldAbort: () => boolean
): Promise<boolean> {
  if (!beat.dramaturgy) return true;

  const nextBeat = beats[beatIndex + 1];
  if (nextBeat) prefetchBeatStart(nextBeat, options, beatIndex + 1);

  const turns = beat.discussion_turns ?? [];
  if (turns.length > 0) {
    const discussionOk = await playDiscussionPhase(
      turns,
      beat,
      beatIndex,
      options,
      onState,
      shouldAbort
    );
    if (!discussionOk) return false;
  } else {
    prefetchPerformanceSentences(options, beat, beatIndex);
  }

  return playPerformancePhase(beat, beatIndex, options, onState, shouldAbort);
}

export function prefetchBeatStart(
  beat: ScriptBeat,
  options: PlaybackAudioOptions,
  beatIndex = beat.order
): void {
  const turns = beat.discussion_turns ?? [];
  if (turns.length > 0) {
    prefetchDiscussionTurn(options, beat.id, turns[0], 0);
    if (turns.length > 1) prefetchDiscussionTurn(options, beat.id, turns[1], 1);
    prefetchPerformanceSentences(options, beat, beatIndex);
    return;
  }
  prefetchPerformanceSentences(options, beat, beatIndex);
}

export async function runScriptPlayback(
  beats: ScriptBeat[],
  options: PlaybackAudioOptions,
  startBeatIndex: number,
  onState: (state: Partial<PlaybackState>) => void,
  shouldAbort: () => boolean
): Promise<void> {
  const start = Math.max(0, Math.min(startBeatIndex, beats.length - 1));
  onState({
    running: true,
    paused: false,
    completed: false,
    beatIndex: start,
    sentenceIndex: 0,
    segmentPhase: undefined,
    discussionTurnIndex: undefined,
    dramaturgSpeaker: undefined,
    performanceSpeaker: undefined,
    activeOscBridge: null,
    activeOscCommand: null
  });

  for (let index = start; index < beats.length; index++) {
    if (shouldAbort()) {
      onState({
        running: false,
        paused: true,
        beatIndex: index,
        activeOscBridge: null,
        activeOscCommand: null
      });
      return;
    }

    const ok = await playBeat(beats[index], index, beats, options, onState, shouldAbort);
    if (!ok) {
      onState({
        running: false,
        paused: true,
        beatIndex: index,
        activeOscBridge: null,
        activeOscCommand: null
      });
      return;
    }
  }

  onState({
    running: false,
    paused: false,
    completed: true,
    beatIndex: 0,
    segmentPhase: undefined,
    discussionTurnIndex: undefined,
    dramaturgSpeaker: undefined,
    performanceSpeaker: undefined,
    activeOscBridge: null,
    activeOscCommand: null,
    showPhase: undefined
  });
}

export function stopScriptPlayback() {
  stopPlayback();
}
