"use client";

import { useEffect, useState } from "react";

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

  useEffect(() => {
    setTryout(readPerformanceTryout());
  }, []);

  return (
    <label className="performanceTryout" style={{ fontSize: "0.85rem" }}>
      <input
        type="checkbox"
        checked={tryout}
        disabled={disabled}
        onChange={(e) => {
          const next = e.target.checked;
          setTryout(next);
          writePerformanceTryout(next);
        }}
      />
      <span>Probebetrieb (OSC-Log, kein Licht)</span>
    </label>
  );
}
