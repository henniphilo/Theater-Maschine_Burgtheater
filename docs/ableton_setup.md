# Sound-Übersicht (Ableton / MIDI)

Quelldatei: **`media/sound/Sound Übersicht.csv`** — analog zu `media/light/Kanal Übersicht.xlsx`.

Die Maschine triggert **keine Audiodateien**, sondern sendet **MIDI Note On/Off** an Ableton (IAC-Bus).  
Die Sound-Abteilung mappt Note → Sample/Clip.

```
Dramaturgie (cue_id)  →  Sound Übersicht.csv  →  MIDI Note  →  Ableton  →  Ton
  maschinen_grundader         Note 36, Kanal 1      IAC-Bus      Drum Rack Pad C1
  maschinen_grundader_fade_in Note 52              …            Fade In
```

**Kurz-README:** [Start mit Sound / Ableton](../README.md#start-mit-sound--ableton-backend-nativ) · **Technik-Test:** http://localhost:3003/technik

---

## 1. Zwei Mapping-Ebenen

| Ebene | Wer | Datei / Ort | Was |
|-------|-----|-------------|-----|
| **Regie → MIDI** | Dramaturgie | `media/sound/Sound Übersicht.csv` | `cue_id` → Note + Kanal + Aktion |
| **MIDI → Ton** | Sound-Abteilung | Ableton-Set (.als) | Note → Sample, Clip, Fade |

Spalten in der CSV (Semikolon-getrennt):

| cue_id | midi_note | kanal | soundname | aktion | beschreibung | tags | stimmungen |
|--------|-----------|-------|-----------|--------|--------------|------|------------|

**Aktionen:** `play` · `fade_in` · `fade_out` — jede mit **eigener MIDI-Note**.

---

## 2. Mac: virtueller MIDI-Bus (IAC)

1. **Audio-MIDI-Setup** (macOS) öffnen  
2. Fenster **MIDI-Studio** → Doppelklick **IAC-Treiber**  
3. **Gerät ist online** aktivieren  
4. Mindestens **Bus 1** anlegen  

Portname je nach macOS-Sprache:

| Sprache | Portname |
|---------|----------|
| Deutsch | `IAC-Treiber Bus 1` |
| Englisch | `IAC Driver Bus 1` |

Das Backend erkennt beide Schreibweisen (`Driver` ↔ `Treiber`).

---

## 3. Backend starten (nativ — nicht Docker)

MIDI zum IAC-Bus funktioniert **nur mit Backend nativ auf dem Mac**, nicht aus dem Docker-Container.

```bash
# Projektroot
docker compose -f docker-compose.yml -f docker-compose.native.yml up -d postgres redis frontend
docker compose stop backend

# Backend nativ (Python 3.11)
cd backend && ./run-native.sh
```

Voraussetzung: `brew install python@3.11` — **nicht** System-`python3` (3.9) verwenden.

### `backend/.env`

```env
SOUND_OUTPUT=midi
SOUND_OSC_MIRROR=false
SOUND_MIDI_PORT="IAC-Treiber Bus 1"
SOUND_MIDI_CHANNEL=1
OSC_DRY_RUN=false
OSC_HOST=host.docker.internal   # nur für Docker; run-native.sh setzt 127.0.0.1
```

`SOUND_MIDI_PORT` leer = erster IAC-Port.

Mapping bearbeiten in **`media/sound/Sound Übersicht.csv`**.  
Abgeleitet (automatisch): `data/sound_cues.json`

| Regie-Aktion | MIDI |
|--------------|------|
| Cue starten (`trigger_cue` / `play`) | **Note On** |
| Cue stoppen (`stop_cue`) | **Note Off** (gleiche Note) |
| Fade In (`fade_in` cue_id) | **Note On** auf Fade-In-Note |
| Fade Out (`fade_out` cue_id) | **Note On** auf Fade-Out-Note |
| Alles aus (`stop_all`) | **All Notes Off** (CC 123) |

---

## 4. Ableton Live einrichten

### Drum Rack (empfohlen)

1. **MIDI-Track** anlegen (`Cmd+Shift+T`)
2. Rechts **`I-O`** aktivieren — sonst fehlen MIDI From, Monitor und Arm-Button
3. **MIDI From:** `IAC-Treiber Bus 1` (oder `IAC Driver Bus 1`)
4. **Monitor:** `In`
5. **Arm:** an (roter Kreis unten am Track)
6. **Drum Rack** auf den Track ziehen
7. Pads für alle Noten aus der CSV belegen — pro Soundname: `play`, `fade_in`, `fade_out`

### Oktav-Namen (wichtig)

| MIDI-Note | Maschine (Technik-UI) | Ableton Drum Rack |
|-----------|----------------------|-------------------|
| 36 | C2 | **C1** |
| 37 | C#2 | C#1 |
| 52 | E3 | E2 |

Die **Nummer** (z. B. 36) ist maßgeblich — C1/C2 ist nur Beschriftung.

### Beispiel Maschinen-Grundader

| cue_id | Note | Ableton-Pad |
|--------|------|-------------|
| maschinen_grundader | 36 | C1 — Loop |
| maschinen_grundader_fade_in | 52 | E2 — Fade-In |
| maschinen_grundader_fade_out | 53 | F2 — Fade-Out |

---

## 5. Test

1. Backend nativ: `cd backend && ./run-native.sh`
2. Browser: **http://localhost:3003/technik** → Bereich **Sound**
3. Cue wählen (z. B. `Maschinen-Grundader`) → **Signal senden**
4. Log (ohne Fehler):

```text
[MIDI SEND] [sound] → IAC-Treiber Bus 1 note_on ch=1 note=36 vel=63
```

5. In Ableton: Pad **C1** blinkt, Sample spielt

**Signal halten** = wiederholtes MIDI (Keepalive). **Signal stoppen** = Note Off.

---

## 6. Dramaturgie-Cue-IDs

Dramaturgen wählen `cue_id` aus der CSV — z. B. `maschinen_grundader`, `kaefigecho_fade_in`.

| cue_id | Note | soundname | aktion |
|--------|------|-----------|--------|
| maschinen_grundader | 36 | Maschinen-Grundader | play |
| maschinen_grundader_fade_in | 52 | Maschinen-Grundader | fade_in |
| maschinen_grundader_fade_out | 53 | Maschinen-Grundader | fade_out |
| kaefigecho | 37 | Käfigecho | play |

Vollständige Liste: `media/sound/Sound Übersicht.csv`

---

## 7. Häufige Fehler

| Symptom | Lösung |
|---------|--------|
| `rtmidi` / Import-Fehler im Log | Backend läuft in Docker → nativ mit `./run-native.sh` |
| `MIDI port not found: IAC Driver…` | Deutscher Mac: `IAC-Treiber Bus 1` in `.env` und Ableton |
| Log OK, kein Ton | Monitor `In`, Arm an, Pad **C1** (nicht C5) |
| `socket.gaierror` / `host.docker.internal` | Nativ starten — `run-native.sh` setzt `OSC_HOST=127.0.0.1` |
| `python3` 3.9 / pip-Fehler | `brew install python@3.11`, `./run-native.sh` |
