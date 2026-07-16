import { sessionGet, sessionSet } from "@/lib/browser/session";

const STORAGE_KEY = "teil2PerformanceTryout";

/** Latest desired Probebetrieb value — used to reconcile in-flight safety patches. */
let latestDesiredTryout: boolean | null = null;

export function readPerformanceTryout(): boolean {
  if (typeof window === "undefined") return false;
  return sessionGet(STORAGE_KEY) === "1";
}

export function writePerformanceTryout(enabled: boolean): void {
  if (typeof window === "undefined") return;
  latestDesiredTryout = enabled;
  sessionSet(STORAGE_KEY, enabled ? "1" : "0");
}

export function peekDesiredPerformanceTryout(): boolean {
  if (latestDesiredTryout != null) return latestDesiredTryout;
  return readPerformanceTryout();
}

export function noteDesiredPerformanceTryout(enabled: boolean): void {
  latestDesiredTryout = enabled;
}
