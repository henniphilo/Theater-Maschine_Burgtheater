"use client";

import { PlaybackSpeedControl } from "@/components/show/PlaybackSpeedControl";
import { PerformanceTryoutControl } from "@/components/show/PerformanceTryoutControl";

type Teil2PerformanceBarProps = {
  positionLabel: string;
  detail: string;
  running: boolean;
  paused: boolean;
  canPlay: boolean;
  currentIndex?: number | null;
  totalCount?: number;
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
  currentIndex,
  totalCount,
  onPlay,
  onPause,
  onStop
}: Teil2PerformanceBarProps) {
  const showPause = running && !paused;
  const showPlay = !running || paused;
  const stopEnabled = running || paused;
  const showCounter = typeof totalCount === "number" && totalCount > 0;
  const displayIndex =
    currentIndex != null && currentIndex > 0 ? String(currentIndex) : "—";

  return (
    <footer className="performanceTransport" aria-label="Teil-2-Steuerung">
      <div className="performanceTransportInner performanceTransportInnerCompact">
        <div className="performanceTransportPlayGroup">
          {showPlay ? (
            <button
              type="button"
              className="machineStartBtn transportBtn transportBtnPlay"
              disabled={!canPlay}
              onClick={onPlay}
              aria-label={paused ? "Fortsetzen" : "Abspielen"}
            >
              ▶
            </button>
          ) : null}
          {showPause ? (
            <button
              type="button"
              className="transportBtn transportBtnPause"
              disabled={!canPlay}
              onClick={onPause}
              aria-label="Pause"
            >
              ⏸
            </button>
          ) : null}
          <button
            type="button"
            className="machineStopBtn transportBtn transportBtnStop"
            onClick={onStop}
            disabled={!stopEnabled}
            aria-label="Stoppen"
          >
            ⏹
          </button>
        </div>
        <div className="liveTransportCounter performanceTransportMeta">
          {showCounter ? (
            <strong className="liveTransportCounterValue" aria-label={positionLabel}>
              {displayIndex} <span>/ {totalCount}</span>
            </strong>
          ) : (
            <strong>{positionLabel}</strong>
          )}
          <span className="textMuted performanceTransportDetail">{detail}</span>
        </div>
        <div className="performanceTransportRight">
          <PerformanceTryoutControl />
          <PlaybackSpeedControl compact disabled={running && !paused} />
        </div>
      </div>
    </footer>
  );
}
