# Sound-Übersicht (Ableton / MIDI)

Quelldatei für alle Sound-Cues der Maschine — analog zu `media/light/Kanal Übersicht.xlsx`.

Die Maschine spielt **keine Audiodateien** ab. Jede Zeile ist ein `cue_id`, der per **MIDI Note On/Off** an Ableton (IAC-Bus) gesendet wird. Die Sound-Abteilung mappt Note → Sample/Clip.

## Datei

`Sound Übersicht.csv` — Semikolon-getrennt, UTF-8.

| Spalte | Bedeutung |
|--------|-----------|
| `cue_id` | ID für Dramaturgie / Regie (nur Kleinbuchstaben, `_`) |
| `midi_note` | Note 0–127 (Ableton Drum Rack / Clip-Launch) |
| `kanal` | MIDI-Kanal 1–16 |
| `soundname` | Anzeigename für Dramaturgen |
| `aktion` | `play` · `fade_in` · `fade_out` |
| `beschreibung` | Dramaturgische Lesart |
| `tags` | Komma-getrennt |
| `stimmungen` | Komma-getrennt |

## Fade In / Fade Out

Pro **soundname** drei Zeilen:

- `…` + `aktion=play` — Ton starten (Note On)
- `…_fade_in` — Einblenden in Ableton
- `…_fade_out` — Ausblenden in Ableton

Jede Aktion hat eine **eigene MIDI-Note** (Spalte `midi_note`).

## Pflege

1. CSV bearbeiten (Excel, Numbers, LibreOffice)
2. Backend neu laden (Neustart oder nächster API-Call lädt neu)
3. Ableton: passende Noten belegen (siehe `docs/ableton_setup.md`)

Abgeleitete Datei (automatisch): `data/sound_cues.json`
