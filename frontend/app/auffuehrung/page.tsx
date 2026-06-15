"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { AppNav } from "@/components/layout/AppNav";
import { ScriptBeatBlock } from "@/components/script/ScriptBeatBlock";
import { MachineStage } from "@/components/show/MachineStage";
import { StagePreview } from "@/components/stage/StagePreview";
import { fetchTTSStatus } from "@/lib/api/client";
import { fetchMediaCatalog } from "@/lib/api/media";
import { downloadBlob, exportPerformance, importPerformance } from "@/lib/api/performance";
import { fetchScript } from "@/lib/api/script";
import {
  INITIAL_PLAYBACK_STATE,
  prefetchBeatStart,
  runScriptPlayback,
  stopScriptPlayback,
  type PlaybackAudioOptions,
  type PlaybackState
} from "@/features/show/scriptPlayback";
import { buildMediaLookup, type MediaCatalog, type MediaLookup } from "@/lib/types/media";
import type { ProductionScript } from "@/lib/types/script";
import type { DirectorPayload } from "@/lib/types/director";

function AuffuehrungContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const scriptId = searchParams.get("id") ?? sessionStorage.getItem("currentScriptId") ?? "";
  const importInputRef = useRef<HTMLInputElement>(null);
  const [script, setScript] = useState<ProductionScript | null>(null);
  const [playback, setPlayback] = useState<PlaybackState>(INITIAL_PLAYBACK_STATE);
  const [mediaCatalog, setMediaCatalog] = useState<MediaCatalog | null>(null);
  const [media, setMedia] = useState<MediaLookup | undefined>();
  const [ttsAvailable, setTtsAvailable] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const abortRef = useRef(false);
  const playbackGenRef = useRef(0);

  const load = useCallback(async () => {
    if (!scriptId) {
      setLoading(false);
      return;
    }
    try {
      const data = await fetchScript(scriptId);
      setScript(data);
      sessionStorage.setItem("currentScriptId", data.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Stück nicht gefunden");
    } finally {
      setLoading(false);
    }
  }, [scriptId]);

  useEffect(() => {
    void load();
    fetchTTSStatus()
      .then((s) => setTtsAvailable(s.available))
      .catch(() => undefined);
    fetchMediaCatalog()
      .then((catalog) => {
        setMediaCatalog(catalog);
        setMedia(buildMediaLookup(catalog));
      })
      .catch(() => undefined);
  }, [load]);

  const ready = script?.status === "ready";
  const canPlay = ready || Boolean(script?.has_rendered_audio);

  const playbackAudio: PlaybackAudioOptions = useMemo(
    () => ({
      ttsAvailable,
      scriptId: script?.id,
      hasRenderedAudio: Boolean(script?.has_rendered_audio)
    }),
    [ttsAvailable, script?.id, script?.has_rendered_audio]
  );

  useEffect(() => {
    if (!script || !canPlay) return;
    const beat = script.beats[playback.beatIndex];
    if (beat) prefetchBeatStart(beat, playbackAudio);
  }, [script, canPlay, playback.beatIndex, playbackAudio]);

  const currentBeat = playback.beatIndex >= 0 ? script?.beats[playback.beatIndex] : undefined;
  const canResume = playback.paused && !playback.completed && playback.beatIndex >= 0;
  const inDiscussion = playback.segmentPhase === "discussion";
  const discussionTurn =
    inDiscussion && currentBeat?.discussion_turns && playback.discussionTurnIndex !== undefined
      ? currentBeat.discussion_turns[playback.discussionTurnIndex]
      : undefined;

  const directorPayload: DirectorPayload | undefined =
    currentBeat?.dramaturgy && !inDiscussion
      ? {
          event: {},
          decision: currentBeat.dramaturgy,
          executed: playback.showPhase === "sent",
          blocked_reason: null,
          planned_commands: currentBeat.planned_commands,
          osc_commands: []
        }
      : undefined;

  const playFrom = useCallback(
    async (startIndex: number) => {
      if (!script || !canPlay) return;
      const gen = ++playbackGenRef.current;
      setError("");
      abortRef.current = false;
      setPlayback((prev) => ({ ...prev, beatIndex: startIndex, paused: false, completed: false }));

      await runScriptPlayback(
        script.beats,
        playbackAudio,
        startIndex,
        (update) => {
          if (gen === playbackGenRef.current) {
            setPlayback((prev) => ({ ...prev, ...update }));
          }
        },
        () => abortRef.current
      );
    },
    [script, canPlay, playbackAudio]
  );

  function handleStart() {
    const from = canResume ? playback.beatIndex : playback.beatIndex >= 0 ? playback.beatIndex : 0;
    if (script) {
      const beat = script.beats[from];
      if (beat) prefetchBeatStart(beat, playbackAudio);
    }
    void playFrom(from);
  }

  function handleStop() {
    abortRef.current = true;
    playbackGenRef.current += 1;
    stopScriptPlayback();
    setPlayback((prev) => ({
      ...prev,
      running: false,
      paused: true,
      activeOscBridge: null,
      activeOscCommand: null
    }));
  }

  function handleJumpToBeat(index: number) {
    if (!script || index < 0 || index >= script.beats.length) return;
    prefetchBeatStart(script.beats[index], playbackAudio);
    setPlayback((prev) => ({ ...prev, beatIndex: index, paused: true, completed: false }));

    if (playback.running) {
      abortRef.current = true;
      playbackGenRef.current += 1;
      stopScriptPlayback();
      void playFrom(index);
    }
  }

  async function handleExport() {
    if (!script || !ready) return;
    setExporting(true);
    setError("");
    try {
      const { blob, filename } = await exportPerformance(script.id);
      downloadBlob(blob, filename);
      const updated = await fetchScript(script.id);
      setScript(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export fehlgeschlagen");
    } finally {
      setExporting(false);
    }
  }

  async function handleImportFile(file: File | null) {
    if (!file) return;
    setImporting(true);
    setError("");
    try {
      const imported = (await importPerformance(file)) as ProductionScript;
      sessionStorage.setItem("currentScriptId", imported.id);
      router.push(`/auffuehrung?id=${imported.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import fehlgeschlagen");
    } finally {
      setImporting(false);
      if (importInputRef.current) importInputRef.current.value = "";
    }
  }

  return (
    <main className="container col">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0 }}>Aufführung</h1>
        <AppNav />
      </div>
      <p className="textMuted">
        Pro Abschnitt: Dramaturgen-Gespräch, dann Stücktext mit Cues. Aufführung als{" "}
        <code>.tmshow.zip</code> exportieren (Text, Stimmen, Cues) und später ohne Dramaturgie importieren.
      </p>

      <section className="card col">
        <h2>Aufführung laden / speichern</h2>
        <p className="textMuted" style={{ fontSize: "0.9rem" }}>
          Import: ZIP mit Stücktext, Regie-Cues und vorgerenderten Stimmen. Export: rendert alle Stimmen und lädt
          ein portables Paket herunter.
        </p>
        <div className="row">
          <button
            type="button"
            onClick={() => importInputRef.current?.click()}
            disabled={importing}
          >
            {importing ? "Import läuft …" : "Aufführung importieren (.zip)"}
          </button>
          <input
            ref={importInputRef}
            type="file"
            accept=".zip,application/zip"
            hidden
            onChange={(e) => void handleImportFile(e.target.files?.[0] ?? null)}
          />
          {script && ready ? (
            <button type="button" onClick={() => void handleExport()} disabled={exporting || playback.running}>
              {exporting ? "Export rendert Stimmen …" : "Aufführung exportieren"}
            </button>
          ) : null}
        </div>
        {script?.has_rendered_audio ? (
          <p className="textMuted" style={{ fontSize: "0.85rem" }}>
            Vorgespeicherte Stimmen aktiv — Wiedergabe ohne Live-TTS.
          </p>
        ) : null}
      </section>

      {loading ? <p className="textFaint">Lade Stück …</p> : null}
      {error ? <div className="textError" role="alert">{error}</div> : null}
      {!scriptId && !loading ? (
        <p className="textFaint">
          Kein Stück geladen — oben importieren oder <Link href="/dramaturgie">Dramaturgie</Link> starten.
        </p>
      ) : null}

      {script ? (
        <>
          <section className="card col">
            <h2>{script.title}</h2>
            {mediaCatalog ? (
              <p className="textMuted" style={{ fontSize: "0.85rem" }}>
                Medien-Datenbank: <code>{mediaCatalog.data_dir}/media.json</code> · TouchDesigner OSC{" "}
                <code>
                  {mediaCatalog.touchdesigner.osc_host}:{mediaCatalog.touchdesigner.osc_port}
                </code>
                {mediaCatalog.touchdesigner.osc_dry_run ? " (DRY-RUN)" : ""}
              </p>
            ) : null}
            <StagePreview
              beats={script.beats}
              activeBeatIndex={playback.beatIndex}
              activeOscBridge={playback.activeOscBridge}
              segmentPhase={playback.segmentPhase}
              running={playback.running}
              paused={playback.paused}
              onBeatSelect={canPlay ? handleJumpToBeat : undefined}
              media={media}
            />
            <div className="row">
              <button
                type="button"
                className="machineStartBtn"
                onClick={handleStart}
                disabled={!canPlay || playback.running}
              >
                {playback.running
                  ? "Läuft …"
                  : canResume
                    ? `Fortsetzen ab Abschnitt ${playback.beatIndex + 1}`
                    : playback.beatIndex > 0
                      ? `Starten ab Abschnitt ${playback.beatIndex + 1}`
                      : "Maschine starten"}
              </button>
              {playback.running || playback.paused ? (
                <button type="button" className="machineStopBtn" onClick={handleStop} disabled={!playback.running}>
                  Stoppen
                </button>
              ) : null}
            </div>
            {!canPlay ? (
              <p className="textFaint">
                Stück noch nicht bereit — Dramaturgie abschließen oder gespeicherte Aufführung importieren.
              </p>
            ) : null}
            {playback.completed ? (
              <p className="textMuted">Aufführung beendet. Erneut starten oder Abschnitt wählen.</p>
            ) : null}
          </section>

          <MachineStage
            running={playback.running}
            beatIndex={Math.max(playback.beatIndex, 0)}
            beatTotal={script.beats.length}
            segmentPhase={playback.segmentPhase}
            discussionTurnIndex={playback.discussionTurnIndex}
            discussionText={discussionTurn?.content}
            dramaturgSpeaker={playback.dramaturgSpeaker}
            performanceSpeaker={playback.performanceSpeaker}
            director={directorPayload}
            showPhase={playback.showPhase}
            activeOscBridge={playback.activeOscBridge}
            activeOscCommand={playback.activeOscCommand}
            onStop={handleStop}
          />

          <section className="card col scriptDocument">
            <h2>Stücktext (klickbar)</h2>
            <p className="textMuted" style={{ fontSize: "0.9rem" }}>
              Klick startet ab Dramaturgen-Gespräch des Abschnitts
              {playback.running ? " und setzt die Wiedergabe fort" : ""}.
            </p>
            {script.beats.map((beat, index) => (
              <ScriptBeatBlock
                key={beat.id}
                beat={beat}
                media={media}
                highlight={index === playback.beatIndex && (playback.running || playback.paused)}
                segmentPhase={index === playback.beatIndex ? playback.segmentPhase : undefined}
                discussionTurnIndex={
                  index === playback.beatIndex ? playback.discussionTurnIndex : undefined
                }
                sentenceIndex={index === playback.beatIndex ? playback.sentenceIndex : undefined}
                clickable={canPlay}
                onSelect={() => handleJumpToBeat(index)}
              />
            ))}
          </section>
        </>
      ) : null}
    </main>
  );
}

export default function AuffuehrungPage() {
  return (
    <Suspense fallback={<main className="container"><p className="textFaint">Lade …</p></main>}>
      <AuffuehrungContent />
    </Suspense>
  );
}
