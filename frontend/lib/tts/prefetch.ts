import { fetchSpeechBlob } from "@/lib/api/client";

type TtsSpeaker = "openai" | "anthropic" | "AI_A" | "AI_B" | "narrator";

function cacheKey(text: string, speaker: TtsSpeaker): string {
  return `${speaker}\0${text}`;
}

const blobCache = new Map<string, Promise<Blob>>();

export function prefetchSpeech(text: string, speaker: TtsSpeaker): Promise<Blob> {
  const key = cacheKey(text, speaker);
  let pending = blobCache.get(key);
  if (!pending) {
    pending = fetchSpeechBlob(text, speaker).catch((err) => {
      blobCache.delete(key);
      throw err;
    });
    blobCache.set(key, pending);
  }
  return pending;
}

export function getCachedSpeech(text: string, speaker: TtsSpeaker): Promise<Blob> {
  return prefetchSpeech(text, speaker);
}

export function clearSpeechCache(): void {
  blobCache.clear();
}
