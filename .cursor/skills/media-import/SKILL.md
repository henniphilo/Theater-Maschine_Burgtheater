---
name: media-import
description: >-
  Regenerate video/avatar catalogs from CSV or Numbers sources. Use when updating
  OSC command lists, video_cues.json, avatar_speech.json, or media/video mappings.
disable-model-invocation: true
---

# Media Import

Regenerate catalogs from source spreadsheets and OSC command lists.

## Avatar import

Maps avatar text assignments to speech catalog and OSC lists:

```bash
make avatar-import
```

Script: `backend/scripts/import_avatar_textzuordnung.py`

Outputs (typical):

- `data/avatar_speech.json`
- `media/video/OSCBefehllisteAvatare.txt`
- Related CSV mappings under `media/video/`

## Video / atmosphere import

Maps video assignments to atmosphere cues (non-avatar clips):

```bash
make video-import
```

Script: `backend/scripts/import_video_zuordnung.py`

Outputs (typical):

- `data/video_cues.json`
- `media/video/OSCBefehllisteOhneAvatare.txt`

## Prerequisites

- Source files present locally (`Textzuordnung.numbers`, `Videozuordnung.numbers` or exported CSV)
- `media/video/` may not be in git — verify files exist before import
- Backend venv: `cd backend && .venv/bin/pip install -e ".[dev]"`

## After import

1. Verify catalog counts:

```bash
make avatar-catalog
```

2. Run catalog tests:

```bash
cd backend && ./run-tests.sh -q tests/test_video_cue_catalog.py tests/test_teil2_atmosphere_cues.py
```

3. Spot-check one entry in `data/video_cues.json` or `data/avatar_speech.json`

## OSC command list files

| File | Purpose |
|------|---------|
| `media/video/OSCBefehllisteAvatare.txt` | Avatar video cues |
| `media/video/OSCBefehllisteOhneAvatare.txt` | Atmosphere B-roll |
| `OSCBefehlliste.txt` (repo root) | Legacy combined list |

Do not hand-edit generated JSON without updating the import source — changes will be overwritten on next import.

## Rule reference

See `.cursor/rules/50-data-media.mdc` for data directory conventions.
