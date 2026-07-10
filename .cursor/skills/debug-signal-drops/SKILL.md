---
name: debug-signal-drops
description: >-
  Debug missing OSC/cue signals using signal_trace.jsonl, analyze-signal-trace,
  and show timeline visualization. Use when cues are dropped, OSC does not arrive,
  or investigating show_timeline / run_epoch mismatches.
disable-model-invocation: true
---

# Debug Signal Drops

## When to use

- Cues missing during show or tryout
- OSC not reaching TouchDesigner / Pixera
- Frontend fired cue but backend trace shows drop
- Investigating `show_timeline.png` or `run_epoch` mismatches

## Step 1: Locate trace file

Check in order:

1. `logs/signal_trace.jsonl` (repo root, native backend)
2. `backend/logs/signal_trace.jsonl`
3. Archived traces from `make prepare-tryout`

If empty, ensure `SIGNAL_TRACE_ENABLED=true` and backend was restarted after config change.

## Step 2: Run analysis

```bash
make analyze-signal-trace
```

Or directly:

```bash
cd backend && .venv/bin/python scripts/analyze_signal_trace.py --trace ../logs/signal_trace.jsonl
```

Read the drop report: `drop_class`, `command_id`, counts as `send_attempted` vs `send_completed` vs `receiver.seen`.

## Step 3: Visualize timeline

```bash
make visualize-logs
```

Output: `logs/show_timeline.png`, `logs/show_timeline.txt`

## Step 4: Correlate frontend and backend

Filter trace by:

- `run_epoch` — must match between frontend playback start and backend events
- `frontend_run_id` — links frontend-initiated cues to trace rows
- `cue_id` / `logical_signal_id` — specific cue under investigation

Frontend trace export (if enabled): pass via `--frontend-export` to analyze script.

## Step 5: Classify the fix

| Symptom | Likely cause | Where to look |
|---------|--------------|---------------|
| `command.built` but no `queue.enqueued` | SafetyState filter, bridge disabled | `pipeline.py`, director API toggles |
| `enqueued` but no `dequeued` | Run epoch invalidated, queue cleared | `run_state.py`, `osc_queue.py` |
| `send_attempted` but no `send_completed` | Network/OSC host wrong | `config.py`, `OSC_HOST`, dry-run |
| `send_completed` but no `receiver.seen` | Wrong port, TD not listening | fake receiver tests, TouchDesigner setup |
| Frontend cue missing in trace | Playback timing, wrong run_epoch | `teil2TextSyncPlayback.ts` |
| Avatar early/late | char_offset vs TTS progress | `text_split.py`, `splitSentences.ts` |

## Step 6: Verify fix

```bash
make run-tryout          # automated probe (backend must be running)
make analyze-signal-trace
make test-backend      # at least test_signal_trace, test_osc_queue_trace
```

## Reference doc

Use section index only — do not load the full file:

- [docs/debug_signal_drop_plan.md](../../docs/debug_signal_drop_plan.md)

Search for: `run_epoch`, `frontend_run_id`, `queue stagger`, `SafetyState`.

## Fake receiver for isolated tests

```python
# backend/app/director/testing/fake_osc_receiver.py
```

Use in tests before enabling live OSC.
