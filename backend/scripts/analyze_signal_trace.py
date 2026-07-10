#!/usr/bin/env python3
"""Analyze structured signal trace JSONL for dropped commands."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

from app.director.signal_trace_analysis import DropReport, classify_command_drops


def load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not path.is_file():
        return events
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        events.append(json.loads(line))
    return events


def _filter_run(events: list[dict[str, Any]], run_id: str | None) -> list[dict[str, Any]]:
    if not run_id:
        return events
    return [e for e in events if e.get("run_id") == run_id]


def _latency_stats(events: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    by_command: dict[str, dict[str, float]] = defaultdict(dict)
    for event in events:
        command_id = event.get("command_id")
        if not command_id:
            continue
        by_command[str(command_id)][str(event.get("event"))] = float(event.get("ts_mono_ms", 0))

    bridge_latencies: dict[str, list[float]] = defaultdict(list)
    for stages in by_command.values():
        built = stages.get("command.built")
        completed = stages.get("command.send_completed") or stages.get("command.dry_run_suppressed_send")
        if built is not None and completed is not None:
            bridge_latencies["all"].append(completed - built)

    def summarize(values: list[float]) -> dict[str, float]:
        if not values:
            return {"p50": 0.0, "p95": 0.0, "max": 0.0}
        ordered = sorted(values)
        p95_index = max(0, int(len(ordered) * 0.95) - 1)
        return {
            "p50": round(median(ordered), 2),
            "p95": round(ordered[p95_index], 2),
            "max": round(max(ordered), 2),
        }

    return {bridge: summarize(values) for bridge, values in bridge_latencies.items()}


def summarize_run(events: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = defaultdict(int)
    logical_signals: set[str] = set()
    for event in events:
        counts[str(event.get("event", ""))] += 1
        if event.get("logical_signal_id"):
            logical_signals.add(str(event["logical_signal_id"]))

    drops = classify_command_drops(events)
    run_epoch = next((e.get("run_epoch") for e in events if e.get("run_epoch") is not None), "?")
    run_id = next((e.get("run_id") for e in events if e.get("run_id")), "?")

    return {
        "run_id": run_id,
        "run_epoch": run_epoch,
        "logical_signals": len(logical_signals),
        "commands_built": counts.get("command.built", 0),
        "enqueued": counts.get("queue.enqueued", 0),
        "dequeued": counts.get("queue.dequeued", 0),
        "send_attempted": counts.get("command.send_attempted", 0),
        "send_completed": counts.get("command.send_completed", 0),
        "send_failed": counts.get("command.send_failed", 0),
        "receiver_seen": counts.get("receiver.seen", 0),
        "drops": drops,
        "latency": _latency_stats(events),
    }


def format_report(summary: dict[str, Any]) -> str:
    lines = [
        f"Run {summary['run_id']} epoch={summary['run_epoch']}",
        f"logical_signals: {summary['logical_signals']}",
        f"commands_built: {summary['commands_built']}",
        f"enqueued: {summary['enqueued']}",
        f"dequeued: {summary['dequeued']}",
        f"send_attempted: {summary['send_attempted']}",
        f"send_completed: {summary['send_completed']}",
        f"send_failed: {summary['send_failed']}",
        f"receiver_seen: {summary['receiver_seen']}",
        "",
        "Top drops:",
    ]
    drops: list[DropReport] = summary["drops"]
    if not drops:
        lines.append("- (none)")
    else:
        for drop in drops[:20]:
            detail = f" ({drop.detail})" if drop.detail else ""
            lines.append(f"- {drop.command_id}: {drop.drop_class}{detail}")
    latency = summary.get("latency", {}).get("all")
    if latency:
        lines.extend(
            [
                "",
                f"Latency built→send p50={latency['p50']}ms p95={latency['p95']}ms max={latency['max']}ms",
            ]
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze signal_trace.jsonl for command drops")
    parser.add_argument("--trace", type=Path, required=True, help="Path to signal_trace.jsonl")
    parser.add_argument("--run-id", type=str, default=None, help="Filter by run_id")
    parser.add_argument("--frontend-export", type=Path, default=None, help="Optional frontend JSONL export")
    args = parser.parse_args()

    events = load_events(args.trace)
    if args.frontend_export:
        events.extend(load_events(args.frontend_export))
    events = _filter_run(events, args.run_id)
    print(format_report(summarize_run(events)))


if __name__ == "__main__":
    main()
