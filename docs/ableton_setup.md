# Sound-Übersicht (Ableton / MIDI)

Quelldatei: **`media/sound/Sound Übersicht.csv`** — analog zu `media/light/Kanal Übersicht.xlsx`.

Die Maschine triggert **keine Audiodateien**, sondern sendet **MIDI Note On/Off** an Ableton (IAC-Bus).  
Die Sound-Abteilung mappt Note → Sample/Clip.

```
Dramaturgie (cue_id)  →  Sound Übersicht.csv  →  MIDI Note  →  Ableton  →  Ton
  maschinen_grundader         Note 36, Kanal 1      IAC Bus      Drum Rack
  maschinen_grundader_fade_in Note 52              …            Fade In
```

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
2. Fenster **MIDI-Studio** → doppelklick **IAC-Treiber**  
3. **Gerät ist online** aktivieren  
4. Mindestens **Bus 1** anlegen (Name z. B. `IAC Driver Bus 1`)

---

## 3. Backend konfigurieren

In `backend/.env` (Backend **nativ auf dem Mac**):

```env
SOUND_OUTPUT=midi
SOUND_OSC_MIRROR=false
SOUND_MIDI_PORT="IAC Driver Bus 1"
SOUND_MIDI_CHANNEL=1
OSC_DRY_RUN=false
```

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

1. MIDI-Track, **MIDI from:** `IAC Driver Bus 1`, **Monitor:** `In`
2. Drum Rack mit Pads für alle Noten aus der CSV
3. Pro Soundname drei Pads: `play`, `fade_in`, `fade_out`

Beispiel **Maschinen-Grundader**:

| cue_id | Note | Ableton |
|--------|------|---------|
| maschinen_grundader | 36 | Pad — Loop |
| maschinen_grundader_fade_in | 52 | Pad — Fade-In-Clip |
| maschinen_grundader_fade_out | 53 | Pad — Fade-Out-Clip |

---

## 5. Test

1. Backend nativ starten  
2. Frontend → **Technik** → Sound-Cue wählen → **Sound starten**  
3. Log: `[MIDI SEND] … note_on ch=1 note=36 …`

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
