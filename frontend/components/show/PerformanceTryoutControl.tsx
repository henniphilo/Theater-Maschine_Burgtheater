"use client";

import { useEffect, useState } from "react";

import { syncPerformanceTryoutToDirector } from "@/lib/api/director";

const STORAGE_KEY = "teil2PerformanceTryout";

export function readPerformanceTryout(): boolean {
  if (typeof window === "undefined") return false;
  return sessionStorage.getItem(STORAGE_KEY) === "1";
}

export function writePerformanceTryout(enabled: boolean): void {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(STORAGE_KEY, enabled ? "1" : "0");
}

type PerformanceTryoutControlProps = {
  disabled?: boolean;
};

export function PerformanceTryoutControl({ disabled }: PerformanceTryoutControlProps) {
  const [tryout, setTryout] = useState(false);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    const initial = readPerformanceTryout();
    setTryout(initial);
    void syncPerformanceTryoutToDirector(initial).catch((err) => {
      console.warn("Probebetrieb konnte beim Laden nicht synchronisiert werden:", err);
    });
  }, []);

  const applyTryout = async (next: boolean) => {
    setTryout(next);
    writePerformanceTryout(next);
    setSyncing(true);
    try {
      await syncPerformanceTryoutToDirector(next);
    } catch (err) {
      console.warn("Probebetrieb konnte nicht am Director gesetzt werden:", err);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <label className="performanceTryout" style={{ fontSize: "0.85rem" }}>
      <input
        type="checkbox"
        checked={tryout}
        disabled={disabled || syncing}
        onChange={(e) => {
          void applyTryout(e.target.checked);
        }}
      />
      <span>Probebetrieb (OSC-Log, kein Licht)</span>
    </label>
  );
}
