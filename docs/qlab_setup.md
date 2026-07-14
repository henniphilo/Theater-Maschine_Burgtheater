# QLab lokal für Video-OSC testen

Theatermaschine sendet Video als **Pixera-OSC** (`/pixera/args/cue/apply`). QLab versteht das nicht direkt — ein kleiner Relay auf dem Mac übersetzt die Befehle.

```
Theatermaschine  →  127.0.0.1:8990  →  pixera_qlab_relay  →  QLab :53000
```

Auf der Bühne entfällt der Relay; Pixera empfängt die gleichen Befehle direkt.

---

## 1. Backend (.env)

Lokal in `backend/.env`:

```env
OSC_DRY_RUN=false
VISUAL_OUTPUT=pixera
PIXERA_OSC_HOST=127.0.0.1
PIXERA_OSC_PORT=8990
```

Backend **nativ** starten (`make run`), nicht Docker-Backend.

---

## 2. QLab-Workspace

### OSC Access

1. QLab-Workspace öffnen
2. **Workspace Settings** → **Network** → **OSC Access**
3. Haken bei **View** und **Control**
4. OSC Listening Port: **53000** (Standard)

Ohne **Control** kommen OSC-Nachrichten an, aber Cues starten nicht.

### Video-Cues

Pro Videodatei einen **Video Cue** mit **Cue-Nummer = exakter Pixera-Name** (Spalte `qlab_cue_number`).

**Fertige Listen** (aus OSC-Dateien generiert):

| Datei | Inhalt |
|-------|--------|
| [`data/qlab_cue_list_all.csv`](../data/qlab_cue_list_all.csv) | alle 404 Cues (4 Projektoren) |
| [`data/qlab_cue_list_rz21.csv`](../data/qlab_cue_list_rz21.csv) | nur RZ21 (101 Cues) — empfohlen für lokalen Test |

Neu erzeugen:

```bash
make qlab-cue-list
```

Quellen: `OSCBefehlliste.txt` (Datenbank-Clips), `OSCBefehllisteAvatare.txt`, `OSCBefehllisteOhneAvatare.txt`.

Wichtig: Spalte **`qlab_cue_number`** ist maßgeblich — das sendet Theatermaschine (inkl. Aliase, z. B. `BAK1_Nicolas_Pflanzen` statt `BAK1_NicolasPflanzen3`). Spalte `osc_list_name` ist nur Referenz.

| Cue-Nummer | Beispiel-Clip |
|------------|---------------|
| `KI_RZ21.Clyde` | Clyde auf RZ21 |
| `KI_RZ21.BAK1_Nicolas_Pflanzen` | Avatar BAK1 (Alias!) |
| `KI_RZ21.AffenSlowOdysee` | Atmosphäre ohne Avatar |

Für den Start reicht oft nur **ein** Projektor (`qlab_cue_list_rz21.csv`). Theatermaschine schickt bei Standard-Clips vier Befehle — fehlende Cues in QLab werden ignoriert.

### Viele Cues auf einmal anlegen (schnellster Weg)

QLab hat keinen CSV-Import. Zwei praktische Wege:

**A) Python-Importer (empfohlen)** — zuverlässiger als reines AppleScript:

```bash
make qlab-cue-list
make qlab-import VIDEO_DIR="/Pfad/zu/deinen/Videos" SOURCE=avatar
```

Nur Avatar-Clips (Ordner wie `KI Test/Avatare`): `SOURCE=avatar` setzen — sonst sucht das Skript auch Database- und Atmosphäre-Clips, die in dem Ordner nicht liegen.

Oder direkt:

```bash
python3 tools/qlab_import_video_cues.py "/Pfad/zu/deinen/Videos" data/qlab_cue_list_rz21.csv
python3 tools/qlab_import_video_cues.py "/Pfad/zu/deinen/Videos" data/qlab_cue_list_rz21.csv --dry-run
```

Voraussetzungen: QLab offen, Ziel-Workspace im Vordergrund, Videodateien im Ordner (`.mp4`/`.mov`). Matcht Dateinamen grob an `clip_part`.

**A2) AppleScript** (Alternative):

```bash
osascript tools/qlab_import_video_cues.applescript "/Pfad/zu/deinen/Videos" "data/qlab_cue_list_rz21.csv"
```

**B) Drag & Drop + Nummern manuell** — alle Videos in QLab ziehen (erzeugt Cues 1…n), dann pro Cue im Tab **Basics** das Feld **Number** aus der CSV setzen. Für 21 Clips okay, für 100+ eher A).

**C) Bereits angelegte Cues umbenennen** — wenn du schon Cues 1–21 hast: nur **Number** je Cue aus `qlab_cue_list_rz21.csv` eintragen, Dateien können bleiben.

### Preview: Video-Stages pro Projektor

Für die Vorschau auf dem Mac alle Projektoren auf separate QLab-Stages legen:

| Cue-Präfix | Video Output Stage |
|------------|-------------------|
| `KI_RZ21.*` | Stage 1 |
| `KI_Adam.*` | Stage 2 |
| `KI_Eva.*` | Stage 3 |
| `KI_LED.*` | Stage 4 |

```bash
make qlab-stages
```

QLab muss offen sein. Das Skript setzt bei allen **Video Cues** die `stage number` anhand der Cue-Nummer. Nach neuem Import erneut ausführen.

In QLab unter **Workspace Settings → Video → Video Outputs** sollten Stage 1–4 auf verschiedene Bildschirme/Fenster geroutet sein (z. B. vier Audition-Fenster oder Monitor-Layouts).

### Video-Ausgabe

- **Video Output Patch** auf Mac-Bildschirm oder Test-Monitor
- Workspace nicht auf Pause/Panic

### Manueller QLab-Test (ohne Relay)

```bash
echo "/cue/KI_RZ21.Clyde/start" | nc -u -w1 127.0.0.1 53535
```

Wenn der Cue startet, ist QLab korrekt konfiguriert.

---

## 3. Relay starten

```bash
make qlab-relay
```

Oder direkt:

```bash
cd backend && .venv/bin/python ../tools/pixera_qlab_relay.py -v
```

Umgebungsvariablen (optional):

| Variable | Standard | Bedeutung |
|----------|----------|-----------|
| `PIXERA_LISTEN_HOST` | `127.0.0.1` | Relay lauscht hier |
| `PIXERA_LISTEN_PORT` | `8990` | = `PIXERA_OSC_PORT` im Backend |
| `QLAB_HOST` | `127.0.0.1` | QLab-Mac |
| `QLAB_PORT` | `53000` | QLab OSC-Port |

Mapping:

```
/pixera/args/cue/apply  "KI_RZ21.Clyde"  →  /cue/KI_RZ21.Clyde/start
```

---

## 4. Test-Ablauf

1. QLab mit Test-Cues öffnen
2. `make qlab-relay` (eigenes Terminal)
3. `make run` (Backend nativ)
4. Browser: http://localhost:3003/technik
5. Clip wählen (z. B. `clyde`) → **Video senden**
6. Prüfen:
   - `logs/osc.log` — `[pixera] → 127.0.0.1:8990 /pixera/args/cue/apply 'KI_RZ21.Clyde'`
   - Relay-Terminal — `relay ... -> /cue/KI_RZ21.Clyde/start`
   - QLab — Video startet

---

## 5. Auf der Bühne umschalten

1. Relay beenden (Ctrl+C)
2. In `backend/.env`:

```env
PIXERA_OSC_HOST=172.27.27.1
PIXERA_OSC_PORT=8990
```

3. Backend neu starten

Gleicher Katalog (`video_cues.json`), gleiche Inszenierung — nur das Ziel ändert sich. QLab auf der Bühne ist nicht nötig, wenn Pixera die Videos ausspielt.

---

## Was nicht funktioniert

| Ansatz | Problem |
|--------|---------|
| `PIXERA_OSC_PORT=53000` ohne Relay | Falsches OSC-Format für QLab |
| `OSC_DRY_RUN=true` | Nur Logging, kein UDP |
| `VISUAL_OUTPUT=touchdesigner` | Andere Adressen (`/visual/play_clip`) |
| QLab „OSC Controls“ | Nur Workspace-Aktionen, nicht pro Video-Cue |
