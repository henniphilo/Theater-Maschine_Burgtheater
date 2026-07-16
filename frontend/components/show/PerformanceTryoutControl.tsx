"use client";

import { useEffect, useState } from "react";

import { syncPerformanceTryoutToDirector } from "@/lib/api/director";
import {
  noteDesiredPerformanceTryout,
  readPerformanceTryout,
  writePerformanceTryout
} from "@/lib/performanceTryout";

export { readPerformanceTryout, writePerformanceTryout } from "@/lib/performanceTryout";

type PerformanceTryoutControlProps = {
  disabled?: boolean;
};

export function PerformanceTryoutControl({ disabled }: PerformanceTryoutControlProps) {
  const [tryout, setTryout] = useState(false);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    const initial = readPerformanceTryout();
    setTryout(initial);
    noteDesiredPerformanceTryout(initial);
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
