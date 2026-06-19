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
| `aktion` | `play` · `fade_in` · `fade_out` · `out` · `cut_all` |
| `beschreibung` | Dramaturgische Lesart |
| `tags` | Komma-getrennt |
| `stimmungen` | Komma-getrennt |
| `dramaturgie` | `ja` = Dramaturgen dürfen diese `cue_id` wählen · `nein` = nur Technik-Test |

## Aktionen pro Soundname

Pro **soundname** vier Zeilen (wenn vollständig):

| Suffix / cue_id | `aktion` | Bedeutung |
|-----------------|----------|-----------|
| Basis-ID | `play` | Ton starten |
| `…_fade_in` | `fade_in` | Einblenden |
| `…_fade_out` | `fade_out` | Ausblenden |
| `…_out` | `out` | Sofort aus (harter Cut für diesen Layer) |

Zusätzlich global:

| cue_id | Note | `aktion` | Bedeutung |
|--------|------|----------|-----------|
| `alle_sounds_cut` | 127 | `cut_all` | Alle Sounds sofort aus |

## Dramaturgie (aktueller Stand)

Mit `dramaturgie=ja` (in Ableton angelegt):

- `maschinen_grundader` … `herz_unter_glas_fade_out` (inkl. `_out`)
- `metallseufzer` … `metallseufzer_out`
- `alle_sounds_cut`

Alle anderen Zeilen bleiben in der CSV (`dramaturgie=nein`) für spätere Erweiterung und Technik-Test.

## MIDI-Noten (Übersicht)

| Bereich | Noten | Aktion |
|---------|-------|--------|
| Play | 36–45 | `play` |
| Fade In | 52–70 | `fade_in` |
| Fade Out | 53–71 | `fade_out` |
| Out | 72–81 | `out` |
| Alle aus | 127 | `cut_all` |

## Pflege

1. CSV bearbeiten (Excel, Numbers, LibreOffice)
2. Backend neu laden (Neustart oder nächster API-Call lädt neu)
3. Ableton: passende Noten belegen (siehe `docs/ableton_setup.md`)

Abgeleitete Datei (automatisch): `data/sound_cues.json`
