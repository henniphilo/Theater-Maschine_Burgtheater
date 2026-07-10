"""Tests for background Teil-2 prepare jobs."""

from __future__ import annotations

import asyncio

import pytest

from app.schemas.inszenierung import PatchCorpusRequest
from app.services.inszenierung_store import get_inszenierung_store
from app.services.teil2_prepare_job import Teil2PrepareJobService
from app.services.teil2_prepare_service import Teil2PrepareService


@pytest.mark.asyncio
async def test_prepare_job_sets_ready_status(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.director_dramaturgy_mode", "rules")
    store = get_inszenierung_store()
    corpus = store.create("Job Test")
    store.patch(
        corpus.id,
        PatchCorpusRequest(script_text="23. Der Delphin spricht.\n\n24. Der Bärenklauer folgt.\n"),
    )

    service = Teil2PrepareJobService()
    prepare = Teil2PrepareService()
    monkeypatch.setattr(
        "app.services.teil2_prepare_job.get_teil2_prepare_service",
        lambda: prepare,
    )
    service.start(corpus.id)

    for _ in range(80):
        updated = store.get(corpus.id)
        if updated.status == "ready":
            assert updated.teil2_plan is not None
            assert updated.teil2_plan.cue_overview is not None
            assert updated.prepare_phase is None
            return
        if updated.prepare_error:
            pytest.fail(updated.prepare_error)
        await asyncio.sleep(0.05)
    pytest.fail("prepare did not finish")


@pytest.mark.asyncio
async def test_prepare_job_rejects_double_start():
    store = get_inszenierung_store()
    corpus = store.create("Dup")
    store.patch(corpus.id, PatchCorpusRequest(script_text="Ein Satz reicht."))
    store.set_preparing(corpus.id)
    service = Teil2PrepareJobService()
    with pytest.raises(ValueError, match="bereits"):
        service.start(corpus.id)
