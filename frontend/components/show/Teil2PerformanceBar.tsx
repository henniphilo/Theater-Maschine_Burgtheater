"use client";

import { PlaybackSpeedControl } from "@/components/show/PlaybackSpeedControl";
import { PerformanceTryoutControl } from "@/components/show/PerformanceTryoutControl";

type Teil2PerformanceBarProps = {
  positionLabel: string;
  detail: string;
  running: boolean;
  paused: boolean;
  canPlay: boolean;
  onPlay: () => void;
  onPause: () => void;
  onStop: () => void;
};

export function Teil2PerformanceBar({
  positionLabel,
  detail,
  running,
  paused,
  canPlay,
  onPlay,
  onPause,
  onStop
}: Teil2PerformanceBarProps) {
  const showPause = running && !paused;
  const showPlay = !running || paused;
  const stopEnabled = running || paused;

  return (
    <footer className="performanceTransport" aria-label="Teil-2-Steuerung">
      <div className="performanceTransportInner performanceTransportInnerCompact">
        <div className="performanceTransportPlayGroup">
          {showPlay ? (
            <button
              type="button"
              className="machineStartBtn"
              disabled={!canPlay}
              onClick={onPlay}
              aria-label={paused ? "Fortsetzen" : "Abspielen"}
            >
              {paused ? "▶ Fortsetzen" : "▶ Play"}
            </button>
          ) : null}
          {showPause ? (
            <button type="button" disabled={!canPlay} onClick={onPause} aria-label="Pause">
              ⏸
            </button>
          ) : null}
          <button
            type="button"
            className="machineStopBtn"
            onClick={onStop}
            disabled={!stopEnabled}
            aria-label="Stoppen"
          >
            ⏹ Stop
          </button>
        </div>
        <div className="performanceTransportMeta">
          <strong>{positionLabel}</strong>
          <span className="textMuted performanceTransportDetail">{detail}</span>
        </div>
        <div className="performanceTransportRight">
          <PerformanceTryoutControl disabled={running && !paused} />
          <PlaybackSpeedControl compact disabled={running && !paused} />
        </div>
      </div>
    </footer>
  );
}
