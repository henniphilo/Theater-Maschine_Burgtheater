"use client";

import { useEffect, useState } from "react";

import { getPlaybackRate, setPlaybackRate } from "@/lib/api/client";

type PlaybackSpeedControlProps = {
  disabled?: boolean;
  compact?: boolean;
};

export function PlaybackSpeedControl({ disabled, compact }: PlaybackSpeedControlProps) {
  const [rate, setRate] = useState(1);

  useEffect(() => {
    setRate(getPlaybackRate());
  }, []);

  return (
    <label className={compact ? "performanceSpeed performanceSpeedCompact" : "performanceSpeed"}>
      <span className="performanceSpeedLabel">Tempo</span>
      <input
        type="range"
        min={50}
        max={200}
        step={5}
        value={Math.round(rate * 100)}
        disabled={disabled}
        aria-label="Sprechtempo"
        onChange={(e) => {
          const next = Number(e.target.value) / 100;
          setRate(next);
          setPlaybackRate(next);
        }}
      />
      <span className="performanceSpeedValue">{rate.toFixed(1)}×</span>
    </label>
  );
}
