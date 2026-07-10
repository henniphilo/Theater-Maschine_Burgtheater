# Debug-Plan: Dropped Signals / Race Conditions

Stand: 2026-07-07 (Review eingearbeitet)

## Plan-Review (streng)

Dieser Abschnitt dokumentiert Review-Findings und wie sie im Plan behoben wurden.
Ein Coding-Agent soll hier zuerst lesen, bevor er implementiert.

### Kritische Findings (behoben)

| # | Problem | Auswirkung | Fix im Plan |
| --- | --- | --- | --- |
| R1 | Event-Namen inkonsistent (`command.enqueued` vs `queue.enqueued` vs `command_built`) | Agent schreibt Events, Analyse findet sie nicht | Einheitliche `domain.action`-Namen + separates `status`-Feld (siehe Konventionen) |
| R2 | Pflicht-Events unvollstaendig (`midi.send_logged`, `api.response_executed` fehlten) | Luecken in Drop-Klassifikation | Vollstaendige Event-Liste mit Phase-Zuordnung |
| R3 | Keine ID-Generierungsregeln | Agent erfindet inkompatible Formate | Abschnitt `ID-Generierung` |
| R4 | `TraceContext` nicht als Struktur definiert | Unklare API-Erweiterungen Frontend/Backend | Abschnitt `TraceContext` mit exakten Feldern und Dateipfaden |
| R5 | Frontend-Trace-Sink unklar (nur Browser-Konsole erwaehnt) | JSONL-Analyse sieht Frontend-Events nicht | Frontend-Events gehen in Ringbuffer + optionaler Export; Backend schreibt `logs/signal_trace.jsonl` |
| R6 | `run_epoch` / `run.barrier_created` in Phase 3 erwartet, aber erst Phase 5 definiert Autoritaet | Falsche Abnahme in Phase 1–3 | Phasen-Tabelle: was in Phase 1 nur geloggt vs. ab Phase 5 erzwungen wird |
| R7 | Invariante „genau eine `logical_signal_id` pro fachlichem Cue“ widerspricht Re-Fires/Duplikaten | Falsche Drop-Alarme | Invariante praezisiert: pro Execute-Request eine ID; Duplikate eigene Klasse |
| R8 | Sync-Send-Pfad (ohne Queue) nicht spezifiziert | Agent loggt nur Queue-Events | Abschnitt `Dispatch-Pfade` |
| R9 | `OscCommand`-Typ an falscher Stelle impliziert (`schemas` statt `cue_models`) | Agent patcht falsche Datei | Explizite Dateipfade fuer Backend + Frontend-Typen |
| R10 | Wichtige Call-Sites fehlten (`showRunner`, `machineRunner`, `armDirectorForPerformance`) | Instrumentierung unvollstaendig | Erweiterte Codebereiche/Messpunkte |
| R11 | Analyse-Script ohne Pfad; `visualize_show_logs.py` nicht referenziert | Agent baut Parallel-Tool | `backend/scripts/analyze_signal_trace.py` + Abgrenzung zu `visualize_show_logs.py` |
| R12 | T08 „definierte Grenzen“ ohne Zahlen | Nicht testbar | Konkrete Schwellen oder explizit „nur relativ, keine Hard-Limits in Phase 1–3“ |
| R13 | `signal_trace_enabled` Default „in dev“ ohne Mechanismus | Agent rät Env-Logik | Default an `app_env == "dev"` und `OSC_DRY_RUN` gekoppelt |
| R14 | `executed` Semantik: Pipeline setzt `executed=allowed and bool(osc_commands)` — geplante/enqueued Commands zaehlen | Falsche Drop-Diagnose | Harte Code-Fakten erweitert |

### Agent-Regeln (verbindlich)

1. Event-Namen und `status`-Werte nie mischen. Events heissen `queue.enqueued`, Status heisst `enqueued`.
2. Kein zusaetzlicher `build_osc_commands`-Aufruf — Metadaten am bestehenden Build-Ergebnis anhaengen.
3. Phase 1: beobachten only. Kein `queue.stale_dropped` erzwingen, nur loggen wenn Epoch-Vergleich moeglich.
4. Phase 5 erst nach gruener Phase-1–4-Abnahme.
5. Tests: Queue-Modus explizit aktivieren (`monkeypatch.setattr(settings, "director_osc_queue", True)`), da `conftest.py` default `False` setzt.
6. `send_osc_batch` haengt Commands auch nach Exception an `sent` — das ist ein bekannter Bug, Phase 1 nur loggen (`command.send_failed` + trotzdem in `osc_commands` Response).

## Ziel

Dieser Plan soll klaeren, wo Signale verloren gehen, doppelt kommen, zu spaet kommen
oder nach Stop/Emergency noch aus alten Kontexten auftauchen:

```text
Frontend Playback
  -> API Request
  -> DirectorPipeline
  -> Command Build
  -> OSC/MIDI/TCP Queue oder Sync Send
  -> Bridge
  -> Empfaenger / Hardware
```

Der Plan ist bewusst phasenweise. Ein Coding-Agent muss jede Phase separat
abarbeiten koennen, ohne spaetere Fixes vorwegzunehmen.

Wichtig: Wir debuggen nicht zuerst "warum fuehlt es sich falsch an", sondern
bauen eine durchgehende Spur. Erst wenn jeder Request, jeder logische Cue und
jeder konkrete Transport-Command eine ID und einen Status hat, werden Fixes
priorisiert.

## Nicht-Ziele

- Keine grosse Architektur-Rewrite-Runde am Anfang.
- Keine gleichzeitigen kosmetischen Refactors.
- Keine Annahme, dass `executed=true` schon "bei der Hardware angekommen"
  bedeutet.
- Keine reine UI-Diagnose, solange Backend-Queue und Hardware-Ausgang nicht
  korreliert sind.
- Keine zusaetzlichen Command-Builds nur fuer Logging. `build_osc_commands`
  darf nicht doppelt aufgerufen werden, weil Light-State bereits beim Build
  mutieren kann.

## Harte Code-Fakten

Diese Punkte sind im aktuellen Code bereits relevant und duerfen im Plan nicht
weichgespuelt werden:

- `frontend/lib/api/director.ts` nutzt ein globales `performanceOscAbort`.
- `stopDirectorPerformance()` bricht Frontend-Fetches ab und feuert
  `postDirectorEmergencyStop()` fire-and-forget.
- `DirectorPipeline._dispatch_commands(... wait=False)` gibt bei aktivem
  Queue-Modus zurueck, bevor Hardware-I/O fertig ist.
- `OscCommandQueue.enqueue(... wait=False)` gibt geplante Commands zurueck,
  nicht sicher gesendete Commands.
- `send_osc_batch` haengt Commands auch nach Exception an `sent`
  (`backend/app/director/outputs/osc_queue.py`, Zeilen 127–136).
- `build_osc_commands` mutiert den globalen Light Scene Tracker
  (`backend/app/director/outputs/light_scene_tracker.py`).
- `DirectorPipeline._dispatch_commands(..., wait=False)` liefert bei Queue-Modus
  die geplanten Commands zurueck, nicht gesendete
  (`backend/app/director/pipeline.py`).
- `executed` in `DirectorResult` ist `allowed and bool(osc_commands)` — bei Queue
  bedeutet das „Dispatch akzeptiert/geplant“, nicht Hardware-Ack.
- `armDirectorForPerformance()` setzt Abort-Controller neu und ruft
  `postDirectorEmergencyClear()` fire-and-forget auf
  (`frontend/lib/api/director.ts`).
- Backend-Tests setzen `settings.director_osc_queue = False` per default
  (`backend/tests/conftest.py`). Queue-Race-Tests muessen den Queue-Modus
  explizit aktivieren. Produktions-Default in `config.py` ist `True`.
- `OscCommand` liegt in `backend/app/director/cues/cue_models.py` (nicht in
  `schemas/director.py`). Frontend-Spiegel: `frontend/lib/types/director.ts`.

## Leit-Hypothese

Die wahrscheinlichsten Ursachen sind eine Mischung aus:

- alte Queue-Batches laufen nach Stop / Emergency weiter;
- Frontend bricht Requests ab, aber bereits akzeptierte Backend-Kommandos
  bleiben aktiv;
- `executed` bedeutet aktuell eher "accepted/planned/enqueued" als
  "physisch gesendet";
- mehrere globale Playback-Zustaende (`currentAudio`, Layered Audio,
  Avatar Timer, Cue-Ketten) koennen nach Abort noch Callbacks feuern;
- UDP/OSC ist best effort und kann ohne Empfaenger-Ack nicht beweisen, dass
  ein Signal angekommen ist;
- Licht/MIDI/Pixera haben unterschiedliche Semantiken fuer "gesendet",
  "angenommen", "ausgefuehrt".

## Signal-Taxonomie

| Signaltyp | Transport | Kritische Stellen | Typische Drop-Symptome |
| --- | --- | --- | --- |
| Video Avatar | Pixera OSC | Text-Sync Position, Avatar Lock, Queue, Pixera Cue Name | Avatar fehlt, falscher Beamer, zu spaet |
| Video Atmosphaere | Pixera/TouchDesigner OSC | layered execute, projector routing, interrupt logic | Atmosphaere bleibt aus oder ueberschreibt Avatar |
| Sound Cue | MIDI oder OSC | active_cues, MIDI map, Ableton/QLab Empfang | Sound startet nicht, Fade fehlt, Cut kommt zu spaet |
| Licht Cue | TCP/OSC EOS | Light scene tracker, TCP session, blackout/replace_previous | Lichtszene bleibt, Blackout fehlt, alte Szene kommt zurueck |
| Stop / Emergency | API + Bridge Calls | Queue cancellation, safety state, pending callbacks | Nach Stop kommen noch Signale |
| UI Highlight | React State | async highlight callbacks, generation guards | UI zeigt Signal, Hardware nicht; oder andersrum |

## Kritische Codebereiche

Frontend:

- Director API / Abort / Arm: `frontend/lib/api/director.ts`
  (`armDirectorForPerformance`, `stopDirectorPerformance`, `postDirectorExecute*`)
- Audio singleton: `frontend/lib/api/client.ts`
- Teil 1 Seite / Stop/Seek/Generation: `frontend/app/auffuehrung/page.tsx`
- Teil 2 Solo-Seite / Stop/Generation: `frontend/app/inszenierung/auffuehrung/page.tsx`
- Teil 1 Playback: `frontend/features/show/scriptPlayback.ts`
- Cue-Ausfuehrung: `frontend/features/show/cuePlayback.ts`
- Show-Runner (async execute): `frontend/features/show/showRunner.ts`
- Machine-Runner (Dialogue + Execute): `frontend/features/show/machineRunner.ts`
- Diskussion/Mentions: `frontend/features/show/discussionCuePlayback.ts`
- Teil 2 Text-Sync: `frontend/features/inszenierung/teil2TextSyncPlayback.ts`
- Avatar Timer/Serialisierung: `frontend/features/inszenierung/avatarCuePlayback.ts`
- Layered Cues: `frontend/features/inszenierung/layeredCuePlayback.ts`
- Layered Audio: `frontend/features/inszenierung/audioLayerManager.ts`
- Anarchy Playback: `frontend/features/inszenierung/anarchyPlayback.ts`

Backend:

- Director Routes / SSE: `backend/app/api/routes/director.py`
- Director Schemas: `backend/app/schemas/director.py`
- Backend Director Pipeline: `backend/app/director/pipeline.py`
- OSC Queue: `backend/app/director/outputs/osc_queue.py`
- Command Builder/Sender: `backend/app/director/outputs/osc_commands.py`
- Light Scene Tracker: `backend/app/director/outputs/light_scene_tracker.py`
- Light Bridge: `backend/app/director/outputs/lighting.py`
- Light TCP: `backend/app/director/outputs/light_tcp.py`
- Light Technik-Test: `backend/app/director/light_desk_test.py`
- Technik Hold: `backend/app/director/technik_hold.py`
- Sound Bridge: `backend/app/director/outputs/sound.py`
- Sound MIDI: `backend/app/director/outputs/sound_midi.py`
- OSC/MIDI Logs: `backend/app/director/outputs/osc_log.py`,
  `backend/app/director/outputs/midi_log.py`
- Logging Settings: `backend/app/core/config.py`,
  `backend/app/core/logging.py`

## Begriffe und ID-Modell

Diese Begriffe sind verpflichtend. Der Plan darf `Signal` nicht mehr
mehrdeutig verwenden.

| Begriff | Bedeutung | Owner |
| --- | --- | --- |
| `frontend_run_id` | vom Frontend erzeugter Start-Kontext, nur Diagnose-Hinweis | Frontend |
| `frontend_generation` | vorhandener React/Playback-Generation-Zaehler | Frontend |
| `run_id` | autoritative Performance-Run-ID | Backend |
| `run_epoch` | autoritative Backend-Epoch. Jede Start/Stop/Seek/Emergency-Barriere erhoeht sie. | Backend |
| `barrier_id` | ID einer Stop/Seek/Emergency-Barriere | Backend |
| `http_request_id` | ID eines API Requests | Backend, optional Frontend gespiegelt |
| `logical_signal_id` | ein fachlicher Cue, z.B. "Avatar RZ21.Caro" oder "Light scene X" | Backend |
| `command_id` | genau ein konkreter Transport-Command, z.B. ein OSC Address/Args-Paket | Backend |
| `queue_batch_id` | ein Queue-Batch mit einem oder mehreren `command_id`s | Backend |
| `receiver_event_id` | eine Sichtung beim Fake Receiver | Receiver |

Regel:

- Backend ist fuer `run_id` und `run_epoch` autoritativ **ab Phase 5**.
  Phase 1–4: provisional Werte mit `context_source`-Markierung.
- Frontend darf `frontend_run_id` und `frontend_generation` mitsenden, aber
  ein Frontend-Wert darf niemals als Beweis fuer die aktive Backend-Epoch
  gelten.
- Ein logischer Cue kann mehrere Transport-Commands erzeugen. Deshalb muessen
  `logical_signal_id` und `command_id` getrennt sein.
- Drop-Klassifikation erfolgt primaer pro `command_id`. Ein
  `logical_signal_id` kann mehrere Command-Drops enthalten.

## ID-Generierung

Alle IDs sind strings. Counter sind pro Prozess-Lauf thread-safe (Lock).

| ID | Format | Erzeuger | Wann |
| --- | --- | --- | --- |
| `frontend_run_id` | `fe-run-{Date.now()}` | Frontend | Playback-Start Teil 1/2 |
| `frontend_generation` | Integer (bestehend) | Frontend | `++playbackGenRef` / `++genRef` |
| `run_id` | `run-{YYYYMMDD}-{HHMMSS}-{4 hex}` | Backend | Erster Director-Request ohne Kontext; Phase 5: explizit bei Performance-Start |
| `run_epoch` | Integer ab 0 | Backend | Start/Stop/Seek/Emergency; Phase 1: provisional aus Request-Kontext |
| `barrier_id` | `barrier-{6 hex}` | Backend | Stop/Seek/Emergency (Phase 1: loggen wenn erkennbar, Phase 5: autoritativ) |
| `http_request_id` | `req-{6 hex}` | Backend | Jeder Director-Route-Handler-Eingang |
| `logical_signal_id` | `sig-{6 hex}` | Backend | Einmal pro `execute`/`execute_layered`/`osc-test` Request (ein fachlicher Dispatch) |
| `command_id` | `cmd-{sig-suffix}-{2-digit-seq}` | Backend | Einmal pro `OscCommand` im Build-Ergebnis, seq ab `01` |
| `queue_batch_id` | `batch-{6 hex}` | Backend | Pro `OscCommandQueue.enqueue`-Aufruf |
| `receiver_event_id` | `rx-{6 hex}` | Fake Receiver | Pro empfangenem Paket/Nachricht |

Regeln:

- `command_id` wird beim Command-Build vergeben und am `OscCommand` (Sidecar `trace`)
  mitgetragen — nicht erst in der Queue neu erfunden.
- `logical_signal_id` gilt pro Request, nicht global pro Show. Mehrfaches Feuern
  desselben Cue-Punkts erzeugt neue `logical_signal_id`s (Duplikat-Erkennung
  ueber `cue_point_key` + `frontend_generation` + Zeit).
- Phase 1: fehlt Frontend-Kontext, Backend setzt `context_source=backend_generated`
  und erzeugt trotzdem IDs — als Diagnose-Luecke markieren, nicht als Autoritaet.

## TraceContext

Gemeinsame optionale Struktur fuer API-Requests und Command-Sidecar.

Backend (`backend/app/schemas/director.py` — neues Modell `TraceContext`):

```python
class TraceContext(BaseModel):
    frontend_run_id: str | None = None
    frontend_generation: int | None = None
    source: str | None = None          # z.B. "teil2_text_sync"
    trigger: str | None = None         # z.B. "avatar_char_offset"
    cue_point_key: str | None = None
    segment_key: str | None = None
    frontend_route: str | None = None  # z.B. "/auffuehrung"
```

Erweiterungen:

- `ExecuteRequest` / `ExecuteLayeredRequest`: optionales Feld `trace: TraceContext | None`
- `OscCommand` (`cue_models.py`): optionales Feld `trace: CommandTraceMeta | None`:

```python
class CommandTraceMeta(BaseModel):
    logical_signal_id: str
    command_id: str
    run_id: str | None = None
    run_epoch: int | None = None
    http_request_id: str | None = None
```

- Frontend (`frontend/lib/types/director.ts`): analoge Types;
  `postDirectorExecute*` reicht `trace` im JSON-Body durch

## Event- und Status-Konventionen

- **Event-Feld** (`event`): immer `domain.action` in Kleinbuchstaben, z.B. `queue.enqueued`.
- **Status-Feld** (`status`): Kurzform ohne Domain-Prefix, z.B. `enqueued`.
- Zeitstempel fuer Latenz-Analyse: zusaetzlich `*_ts_mono_ms` pro Stufe am selben
  `command_id` (oder aus Event-Reihenfolge ableiten).
- **Nicht** Mischformen wie `command_built` als Event-Name verwenden.

## Dispatch-Pfade

Zwei Wege ab `DirectorPipeline._dispatch_commands`:

| Modus | Bedingung | Events |
| --- | --- | --- |
| Queue | `settings.director_osc_queue == True` | `queue.enqueued` → `queue.dequeued` → `command.send_*` |
| Sync | `settings.director_osc_queue == False` | kein `queue.*`; direkt `command.send_attempted` → `command.send_completed`/`command.send_failed` |

In beiden Faellen: vorher immer `signal.planned` und `command.built` (am Build-Ergebnis).

## Debug-Invarianten

Diese Aussagen muessen nach der Instrumentierung pruefbar sein:

1. Jedes Trace-Event hat `schema_version`, `event`, `ts_wall`, `ts_mono_ms`.
2. Jeder HTTP-Request in Director-Routes hat genau eine `http_request_id`.
3. Jede Performance hat genau ein autoritatives `run_id` (ab Phase 5 via
   `DirectorRunState`; Phase 1 provisional mit `context_source`-Markierung).
4. Jeder Start/Stop/Seek/Emergency erzeugt oder erhoeht `run_epoch` (ab Phase 5
   autoritativ; Phase 1–4 provisional/log-only).
5. Jeder `execute`/`execute_layered`-Request bekommt genau eine `logical_signal_id`.
   Mehrfaches Feuern desselben Cue-Punkts erzeugt neue IDs (Duplikat-Analyse
   separat).
6. Jeder konkrete Transport-Command bekommt genau eine `command_id`.
7. Ein Command darf in der Fix-Phase (Phase 5) nur gesendet werden, wenn seine
   `run_epoch` noch aktiv ist. In Phase 1–4: Epoch-Vergleich nur loggen.
8. Stop/Emergency erzeugt eine sichtbare Barriere: alle danach gesendeten alten
   Epoch-Commands sind Bugs (ab Phase 5 erzwungen; Phase 1–3 nur sichtbar machen).
9. Lifecycle-Stati (`planned`, `built`, `enqueued`, `dequeued`, `send_attempted`,
   `send_failed`, `send_completed`, `receiver_seen`, `stale_dropped`) sind
   unterschiedlich und werden im `status`-Feld gefuehrt; Events heissen
   `signal.planned`, `command.built`, `queue.enqueued`, usw.
10. UI-Highlight darf nicht als Hardware-Sendebeweis gelten.
11. Bei Dry-Run darf kein Hardware-Send passieren, aber die komplette
    Trace-Kette bis `command.dry_run_suppressed_send` muss sichtbar sein.
12. Instrumentierung darf keinen zusaetzlichen `build_osc_commands`-Aufruf
    einfuehren.

## Trace-Schema

Minimal pro Event:

```json
{
  "schema_version": 1,
  "ts_wall": "2026-07-07T12:00:00.000Z",
  "ts_mono_ms": 1234567.89,
  "event": "queue.enqueued",
  "run_id": "run-20260707-120000-7f3a",
  "run_epoch": 12,
  "frontend_run_id": "fe-run-1720353600000",
  "frontend_generation": 38,
  "http_request_id": "req-000123",
  "logical_signal_id": "sig-000423",
  "command_id": "cmd-000423-02",
  "queue_batch_id": "batch-000077",
  "source": "teil2_text_sync",
  "trigger": "avatar_char_offset",
  "bridge": "pixera",
  "address": "/pixera/args/cue/apply",
  "args": ["RZ21.Caro"],
  "decision_reason": "Avatar-Sprache",
  "queue_depth": 3,
  "abort_seen": false,
  "dry_run": false,
  "status": "enqueued"
}
```

Zusaetzliche Felder bei Bedarf:

- `barrier_id`
- `barrier_reason`
- `frontend_route`
- `beat_index`
- `sentence_index`
- `char_offset`
- `cue_point_key`
- `segment_key`
- `projector`
- `clip_id`
- `sound_cue_id`
- `light_scene_id`
- `queue_depth_before`
- `queue_depth_after`
- `worker_thread`
- `latency_ms`
- `receiver_timestamp`
- `receiver_host`
- `receiver_port`
- `tcp_session_id`
- `midi_port`
- `midi_channel`
- `midi_message`
- `error_class`
- `error_message`
- `context_source` (`frontend`, `backend_generated`, `missing`)

## Trace-Events

### Pflicht-Events (vollstaendig)

| Event | Phase | Emittent | Pflichtfelder (zusaetzlich zu Basis) |
| --- | --- | --- | --- |
| `run.started` | 1 (provisional), 5 | Backend | `run_id`, `run_epoch`, `context_source` |
| `run.epoch_advanced` | 1 (log), 5 (enforce) | Backend | `run_id`, `run_epoch`, `barrier_id?`, `barrier_reason?` |
| `run.barrier_created` | 1 (log), 5 (enforce) | Backend | `barrier_id`, `barrier_reason` |
| `frontend.playback_started` | 1 | Frontend | `frontend_run_id`, `frontend_generation`, `source` |
| `frontend.stop_requested` | 1 | Frontend | `frontend_generation` |
| `frontend.seek_requested` | 1 | Frontend | `frontend_generation` |
| `frontend.request_started` | 1 | Frontend | `frontend_run_id`, `frontend_generation`, `source`, `trigger` |
| `frontend.request_aborted` | 1 | Frontend | `http_request_id?` (falls bekannt), `abort_seen: true` |
| `frontend.request_completed` | 1 | Frontend | `executed`, `blocked_reason?` |
| `director.execute_received` | 1 | Backend Route | `http_request_id`, `run_id`, `run_epoch` |
| `director.execute_blocked` | 1 | Backend Pipeline | `blocked_reason` |
| `api.response_executed` | 1 | Backend Route | `executed`, `osc_commands_count`, `queue_mode` |
| `signal.planned` | 1 | Pipeline | `logical_signal_id`, `planned_command_count` |
| `command.built` | 1 | Pipeline | `logical_signal_id`, `command_id`, `bridge`, `address` |
| `queue.enqueued` | 1 | Queue | `queue_batch_id`, `command_id`, `queue_depth_after` |
| `queue.dequeued` | 1 | Queue Worker | `queue_batch_id`, `command_id` |
| `queue.stale_dropped` | 5 only | Queue Worker | `command_id`, `run_epoch`, `active_run_epoch` |
| `command.send_attempted` | 1 | Bridge/Batch | `command_id`, `bridge` |
| `command.send_failed` | 1 | Bridge/Batch | `command_id`, `error_class`, `error_message` |
| `command.send_completed` | 1 | Bridge/Batch | `command_id` |
| `command.dry_run_suppressed_send` | 1 | Bridge | `command_id` |
| `midi.send_logged` | 1–2 | MIDI Bridge | `command_id`, `midi_port`, `midi_channel` (Fallback wenn kein Fake MIDI) |
| `receiver.seen` | 2+ | Fake Receiver | `receiver_event_id`, `address`, `receiver_host`, `receiver_port` |

Basis-Felder jedes Events: `schema_version`, `event`, `ts_wall`, `ts_mono_ms`.

Jedes Event muss fuer Analyse ohne Freitext parsebar sein. Menschenlesbare Logs
duerfen bleiben (`logs/osc.log`, `logs/director.log`), aber die Diagnose basiert
auf JSONL (`logs/signal_trace.jsonl`).

## Phasenplan

### Phase 0: Trace-Vertrag festziehen

Noch keine Runtime-Instrumentierung. Nur Vertrag, Typen, Writer-Skeleton, Tests.

Aufgaben:

- `TraceContext` / `CommandTraceMeta` definieren (siehe Abschnitt `TraceContext`).
- `ExecuteRequest` und `ExecuteLayeredRequest` in `backend/app/schemas/director.py`
  um optionales `trace` erweitern.
- `OscCommand` in `backend/app/director/cues/cue_models.py` um optionales `trace`
  erweitern; Frontend-Typ in `frontend/lib/types/director.ts` spiegeln.
- `SignalTraceWriter` in `backend/app/director/outputs/signal_trace.py`:
  - Setting `signal_trace_path`, default `logs/signal_trace.jsonl`
  - Setting `signal_trace_enabled`, default `app_env == "dev"` (aus `settings.app_env`)
  - In Tests immer `tmp_path` via `conftest`-Fixture setzen
  - Thread-safe append (Lock), eine JSON-Zeile pro Event
- Frontend `SignalTraceBuffer` in `frontend/lib/debug/signalTrace.ts`:
  - Ringbuffer (z.B. 2000 Events) fuer gleiche Schema-Felder
  - `window.__TM_SIGNAL_TRACE__` exportiert `{ events, exportJsonl }`
  - Kein direkter Dateizugriff im Browser; Korrelation mit Backend ueber
    `http_request_id` / `frontend_run_id`
- Event-Namen und Pflichtfelder in Unit-Tests fixieren (ohne volle Pipeline).

Abnahmekriterien:

- Ein Agent kann erkennen, welche ID wann und in welcher Datei erzeugt wird.
- Keine Stelle sagt mehr nur "Signal", wenn eigentlich Request, logischer Cue
  oder Transport-Command gemeint ist.
- Keine zusaetzlichen `build_osc_commands`-Aufrufe sind noetig.
- `backend/tests/test_signal_trace.py` existiert und validiert Schema + Writer.

### Phase 1: Passive Instrumentierung

Keine Send-Semantik aendern. Keine Queue-Cancellation. Keine aktiven
Stale-Drops. Nur beobachten.

Frontend:

- Beim Start von Teil 1 / Teil 2 `frontend_run_id` erzeugen; `frontend.playback_started`
  loggen.
- `armDirectorForPerformance()` ebenfalls loggen (setzt neuen Abort + Emergency-Clear).
- Vorhandene `playbackGenRef` / `genRef` als `frontend_generation` mitsenden.
- Zentrale Instrumentierung in `postDirectorExecute` / `postDirectorExecuteLayered`
  (deckt auch `showRunner`, `machineRunner`, `cuePlayback`, `layeredCuePlayback`,
  `avatarCuePlayback`, `anarchyPlayback` ab).
- `traceContext` optional in API-Body (`trace`-Feld).
- Vor dem Fetch loggen: `frontend.request_started` (+ Felder aus Messpunkte).
- Bei Fetch-Abbruch: `frontend.request_aborted`.
- Bei Response: `frontend.request_completed` inkl. `executed`/`blocked_reason`.
- Events in `SignalTraceBuffer`; bei Bedarf `console.debug` mit Prefix `[signal-trace]`.

Backend:

- Director-Routes (`backend/app/api/routes/director.py`) erzeugen `http_request_id`
  beim Request-Eingang; loggen `director.execute_received`.
- Bei Scheduler/Safety-Block: `director.execute_blocked`.
- Bei Response: `api.response_executed` mit `queue_mode=settings.director_osc_queue`.
- Provisional `run_id`/`run_epoch`: bei fehlendem Kontext Backend-generiert mit
  `context_source=backend_generated` (Diagnose-Luecke, nicht Autoritaet).
- `DirectorPipeline.execute*` loggt `signal.planned`, `command.built` am
  bestehenden Build-Ergebnis (IDs an `OscCommand.trace` haengen).
- `OscCommandQueue.enqueue` loggt `queue.enqueued` mit `queue_batch_id`, depths.
- Queue Worker loggt `queue.dequeued`, `command.send_*` pro `command_id`.
- Sync-Pfad (`_execute_commands_sync`): kein `queue.*`, direkt `command.send_*`.
- Bridges loggen transportnahe Details; Exceptions → `command.send_failed`.
- Bekannter Bug dokumentieren: `send_osc_batch` returned Command trotz Exception
  in `sent` — Trace muss `send_failed` trotzdem schreiben.

Wichtig:

- `stale_epoch` / `epoch_mismatch` nur als optionales Vergleichsfeld loggen
  (`active_run_epoch` vs. Command-`run_epoch`), kein Drop-Mechanismus.
- `executed=true` in API bleibt unveraendert; Trace spiegelt es in
  `api.response_executed`, nicht als Hardware-Beweis.

Abnahmekriterien:

- Technik-Test (`POST /director/osc-test`) erzeugt lueckenlose Kette bis
  `command.send_attempted` oder `command.dry_run_suppressed_send`.
- Queue-Test mit `director_osc_queue=True`: API-Response (`api.response_executed`)
  vor `command.send_completed` sichtbar.
- Bridge-Exceptions fuehren zu `command.send_failed`.

### Phase 2: Fake Receiver Harness

Einen kontrollierten Empfaenger einsetzen, bevor echte Hardware analysiert wird.

OSC / Pixera / TouchDesigner:

- UDP/OSC Receiver mit `python-osc` (Dependency bereits in `backend/pyproject.toml`).
- Neues Modul `backend/app/director/testing/fake_osc_receiver.py` oder Test-Fixture.
- Loggt `receiver.seen` mit Adresse, Args, Host/Port, Timestamp.
- Test-Settings routen auf Fake Receiver:
  - `osc_host` / `osc_port` (TouchDesigner)
  - `pixera_osc_host` / `pixera_osc_port` (falls `visual_output` pixera/both)
  - In Tests via `monkeypatch.setattr(settings, ...)` auf `127.0.0.1:<free_port>`

Light TCP:

- TCP Mock muss die aktuellen Settings spiegeln:
  - `light_osc_tcp_format`
  - `light_osc_tcp_framing`
  - `light_tcp_handshake`
  - `light_tcp_read_ack`
- Loggt Connect, optional Handshake, jedes dekodierte OSC-Paket,
  Disconnect, Fehler.
- Wenn Framing nicht dekodierbar ist, muss raw length/bytes sichtbar sein.

MIDI:

- Wenn ein virtual MIDI port lokal verfuegbar ist, Fake MIDI Receiver nutzen.
- Wenn nicht, darf MIDI nur bis `midi.send_logged` validiert werden.
  Das ist dann kein `receiver.seen` — Analyse-Script muss das als
  `sent_not_received` mit Hinweis `midi_no_receiver` klassifizieren.

Erwartung:

- Wenn Backend `command.send_completed` fuer UDP/OSC loggt, muss Fake Receiver
  `receiver.seen` loggen (innerhalb 500 ms Timeout in Tests).
- Wenn Fake Receiver nichts sieht, liegt der Drop zwischen Bridge und Transport.
- Wenn Fake Receiver alles sieht, liegt der Drop wahrscheinlich in echter
  Hardware, Mapping oder Timing.

### Phase 3: Repro-Matrix

Spalte **Phase**: welche Erwartung in welcher Implementierungsphase gilt.

| Szenario | Phase | Erwartung | Verdacht bei Fehler |
| --- | --- | --- | --- |
| Einzelner Technik-Test Video | 1+ | 1 `logical_signal_id`, N `command_id`, N send/receiver Events | Mapping/Transport |
| Einzelner Technik-Test Sound | 1+ | 1 `logical_signal_id`, MIDI `midi.send_logged` oder Fake MIDI `receiver.seen` | MIDI map/Port/Ableton |
| Einzelner Technik-Test Licht | 1+ | 1 `logical_signal_id`, N Commands, TCP connected | TCP Session/EOS |
| Teil 1 komplett Dry-Run | 1+ | keine Trace-Luecken bis `command.dry_run_suppressed_send` | Frontend scheduling / cue points |
| Teil 2 Text-Sync Dry-Run | 1+ | Avatar-Cues nur ab char_offset | Avatar timer / fired set |
| Start -> Stop nach 100 ms | 1–3 | alte Epoch nach Barrier nur im Trace sichtbar (`epoch_mismatch`) | Queue stale batch |
| Start -> Stop nach 100 ms | 5 | keine physischen Sends alter Epoch nach Barrier | fehlende Queue cancellation |
| Start -> Seek waehrend Cue | 1+ | alte Generation startet keine neuen Requests | generation guard |
| Teil 1 starten, dann Teil 2 starten | 1+ | keine Cross-Run-Signale ohne passende Run/Epoch | shared abort/controller |
| Teil 2 Segment anklicken mehrfach | 1+ | nur letzte Auswahl bleibt aktiv | stop/play race |
| Emergency waehrend Queue depth > 0 | 1–3 | alte Commands nach Barrier im Trace sichtbar | fehlende Queue cancellation |
| Emergency waehrend Queue depth > 0 | 5 | Emergency gewinnt, alte Batches `queue.stale_dropped` | Worker/Epoch bug |
| Hardware offline | 1+ | `command.send_failed` sichtbar, nicht still verschluckt | Bridge exception handling |
| Queue-Stress 100 logische Cues | 1+ | keine stillen Drops, klare Latenz und Queue-Tiefe | worker/backpressure |

Wichtig:

- Erwartungen muessen zwischen `logical_signal_id` und `command_id` zaehlen.
- Licht und Pixera duerfen nie pauschal als "1 Signal = 1 Command" getestet
  werden.
- Barrier/Epoch-Erwartungen in Phase 1–3 sind **nur Trace-Sichtbarkeit**, keine
  erzwungene Cancellation.

### Phase 4: Drop-Klassifikation

Jeder Command-Drop wird in genau eine primaere Klasse eingeordnet. Ein
logischer Cue kann mehrere Command-Drops enthalten.

| Klasse | Definition | Beispiel |
| --- | --- | --- |
| `frontend_not_fired` | UI/Playback hat keinen API Request gestartet | Cue Point nie erreicht |
| `request_aborted_before_backend` | Fetch wurde vor Backend-Annahme abgebrochen | Stop direkt vor Send |
| `backend_blocked` | Backend blockiert bewusst | emergency, safety, interval |
| `planned_not_built` | Logischer Cue geplant, aber kein Command gebaut | Mapping fehlt |
| `built_not_enqueued` | Command gebaut, aber nicht in Queue/sync dispatch | Dispatch bug |
| `enqueued_not_dequeued` | Batch bleibt in Queue | Worker dead/hung |
| `dequeued_not_attempted` | Worker nimmt Batch, versucht Send nicht | stale epoch, bridge routing |
| `attempted_failed` | Bridge/Transport wirft Fehler | TCP connect, MIDI port |
| `sent_not_received` | Bridge sendet, Fake Receiver sieht nichts | UDP/TCP/host/port |
| `received_not_executed` | Receiver/Hardware sieht Signal, fuehrt nicht aus | Mapping/Hardware state |
| `late_stale_signal` | Command kommt nach Stop/Seek/Emergency-Barriere | Race Condition |
| `duplicate_command_id` | gleiche `command_id` feuert mehrfach | Queue/Worker bug |
| `duplicate_logical_signal` | verschiedene Commands/IDs fuer gleiche fachliche Cue unerwartet mehrfach | fired key/generation bug |

### Phase 5: Semantik-Fixes

Erst nach Phase 1 bis 4.

Fix 1: API-Semantik sauber benennen

- API Response sollte bei Queue aktiv nicht suggerieren, dass Hardware fertig
  ist.
- `executed` schrittweise in `accepted` / `queued` / `sent` / `failed`
  aufteilen oder UI bewusst reduzieren.
- UI darf "gesendet" nicht anzeigen, wenn nur "queued" bekannt ist.

Fix 2: Backend Run/Epoch als Autoritaet (Phase 5)

- Backend fuehrt `DirectorRunState` ein (`backend/app/director/run_state.py`).
- Start erzeugt neues `run_id` und erhoeht `run_epoch`; emittiert `run.started`.
- Stop/Seek/Emergency erzeugen `barrier_id`, erhoehen `run_epoch`, emittieren
  `run.barrier_created` + `run.epoch_advanced`.
- Frontend wartet beim Start auf Backend-Run-Kontext (`GET /director/status` oder
  dedizierte Run-Route), bevor Cues feuern — ersetzt provisional Phase-1-Logik.
- `emergency-clear` / `armDirectorForPerformance` → `clear_for_performance` setzt
  Run-State zurueck (explizit loggen).

Fix 3: Queue Epoch / Cancellation

- `_OscBatch` traegt `run_id`, `run_epoch`, `queue_batch_id`.
- Queue kann alte Batches sichtbar droppen.
- Worker prueft vor jedem Command, ob Epoch noch aktiv ist.
- Dropped Commands erhalten `queue.stale_dropped`.
- Emergency-Kommandos muessen bevorzugt oder synchron gesendet werden.

Fix 4: Stop-Barriere

Stop darf erst als vollzogen gelten, wenn:

- Frontend Audio gestoppt ist.
- Layered Audio gestoppt ist.
- pending Avatar Timer gecleart ist.
- in-flight Frontend Requests abgebrochen sind.
- Backend Stop/Emergency akzeptiert wurde.
- alte Queue-Batches invalidiert oder als stale sichtbar sind.

Konkrete Frontend-Aenderung:

- Stop-Funktionen sollen `Promise<void>` zurueckgeben oder eine explizite
  "barrier accepted" Phase haben.
- `stopDirectorPerformance()` darf fuer Debug/Fix-Phase nicht dauerhaft
  fire-and-forget bleiben.
- `avatarPositionTimer` und `pendingAvatarPositionFire` brauchen eine
  exportierte Clear-Funktion, die bei Stop aufgerufen wird.

Fix 5: Receiver-Ack fuer Testbetrieb

- Fake Receiver als Ack fuer Debug/Probe verwenden.
- Optional spaeter TouchDesigner/Pixera Debug-Rueckkanal.

Fix 6: Bridge-spezifische Robustheit

- MIDI: Port/Mappings vor Show validieren.
- Pixera: Cue-Namen vor Show gegen OSC-Liste validieren.
- Licht: TCP connected/session state im Status sichtbar machen.
- Sound: `active_cues` nicht nur append, sondern Stop/Fade semantisch
  nachziehen.

## Entscheidungsbaum

### Signal fehlt komplett

1. Gibt es `frontend.request_started`?
2. Wenn nein:
   - Cue Point / Avatar position / Satzindex pruefen.
   - `shouldAbort()` zum Zeitpunkt pruefen.
   - Debounce/Timer pruefen.
3. Wenn ja: Gibt es `director.execute_received` mit gleicher
   `http_request_id`?
4. Wenn nein:
   - AbortController, Netzwerk, Browser-Konsole pruefen.
5. Wenn ja: Gibt es `signal.planned`?
6. Wenn nein:
   - Scheduler/Safety/Decision pruefen.
7. Wenn ja: Gibt es `command.built`?
8. Wenn nein:
   - Mapping/Command Builder pruefen.
9. Wenn ja: Gibt es `queue.enqueued` oder sync send path?
10. Wenn nein:
   - Pipeline dispatch pruefen.
11. Wenn ja: Gibt es `command.send_attempted`?
12. Wenn nein:
   - Queue Worker / stale epoch / dead thread pruefen.
13. Wenn ja: Gibt es `command.send_completed` oder `command.send_failed`?
14. Wenn failed:
   - Bridge exception und Transport pruefen.
15. Wenn completed: Gibt es `receiver.seen`?
16. Wenn nein:
   - Host/Port/Transport/Firewall/Hardware route pruefen.

### Signal kommt zu spaet

Latenz aus `ts_mono_ms` desselben `command_id` zwischen Events ableiten:

1. `signal.planned` → `command.built`
2. `command.built` → `queue.enqueued` (oder bei Sync direkt → `command.send_attempted`)
3. `queue.enqueued` → `queue.dequeued`
4. `queue.dequeued` → `command.send_attempted`
5. `command.send_attempted` → `command.send_completed`
6. `command.send_completed` → `receiver.seen`
7. Queue depth und `CUE_STAGGER_SECONDS` pruefen.
8. Pruefen, ob Highlight-Sleep, Pause oder TTS-Wait indirekt Timing
   beeinflusst.

### Signal kommt nach Stop

1. Stop erzeugt `run.barrier_created` und `run.epoch_advanced`.
2. Alle nachfolgenden Send-Logs mit alter Epoch markieren.
3. In Phase 1: alte Sends nur sichtbar machen.
4. In Fix-Phase: alte Sends muessen vor Send als `queue.stale_dropped`
   enden.
5. Wenn alte Epoch physisch sendet:
   - Queue braucht cancellation/stale-check.
   - Worker muss vor jedem Command Safety/Epoch pruefen.
   - `emergency_stop()` muss Queue drain/drop sichtbar machen.

### Signal kommt doppelt

1. Gleiche `command_id` doppelt? Dann Queue/Worker bug.
2. Verschiedene `command_id`, gleiche `logical_signal_id`? Dann pruefen, ob
   mehrere Commands fachlich erwartet sind.
3. Verschiedene `logical_signal_id`, gleiche fachliche Cue? Dann Frontend
   scheduler / fired key / generation bug.
4. Gleiche Avatar `segment_key` doppelt? Dann `firedSegments`, Debounce und
   Generation pruefen.
5. Gleicher Sound-Cue mehrfach? Dann `active_cues` und Fade/Hold-Semantik
   pruefen.

## Messpunkte im Frontend

### Playback Start

Log bei:

- `playFrom` in `frontend/app/auffuehrung/page.tsx`
- `playTeil2` in `frontend/app/auffuehrung/page.tsx`
- `play` in `frontend/app/inszenierung/auffuehrung/page.tsx`
- `runScriptPlayback`
- `runTextSyncPlayback`
- `runAnarchyPlayback`

Felder:

- `frontend_run_id`
- `frontend_generation`
- `mode`
- `start_index`
- `end_index`
- `tryout`
- `tts_available`
- `has_rendered_audio`
- `route`

### Cue Fire

Log bei:

- `fireCuePoint`
- `executeCueSafely`
- `scheduleDiscussionCue`
- `fireDiscussionMentionsAtPosition`
- `fireAvatarSegmentsAtPosition`
- `executeAvatarVisualCue`
- `fireLayeredMomentCues`

Felder:

- `cue_point_key`
- `trigger`
- `sentence_index`
- `current_time`
- `global_pos`
- `segment_key`
- `should_abort`
- `director_aborted`

### Stop / Pause / Seek

Log bei:

- `handleStop`
- `handlePause`
- `handleSeek`
- `stopScriptPlayback`
- `stopTextSyncPlayback`
- `stopAnarchyPlayback`
- `stopDirectorPerformance`

Felder:

- alte/neue `frontend_generation`
- alter/neuer Backend-Run-Kontext, falls bekannt
- `currentAudio` vorhanden
- `activeLayeredVoiceCount`
- pending avatar timer ja/nein
- in-flight request count

## Messpunkte im Backend

### Director Route

Log bei allen `POST`/`PATCH` unter `/director/*`, insbesondere:

- `POST /director/execute`
- `POST /director/execute-layered`
- `POST /director/dialogue-event` (indirekter Cue-Pfad via `machineRunner`)
- `POST /director/osc-test`
- `POST /director/technik/start`
- `POST /director/technik/stop`
- `POST /director/light/connect`
- `POST /director/light/disconnect`
- `POST /director/light/send`
- `POST /director/light/stop`
- `POST /director/emergency-stop`
- `POST /director/emergency-clear`
- `POST /director/record/start` / `record/stop` (falls waehrend Show aktiv)

Felder:

- `http_request_id`
- `run_id`
- `run_epoch`
- request arrival timestamp
- response timestamp
- status
- route
- payload trace context

### Pipeline

Log bei:

- `execute`
- `execute_layered`
- `_dispatch_commands`
- `_store_result`
- `clear_for_performance`
- `emergency_stop`

Besonders pruefen:

- Lock deckt State ab, aber nicht zwingend physische Sendereihenfolge.
- `_dispatch_commands(... wait=False)` bedeutet: API kann zurueckkehren, bevor
  Hardware fertig ist.
- `scheduler.mark_executed` passiert direkt nach Dispatch, nicht nach
  Hardware-Ack.
- `projectors.lock_after_play` passiert nach Dispatch, nicht nach Receiver-Ack.

### Command Builder

Log bei bestehendem Build-Ergebnis:

- `signal.planned`
- `command.built`

Verbot:

- Keine extra Build-Aufrufe fuer reine Trace-Zwecke.

Pruefpunkt:

- Mutiert Light Scene Tracker beim Build?
- Plant ein nicht gesendeter Cue trotzdem neue aktive Light Scenes?
- Fuehrt ein Drop dazu, dass spaeter falsche Fade-Outs gebaut werden?

### Queue

Log bei:

- enqueue
- dequeue
- before send each command
- after send each command
- exception per command
- queue flush/drop/cancel

Pruefpunkt:

- Gibt es aktuell keine Moeglichkeit, alte Batches zu invalidieren?
- Gibt es keinen `run_epoch` Check im Worker?
- Wird bei Emergency die Queue geleert?
- Werden Emergency-Kommandos hinter alten Batches eingereiht?

### Bridges

Log bei:

- Pixera `apply_cue`
- TouchDesigner `play_clip`, `blackout`, `stop_clip`
- Sound `trigger`, `stop`, `stop_all`
- MIDI `_send`
- Light TCP `open_session`, `send_osc`, `close_session`
- Lighting `send_scene`, `blackout_signal`, `apply_group`, `apply_channel`

Pruefen:

- Werden Exceptions verschluckt?
- Wird `sent.append(cmd)` auch bei Fehlern gesetzt?
- Wird `dry_run` korrekt pro Bridge beachtet?
- Gibt es fuer Licht Scene Tracker globale Mutationen beim reinen Command
  Build?

## Log-Dateien

Pflicht:

- `logs/signal_trace.jsonl` — strukturierte Trace Events (Backend `SignalTraceWriter`).
- `logs/osc.log` — menschenlesbare OSC/MIDI/TCP Ausgabe (bestehend).
- `logs/director.log` — fachliche Entscheidungen (bestehend).

Frontend (Diagnose, nicht persistent auf Disk):

- `SignalTraceBuffer` + `window.__TM_SIGNAL_TRACE__.exportJsonl()` fuer manuelle
  Korrelation mit Backend-JSONL.
- Browser-Konsole mit Prefix `[signal-trace]` optional.

Abgrenzung:

- `backend/scripts/visualize_show_logs.py` (`make visualize-logs`) visualisiert
  **bestehende** `osc.log`/`director.log` — nicht `signal_trace.jsonl`.
- Neues Analyse-Script arbeitet auf `signal_trace.jsonl` (siehe unten).

JSONL ist wichtig, damit ein Analyse-Script Drops gruppieren kann.

## Analyse-Script

**Pfad:** `backend/scripts/analyze_signal_trace.py`

**Aufruf:**

```bash
cd backend && .venv/bin/python scripts/analyze_signal_trace.py \
  --trace ../logs/signal_trace.jsonl \
  --run-id run-20260707-120000-7f3a
```

Optional: `--frontend-export path/to/frontend-export.jsonl` fuer zusammengefuehrte
Analyse (gleiches Schema).

Das Script soll pro `run_id` ausgeben:

- Anzahl logische Cues geplant.
- Anzahl Commands built/enqueued/dequeued/attempted/completed/failed/received.
- Fehlende Stufen pro `command_id`.
- Aggregierte Drops pro `logical_signal_id`.
- Commands nach Stop-Barriere.
- Doppelte fachliche Cues.
- Latenz p50/p95/max pro Bridge.
- Queue depth Verlauf.
- API-Response-vor-Send-Faelle (`api.response_executed` vor `command.send_completed`
  fuer gleiche `command_id`).

**Drop-Klassifikation im Script:** implementiert die Tabelle aus Phase 4 als
reine Funktion `classify_command_drops(events) -> list[DropReport]` — keine
duplizierte Logik in Tests und Script.

Makefile-Erweiterung (optional, Phase 4): `make analyze-signal-trace` analog zu
`make visualize-logs`.

Beispielausgabe:

```text
Run run-20260707-120000-7f3a epoch=12
logical_signals: 142
commands_built: 219
enqueued: 219
dequeued: 218
send_attempted: 218
send_completed: 215
send_failed: 3
receiver_seen: 211
late_stale_signal: 4

Top drops:
- cmd-000087-01 pixera RZ21.Caro: enqueued_not_dequeued
- cmd-000102-01 sound maschinen_grundader_fade_out: sent_not_received
- cmd-000119-04 light /eos/chan/91: late_stale_signal after barrier barrier-000013
```

## Konkrete Testfaelle

### T01: Single Signal Smoke

Aktion:

- Technik-Test Video, Sound, Licht einzeln ausloesen.

Erwartung:

- Jede Aktion hat genau einen `logical_signal_id`.
- Jeder erzeugte Transport-Command hat einen eigenen `command_id`.
- Kein stiller Fehler.
- Fake Receiver sieht Video/OSC.

### T02: Queue Ordering

Aktion:

- Drei logische Cues schnell hintereinander: Video, Sound, Licht.

Erwartung:

- Reihenfolge im Queue-Log stabil.
- `CUE_STAGGER_SECONDS` erklaert sichtbare Abstaende.
- API Response kann vor `command.send_completed` kommen und wird so geloggt.

### T03: Stop Race

Aktion:

- Teil 2 starten.
- Nach 100 ms Stop.
- Nach 300 ms erneut Start.

Erwartung Phase 1:

- Alte Epoch nach Stop-Barriere ist sichtbar.
- Neue Epoch sendet normal.

Erwartung Fix-Phase:

- Keine physisch gesendeten Commands der alten Epoch nach Stop-Barriere.

### T04: Seek Race

Aktion:

- Teil 1 starten.
- Waehrend Cue-Highlight seeken.

Erwartung:

- Alte Generation aktualisiert UI nicht.
- Alte Generation startet keine neuen Requests.
- Backend-Barriere trennt alte und neue Epoch.

### T05: Avatar Debounce

Aktion:

- Teil 2 Text-Sync mit vielen nahen Avatar-Offsets.

Erwartung:

- `pendingAvatarPositionFire` verliert keine faelligen Segmente.
- Wenn mehrere Offsets innerhalb 150 ms due sind, werden alle faelligen
  Segmente abgearbeitet oder sichtbar blockiert.
- Stop leert `avatarPositionTimer` und `pendingAvatarPositionFire`.

### T06: Emergency Under Load

Aktion:

- Queue kuenstlich fuellen.
- Emergency ausloesen.

Erwartung Phase 1:

- Alte Commands nach Emergency-Barriere sind sichtbar.

Erwartung Fix-Phase:

- Emergency-Kommandos gewinnen.
- Alte Queue-Batches werden gedroppt oder als stale markiert.
- Kein alter Licht/Sound/Video-Befehl nach Emergency.

### T07: Receiver Offline

Aktion:

- Falscher OSC Host/Port oder TCP Mock nicht erreichbar.

Erwartung:

- Drop wird als Transport/Receiver-Problem sichtbar.
- UI meldet nicht "alles okay", wenn Send fehlschlaegt.

### T08: Long Run

Aktion:

- Komplette Auffuehrung im Dry-Run und mit Fake Receiver.

Erwartung:

- Keine fehlenden Stufen pro `command_id`.
- Queue-Tiefe faellt nach Idle wieder auf 0 (kein monotones Wachstum ueber >5 min).
- Relative Latenz p95 pro Bridge steigt nicht um >3x gegenueber den ersten
  10 Minuten (keine Hard-Limits auf Absolutwerte in Phase 1–3).
- Keine `duplicate_command_id` ohne fachliche Begruendung.

### T09: Build-Mutation Guard

Aktion:

- Light Cue planen, aber nicht senden.
- Danach anderen Light Cue bauen.

Erwartung:

- Trace-Instrumentierung verursacht keine zusaetzliche Light-State-Mutation.
- Falls bestehender Build mutiert, ist das als eigenes Risiko sichtbar.

## Automatisierte Tests

Backend:

- `backend/tests/test_signal_trace.py`
  - JSONL Writer schreibt valides Schema.
  - Writer ist thread-safe genug fuer Queue Worker.
  - `conftest`-Fixture setzt `signal_trace_path` auf `tmp_path`.
- `backend/tests/test_analyze_signal_trace.py`
  - Drop-Klassifikation fuer kuenstliche Event-Ketten.
- `backend/tests/test_director_trace_context.py`
  - Execute Requests erzeugen `http_request_id`, `logical_signal_id`,
    `command_id`.
  - Fehlender Frontend-Kontext wird als `context_source=backend_generated`
    sichtbar.
- `backend/tests/test_osc_queue_trace.py`
  - Queue-Modus explizit aktivieren, da `conftest.py` ihn deaktiviert.
  - enqueue/dequeue/send Events werden geschrieben.
  - Exception erzeugt `command.send_failed`.
- `backend/tests/test_run_epoch_queue.py`
  - Erst in Fix-Phase: alte Epoch wird als stale gedroppt.
- `backend/tests/test_fake_receivers.py`
  - UDP/OSC Fake Receiver sieht gesendete Pakete.
  - Light TCP Mock dekodiert oder loggt raw payload nachvollziehbar.

Frontend (Vitest, bestehendes Setup):

- `frontend/lib/api/director.test.ts` (neu):
  - Trace-Kontext wird im JSON-Body mitgesendet.
  - Abort erzeugt `frontend.request_aborted` im Buffer.
- Erweiterung bestehender Tests (`cuePlayback.test.ts` etc.): Mocks fuer
  `SignalTraceBuffer` wo noetig.
- Stop-Tests (Fix-Phase): Generation erhoeht, Avatar-Timer-Clear — in
  `avatarCuePlayback.test.ts` / Page-Tests.

## Priorisierte Verdachtsstellen

### P0: Stop/Emergency vs Queue

Warum kritisch:

- Kann erklaeren, warum Signale "verschwinden" oder spaeter in falschem
  Kontext kommen.
- Sicherheitsrelevant fuer Licht/Sound/Video.

Was pruefen:

- Wird Queue bei Emergency geleert?
- Kann Worker alte Batches erkennen?
- Werden Emergency-Kommandos hinter alten Batches eingereiht?
- Ist `stopDirectorPerformance()` fire-and-forget noch Teil des Problems?

### P0: ID-Modell / Run-Epoch Autoritaet

Warum kritisch:

- Ohne autoritative Backend-Epoch sind Logs nur Dekoration.
- Frontend-Generation allein beweist nicht, ob Backend noch alte Commands
  senden darf.

Was pruefen:

- Gibt es genau eine Backend-Quelle fuer `run_id/run_epoch`?
- Wird jeder Request mit dem aktuellen Backend-Kontext korreliert?
- Sind `frontend_generation` und `run_epoch` sauber getrennt?

### P1: Frontend Abort vs Backend Accepted

Warum kritisch:

- Browser-Abort stoppt nur den Fetch, nicht zwingend Backend-Arbeit, die schon
  angenommen wurde.

Was pruefen:

- Kommt ein Request trotz Abort im Backend an?
- Antwortet Backend nach Abort weiter?
- Wird alte Generation noch highlighted?

### P1: Avatar Debounce / fired Set

Warum kritisch:

- `pendingAvatarPositionFire` haelt nur einen pending Zustand.
- Bei dichter TTS-Progression koennen faellige Segmente zusammenfallen.
- Timer wird aktuell nicht als eigener Stop-State behandelt.

Was pruefen:

- Werden alle due Segmente nach Debounce abgearbeitet?
- Bricht `if (!sent) break` legitime weitere Segmente ab?
- Ist `fired` pro Run sauber neu?
- Wird Timer bei Stop gecleart?

### P2: Command Build mutiert globale Light State

Warum kritisch:

- `build_osc_commands` kann Light Scene Tracker veraendern, bevor Hardware
  wirklich sendet.

Was pruefen:

- Plant ein nicht gesendeter Cue trotzdem neue aktive Light Scenes?
- Fuehrt ein Drop dazu, dass spaeter falsche Fade-Outs gebaut werden?
- Fuehrt Trace-Instrumentierung aus Versehen zu einem zweiten Build?

### P2: Exceptions werden semantisch als sent behandelt

Warum kritisch:

- Einzelne Bridge-Fehler koennen im Log auftauchen, aber UI/Pipeline sieht
  trotzdem Commands.

Was pruefen:

- Wird `sent.append(cmd)` nach Fehlern korrekt behandelt?
- Brauchen wir `send_failed` im Response/Status?
- Muss `executed` fuer Queue-Modus anders benannt werden?

## Definition von "gefixt"

Das Problem gilt erst als beherrscht, wenn:

- mindestens ein kompletter Dry-Run ohne Trace-Luecken durchlaeuft;
- ein Fake-Receiver-Run alle gesendeten UDP/OSC-Commands sieht;
- Stop/Emergency Tests keine physisch gesendeten alten Commands nach der
  Stop-Barriere zeigen;
- Drops automatisch pro `command_id` klassifiziert werden koennen;
- logische Cues korrekt auf ihre Transport-Commands aggregiert werden;
- UI zwischen planned/queued/sent/failed unterscheidet oder bewusst nur einen
  reduzierten Status zeigt;
- fuer Licht/Sound/Video je ein gezielter Regressionstest existiert;
- Trace-Instrumentierung keine zusaetzlichen Command-Build-State-Mutationen
  erzeugt.

## Empfohlener naechster Schritt

Strikt phasenweise — nicht mischen:

**Phase 0 (jetzt):**

1. Typen: `TraceContext`, `CommandTraceMeta`, Schema-Tests.
2. `SignalTraceWriter` + `signal_trace_*` Settings in `config.py`.
3. `SignalTraceBuffer` (Frontend) + `window.__TM_SIGNAL_TRACE__`.
4. API/Model-Erweiterungen (`ExecuteRequest`, `OscCommand`, Frontend-Typen).
5. `backend/tests/test_signal_trace.py` gruen.

**Phase 1 (danach):**

6. Passive Events in `director.ts`, Routes, Pipeline, Queue, Bridges.
7. `backend/tests/test_director_trace_context.py`, `test_osc_queue_trace.py`.
8. T01–T03 manuell/automatisiert im Dry-Run.

**Phase 2–4:** Fake Receiver, Repro-Matrix, `analyze_signal_trace.py`.

**Phase 5:** Semantik-Fixes erst nach gruener Drop-Klassifikation.
