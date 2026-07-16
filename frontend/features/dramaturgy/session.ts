import type { DirectorPayload } from "@/lib/types/director";
import { sessionGet, sessionSet, sessionRemove } from "@/lib/browser/session";

export const DRAMATURGY_SESSION_KEY = "dramaturgySession";

export type DramaturgyChatLine = {
  id: string;
  speaker: string;
  content: string;
  beatOrder?: number;
  director?: DirectorPayload;
};

export type DramaturgySession = {
  title: string;
  sourceText: string;
  scriptId: string | null;
  chat: DramaturgyChatLine[];
  openaiModel: string;
  anthropicModel: string;
};

export function loadDramaturgySession(): DramaturgySession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionGet(DRAMATURGY_SESSION_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as DramaturgySession;
  } catch {
    return null;
  }
}

export function saveDramaturgySession(session: DramaturgySession): void {
  if (typeof window === "undefined") return;
  sessionSet(DRAMATURGY_SESSION_KEY, JSON.stringify(session));
}

export function clearDramaturgySession(): void {
  if (typeof window === "undefined") return;
  sessionRemove(DRAMATURGY_SESSION_KEY);
}
