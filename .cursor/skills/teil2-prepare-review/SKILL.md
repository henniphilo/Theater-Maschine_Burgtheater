---
name: teil2-prepare-review
description: >-
  Review Teil 2 prepare/alignment changes for sentence splits, avatar char offsets,
  atmosphere cues, and alignment warnings. Use when editing teil2_prepare_service,
  text alignment, or avatar segment logic.
disable-model-invocation: true
---

# Teil 2 Prepare Review

Checklist before merging changes to Teil 2 prepare or alignment.

## Sentence split consistency

- [ ] `backend/app/services/text_split.py` unchanged OR synced with `frontend/lib/text/splitSentences.ts`
- [ ] `sentence_char_starts` in plan match `split_sentences(script_text)` output
- [ ] `script_splitter.py` not used for Teil 2 offsets

## Avatar segments

- [ ] Each `avatar_segments[].char_offset` points to valid text in `script_text`
- [ ] `start_sentence_index` / `end_sentence_index` align with char offsets
- [ ] Missing CSV lines appear in `alignment_warnings` (not silently dropped)

## Dramaturgy & atmosphere

- [ ] `dramaturgy.cue_points` reference valid sentence indices
- [ ] `atmosphere_cue_points` use `trigger: time` and valid clip IDs from `OSCBefehllisteOhneAvatare.txt`
- [ ] Projector routing respects avatar-reserved beamers (`teil2_dramaturgy_routing.py`)

## Prepare job

- [ ] `POST .../prepare` stays async (202) — no blocking LLM in request handler
- [ ] `prepare_phase` transitions: idle → preparing → ready (or error)
- [ ] Errors surface in `prepare_error` without corrupting corpus

## Tests to run

```bash
cd backend && ./run-tests.sh -q tests/test_teil2_prepare_service.py tests/test_teil2_text_alignment.py tests/test_teil2_atmosphere_cues.py tests/test_teil2_atmosphere_scheduler.py tests/test_teil2_cue_overview.py
cd frontend && npm test -- --run features/inszenierung/teil2TextSyncPlayback.test.ts
```

## Manual spot-check

1. Pick one inszenierung: `data/inszenierungen/{id}.json`
2. Verify `cue_overview` badges match `script_text` visually
3. If possible, run one sentence in `/inszenierung/auffuehrung` probe mode

## Docs

- [docs/teil2_inszenierung.md](../../docs/teil2_inszenierung.md)
