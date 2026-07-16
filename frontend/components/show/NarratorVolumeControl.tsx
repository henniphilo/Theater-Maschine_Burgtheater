"use client";

import { useEffect, useState } from "react";

import {
  getNarratorVolume,
  isNarratorMuted,
  onNarratorVolumeChange,
  setNarratorMuted,
  setNarratorVolume
} from "@/lib/api/client";

type NarratorVolumeControlProps = {
  disabled?: boolean;
};

export function NarratorVolumeControl({ disabled }: NarratorVolumeControlProps) {
  const [volume, setVolume] = useState(1);
  const [muted, setMuted] = useState(false);

  useEffect(() => {
    setVolume(getNarratorVolume());
    setMuted(isNarratorMuted());
    return onNarratorVolumeChange((nextVolume, nextMuted) => {
      setVolume(nextVolume);
      setMuted(nextMuted);
    });
  }, []);

  return (
    <div className="narratorVolume">
      <button
        type="button"
        className={muted || volume === 0 ? "narratorMuteBtn narratorMuteBtnActive" : "narratorMuteBtn"}
        disabled={disabled}
        aria-pressed={muted}
        aria-label={muted ? "Erzählerton einschalten" : "Erzählerton stummschalten"}
        onClick={() => setNarratorMuted(!muted)}
      >
        {muted || volume === 0 ? "Stumm" : "Ton"}
      </button>
      <label className="narratorVolumeSlider">
        <span className="textMuted">Lautstärke</span>
        <input
          type="range"
          min={0}
          max={100}
          step={1}
          value={Math.round(volume * 100)}
          disabled={disabled || muted}
          aria-label="Erzähler-Lautstärke"
          onChange={(e) => {
            const next = Number(e.target.value) / 100;
            setVolume(next);
            setNarratorVolume(next);
            if (muted && next > 0) setNarratorMuted(false);
          }}
        />
        <span className="narratorVolumeValue">{Math.round(volume * 100)}%</span>
      </label>
    </div>
  );
}
