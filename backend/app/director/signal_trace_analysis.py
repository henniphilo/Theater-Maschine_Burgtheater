"""Drop classification for signal trace events (Phase 4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DropReport:
    command_id: str
    logical_signal_id: str | None
    drop_class: str
    detail: str = ""


_LIFECYCLE = (
    "command.built",
    "queue.enqueued",
    "queue.dequeued",
    "command.send_attempted",
    "command.send_completed",
    "command.send_failed",
    "command.dry_run_suppressed_send",
    "receiver.seen",
)


def _events_by_command(events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        command_id = event.get("command_id")
        if not command_id:
            continue
        grouped.setdefault(str(command_id), []).append(event)
    return grouped


def classify_command_drops(events: list[dict[str, Any]]) -> list[DropReport]:
    """Classify missing lifecycle stages per command_id."""
    reports: list[DropReport] = []
    seen_ids: dict[str, int] = {}
    by_command = _events_by_command(events)

    for command_id, command_events in by_command.items():
        seen_ids[command_id] = seen_ids.get(command_id, 0) + 1
        event_names = {e.get("event") for e in command_events}
        logical_signal_id = next(
            (str(e["logical_signal_id"]) for e in command_events if e.get("logical_signal_id")),
            None,
        )

        if "command.built" not in event_names:
            reports.append(
                DropReport(
                    command_id=command_id,
                    logical_signal_id=logical_signal_id,
                    drop_class="planned_not_built",
                )
            )
            continue

        has_enqueue = "queue.enqueued" in event_names
        has_sync_send = "command.send_attempted" in event_names and not has_enqueue
        if not has_enqueue and not has_sync_send:
            reports.append(
                DropReport(
                    command_id=command_id,
                    logical_signal_id=logical_signal_id,
                    drop_class="built_not_enqueued",
                )
            )
            continue

        if has_enqueue and "queue.dequeued" not in event_names:
            reports.append(
                DropReport(
                    command_id=command_id,
                    logical_signal_id=logical_signal_id,
                    drop_class="enqueued_not_dequeued",
                )
            )
            continue

        if has_enqueue and "queue.dequeued" in event_names and "command.send_attempted" not in event_names:
            reports.append(
                DropReport(
                    command_id=command_id,
                    logical_signal_id=logical_signal_id,
                    drop_class="dequeued_not_attempted",
                )
            )
            continue

        if "command.send_failed" in event_names:
            reports.append(
                DropReport(
                    command_id=command_id,
                    logical_signal_id=logical_signal_id,
                    drop_class="attempted_failed",
                )
            )
            continue

        completed = "command.send_completed" in event_names or "command.dry_run_suppressed_send" in event_names
        if completed and "receiver.seen" not in event_names and not any(
            e.get("event") == "midi.send_logged" for e in command_events
        ):
            if any(e.get("bridge") == "sound" for e in command_events):
                reports.append(
                    DropReport(
                        command_id=command_id,
                        logical_signal_id=logical_signal_id,
                        drop_class="sent_not_received",
                        detail="midi_no_receiver",
                    )
                )
            elif "command.send_completed" in event_names:
                reports.append(
                    DropReport(
                        command_id=command_id,
                        logical_signal_id=logical_signal_id,
                        drop_class="sent_not_received",
                    )
                )

    for command_id, count in seen_ids.items():
        if count > 1:
            reports.append(
                DropReport(
                    command_id=command_id,
                    logical_signal_id=None,
                    drop_class="duplicate_command_id",
                    detail=f"count={count}",
                )
            )

    barrier_events = [e for e in events if e.get("event") == "run.barrier_created"]
    if barrier_events:
        last_barrier_mono = max(e.get("ts_mono_ms", 0) for e in barrier_events)
        for command_id, command_events in by_command.items():
            send_events = [
                e
                for e in command_events
                if e.get("event") in {"command.send_completed", "command.send_attempted"}
            ]
            if send_events and max(e.get("ts_mono_ms", 0) for e in send_events) > last_barrier_mono:
                logical_signal_id = next(
                    (str(e["logical_signal_id"]) for e in command_events if e.get("logical_signal_id")),
                    None,
                )
                reports.append(
                    DropReport(
                        command_id=command_id,
                        logical_signal_id=logical_signal_id,
                        drop_class="late_stale_signal",
                    )
                )

    return reports
