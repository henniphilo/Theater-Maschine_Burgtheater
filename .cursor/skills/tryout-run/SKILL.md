---
name: tryout-run
description: >-
  Run automated probe show (prepare-tryout + script cues via API + signal analysis).
  Use before a live show, for regression checks, or to validate Director/OSC fixes.
disable-model-invocation: true
---

# Tryout Run

Automated probe to fire script cues and analyze signal delivery.

## Prerequisites

1. Backend running: `make run` (or existing native backend on port 8000)
2. Director enabled, signal trace on (default in native mode)

## Run

```bash
make run-tryout
```

This executes:

1. `prepare-tryout` — archives logs, resets trace, prepares director for probe mode
2. `run_tryout_api.py --max-cues 12` — fires script cues via API
3. `analyze-signal-trace` — prints drop report

## Manual steps (if make fails)

```bash
cd backend && .venv/bin/python scripts/prepare_tryout_run.py
cd backend && .venv/bin/python scripts/run_tryout_api.py --max-cues 12
make analyze-signal-trace
make visualize-logs
```

## Interpret results

- **No drops** — probe passed; spot-check `logs/show_timeline.png` for timing
- **Drops reported** — invoke `debug-signal-drops` skill for classification
- **API connection refused** — start backend first with `make run`

## After fixing issues

Re-run tryout and relevant tests:

```bash
make run-tryout
make test-backend
# if frontend timing changed:
make test-frontend
```

## Related

- Skill: `debug-signal-drops`
- Script: `backend/scripts/run_tryout_api.py`
- Script: `backend/scripts/prepare_tryout_run.py`
