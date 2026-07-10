"""Tests for signal trace drop classification."""

from app.director.signal_trace_analysis import classify_command_drops


def _event(event: str, command_id: str, ts: float = 1.0, **extra) -> dict:
    return {"event": event, "command_id": command_id, "ts_mono_ms": ts, **extra}


def test_classify_enqueued_not_dequeued() -> None:
    events = [
        _event("command.built", "cmd-abc-01", 1),
        _event("queue.enqueued", "cmd-abc-01", 2),
    ]
    drops = classify_command_drops(events)
    assert any(d.drop_class == "enqueued_not_dequeued" for d in drops)


def test_classify_attempted_failed() -> None:
    events = [
        _event("command.built", "cmd-abc-01", 1),
        _event("command.send_attempted", "cmd-abc-01", 2),
        _event("command.send_failed", "cmd-abc-01", 3),
    ]
    drops = classify_command_drops(events)
    assert any(d.drop_class == "attempted_failed" for d in drops)


def test_classify_late_stale_signal() -> None:
    events = [
        {"event": "run.barrier_created", "ts_mono_ms": 100},
        _event("command.built", "cmd-abc-01", 50),
        _event("command.send_completed", "cmd-abc-01", 150),
    ]
    drops = classify_command_drops(events)
    assert any(d.drop_class == "late_stale_signal" for d in drops)
