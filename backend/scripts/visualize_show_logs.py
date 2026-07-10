#!/usr/bin/env python3
"""Visualisiert Show-Ausgaben als lesbare Sendereihenfolge pro Ausgang.

Primärquelle: ``logs/signal_trace.jsonl`` (letzter Durchlauf per ``run_id``).
Fallback: ``logs/osc.log`` (letzte Session per Zeitlücke).

Beispiel::

    make visualize-logs

    python scripts/visualize_show_logs.py \\
        --trace ../logs/signal_trace.jsonl \\
        --last-run \\
        -o ../logs/show_timeline.png
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

OSC_LINE = re.compile(
    r"^\[(OSC) (DRY-RUN|SEND)(?: \+([0-9.]+)s)?(?: q=(?P<queue>\d+))?\] "
    r"\[(?P<bridge>\w+)\] → (?P<target>\S+) (?P<rest>.+)$"
)
MIDI_LINE = re.compile(
    r"^\[MIDI (DRY-RUN|SEND)\] \[(?P<bridge>\w+)\] → (?P<port>.+?) "
    r"(?P<msg>note_on|note_off) ch=(?P<ch>\d+) note=(?P<note>\d+)(?: vel=(?P<vel>\d+))?"
)
QUEUE_LINE = re.compile(
    r"^\[OSC QUEUE\] (?P<kind>enqueue|done) "
    r"(?:depth=(?P<depth>\d+) cmds=(?P<cmds>\d+) stagger=(?P<stagger>\w+)"
    r"|waited_ms=(?P<waited>[\d.]+) sent=(?P<sent>\d+))"
)
PIXERA_CUE = re.compile(r"'([^']+)'")
LIGHT_SCENE = re.compile(r"/light/set_scene\s+'([^']+)'", re.I)
MIDI_NOTE = re.compile(r"note=(?P<note>\d+)")
AVATAR_PREFIX = re.compile(r"^(BAK|BK|SCH|MO|PET|WO|DEL|LG)\d", re.I)

PROJECTOR_PREFIXES: tuple[tuple[str, str], ...] = (
    ("KI_Adam.", "adam"),
    ("KI_Eva.", "eva"),
    ("KI_RZ21.", "rz21"),
    ("KI_LED.", "led"),
)

LANE_ORDER = ("video:adam", "video:eva", "video:rz21", "video:led", "sound", "light")


@dataclass(frozen=True)
class TimelineEvent:
    t: float
    lane: str
    category: str
    label: str
    detail: str = ""
    intensity: float | None = None
    dry_run: bool = True
    source: str = "osc"
    global_seq: int = 0
    run_id: str = ""


@dataclass
class ParseResult:
    events: list[TimelineEvent] = field(default_factory=list)
    queue_markers: list[tuple[float, int]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    run_id: str | None = None
    run_started_at: str | None = None


def _repo_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


def resolve_signal_trace_path(explicit: Path | None = None) -> Path | None:
    if explicit is not None:
        p = _repo_path(explicit)
        return p if p.is_file() else None
    for candidate in (
        REPO_ROOT / "logs" / "signal_trace.jsonl",
        REPO_ROOT / "backend" / "logs" / "signal_trace.jsonl",
    ):
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
    return None


def load_sound_note_labels(data_dir: Path | None = None) -> dict[int, str]:
    data_dir = data_dir or _repo_path("data")
    path = data_dir / "sound_cues.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[int, str] = {}
    for cue in payload.get("cues") or []:
        note = cue.get("midi_note")
        cue_id = cue.get("id")
        if isinstance(note, int) and isinstance(cue_id, str):
            out[note] = cue_id
    return out


def _projector_from_pixera_cue(cue_name: str) -> tuple[str, str]:
    for prefix, projector in PROJECTOR_PREFIXES:
        if cue_name.startswith(prefix):
            return projector, cue_name[len(prefix) :]
    if "." in cue_name:
        head, tail = cue_name.split(".", 1)
        return head.replace("KI_", "").lower(), tail
    return "video", cue_name


def _lane_display(lane: str) -> str:
    return lane.replace("video:", "beamer ").replace("rz21", "RZ21").replace("led", "LED")


def _is_avatar_label(label: str) -> bool:
    return bool(AVATAR_PREFIX.match(label))


def _is_light_noise(rest: str) -> bool:
    lowered = rest.lower()
    if "tcp/connect" in lowered or "tcp/disconnect" in lowered:
        return True
    if "/eos/chan/" in lowered and "/light/set_scene" not in lowered:
        return True
    if "/eos/key/" in lowered:
        return True
    return False


def find_last_run_id(trace_path: Path) -> tuple[str | None, str | None]:
    last_run_id: str | None = None
    last_started_at: str | None = None
    if not trace_path.is_file():
        return None, None
    for line in trace_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("event") == "run.started" and isinstance(entry.get("run_id"), str):
            last_run_id = entry["run_id"]
            last_started_at = entry.get("ts_wall")
    return last_run_id, last_started_at


def parse_signal_trace(
    path: Path,
    *,
    run_id: str | None = None,
    note_labels: dict[int, str] | None = None,
) -> ParseResult:
    note_labels = note_labels or {}
    result = ParseResult()
    if not path.is_file():
        result.warnings.append(f"Signal-Trace nicht gefunden: {path}")
        return result

    if run_id is None:
        run_id, result.run_started_at = find_last_run_id(path)
    result.run_id = run_id
    if not run_id:
        result.warnings.append("Kein run.started im Signal-Trace — nutze --run-id oder osc.log")
        return result

    built_by_command: dict[str, dict] = {}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("run_id") != run_id:
            continue
        if entry.get("event") == "command.built" and isinstance(entry.get("command_id"), str):
            built_by_command[entry["command_id"]] = entry

    seq = 0
    run_started_at = result.run_started_at
    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        event_name = entry.get("event")
        if event_name == "run.started" and entry.get("run_id") == run_id:
            run_started_at = entry.get("ts_wall") or run_started_at

        if event_name != "command.send_attempted":
            continue
        if entry.get("run_id") != run_id:
            continue

        built = built_by_command.get(str(entry.get("command_id") or ""), {})
        bridge = str(entry.get("bridge") or built.get("bridge") or "")
        args = built.get("args") or entry.get("args") or []
        address = str(built.get("address") or entry.get("address") or "")
        dry_run = bool(entry.get("dry_run", built.get("dry_run", True)))
        ts_wall = entry.get("ts_wall")
        t = _wall_to_seconds(ts_wall, run_started_at)

        event: TimelineEvent | None = None
        if bridge == "pixera" and address.endswith("/pixera/args/cue/apply"):
            cue_name = str(args[0]) if args else ""
            if not cue_name:
                continue
            projector, clip = _projector_from_pixera_cue(cue_name)
            event = TimelineEvent(
                t=t,
                lane=f"video:{projector}",
                category="video",
                label=clip,
                detail=cue_name,
                dry_run=dry_run,
                source="trace",
                global_seq=seq,
                run_id=run_id,
            )
        elif bridge == "sound":
            if args and isinstance(args[0], str):
                label = args[0]
            else:
                label = address or "sound"
            event = TimelineEvent(
                t=t,
                lane="sound",
                category="sound",
                label=label,
                detail=address,
                dry_run=dry_run,
                source="trace",
                global_seq=seq,
                run_id=run_id,
            )
        elif bridge == "light":
            if _is_light_noise(address):
                continue
            scene = LIGHT_SCENE.search(address)
            if scene:
                label = scene.group(1)
            elif args and isinstance(args[0], str):
                label = args[0]
            else:
                label = address.rsplit("/", 1)[-1] or "light"
            event = TimelineEvent(
                t=t,
                lane="light",
                category="light",
                label=label,
                detail=address,
                dry_run=dry_run,
                source="trace",
                global_seq=seq,
                run_id=run_id,
            )

        if event is None:
            continue
        result.events.append(event)
        seq += 1

    if run_started_at:
        result.run_started_at = run_started_at

    # MIDI nur als Fallback, wenn keine Sound-OSC-Events im Run
    if not any(e.lane == "sound" for e in result.events):
        for line in lines:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("event") != "midi.send_logged":
                continue
            ts_wall = entry.get("ts_wall")
            if run_started_at and isinstance(ts_wall, str) and ts_wall < run_started_at:
                continue
            msg = str(entry.get("midi_message") or "")
            note_match = MIDI_NOTE.search(msg)
            if not note_match:
                continue
            note = int(note_match.group("note"))
            label = note_labels.get(note, f"note {note}")
            result.events.append(
                TimelineEvent(
                    t=_wall_to_seconds(ts_wall, run_started_at),
                    lane="sound",
                    category="sound",
                    label=label,
                    detail=msg,
                    dry_run=bool(entry.get("dry_run", True)),
                    source="trace",
                    global_seq=seq,
                    run_id=run_id or "",
                )
            )
            seq += 1

    return result


def _wall_to_seconds(ts_wall: str | None, run_started_at: str | None) -> float:
    if not ts_wall or not run_started_at:
        return 0.0
    try:
        ts = datetime.fromisoformat(ts_wall.replace("Z", "+00:00"))
        t0 = datetime.fromisoformat(run_started_at.replace("Z", "+00:00"))
        return max(0.0, (ts - t0).total_seconds())
    except ValueError:
        return 0.0


def find_osc_session_start_line(path: Path, *, gap_seconds: float = 120.0) -> int:
    if not path.is_file():
        return 1
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    last_t: float | None = None
    session_start = 1
    saw_timestamp = False
    for index, line in enumerate(lines, start=1):
        osc = OSC_LINE.match(line.strip())
        if not osc or not osc.group(3):
            continue
        t = float(osc.group(3))
        if not saw_timestamp and index > 50:
            session_start = index
        if last_t is not None and t - last_t > gap_seconds:
            session_start = index
        last_t = t
        saw_timestamp = True
    return session_start


def _parse_floats(rest: str) -> list[float]:
    return [float(x) for x in re.findall(r"[-+]?\d*\.\d+|\d+", rest)]


def parse_osc_log(
    path: Path,
    *,
    note_labels: dict[int, str] | None = None,
    min_line: int = 1,
) -> ParseResult:
    note_labels = note_labels or {}
    result = ParseResult()
    if not path.is_file():
        result.warnings.append(f"OSC-Log nicht gefunden: {path}")
        return result

    fallback_t = 0.0
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    seq = 0
    for line_no, line in enumerate(lines, start=1):
        if line_no < min_line:
            continue
        line = line.strip()
        if not line:
            continue

        qm = QUEUE_LINE.match(line)
        if qm:
            if qm.group("kind") == "enqueue" and qm.group("depth"):
                result.queue_markers.append((fallback_t, int(qm.group("depth"))))
            continue

        midi = MIDI_LINE.match(line)
        if midi:
            if midi.group("msg") != "note_on":
                continue
            note = int(midi.group("note"))
            vel = int(midi.group("vel") or 0)
            label = note_labels.get(note, f"note {note}")
            result.events.append(
                TimelineEvent(
                    t=fallback_t,
                    lane="sound",
                    category="sound",
                    label=label,
                    detail=f"ch={midi.group('ch')} vel={vel}",
                    intensity=min(1.0, vel / 127.0),
                    dry_run=midi.group(1) == "DRY-RUN",
                    global_seq=seq,
                )
            )
            seq += 1
            fallback_t += 0.02
            continue

        osc = OSC_LINE.match(line)
        if not osc:
            continue

        t = float(osc.group(3)) if osc.group(3) else fallback_t
        fallback_t = t
        bridge = osc.group("bridge")
        rest = osc.group("rest")
        dry_run = osc.group(2) == "DRY-RUN"

        if bridge == "pixera" and "/pixera/args/cue/apply" in rest:
            cue_match = PIXERA_CUE.search(rest)
            if not cue_match:
                continue
            projector, clip = _projector_from_pixera_cue(cue_match.group(1))
            result.events.append(
                TimelineEvent(
                    t=t,
                    lane=f"video:{projector}",
                    category="video",
                    label=clip,
                    detail=cue_match.group(1),
                    dry_run=dry_run,
                    global_seq=seq,
                )
            )
            seq += 1
            continue

        if bridge == "light":
            if _is_light_noise(rest):
                continue
            scene = LIGHT_SCENE.search(rest)
            if scene:
                label = scene.group(1)
            elif "blackout" in rest.lower():
                label = "blackout"
            else:
                continue
            result.events.append(
                TimelineEvent(
                    t=t,
                    lane="light",
                    category="light",
                    label=label,
                    detail=rest[:80],
                    dry_run=dry_run,
                    global_seq=seq,
                )
            )
            seq += 1
            continue

        if bridge == "sound" and "/sound/" in rest:
            cue_match = PIXERA_CUE.search(rest)
            label = cue_match.group(1) if cue_match else (rest.split()[0] if rest else "sound")
            result.events.append(
                TimelineEvent(
                    t=t,
                    lane="sound",
                    category="sound",
                    label=label,
                    detail=rest[:80],
                    dry_run=dry_run,
                    global_seq=seq,
                )
            )
            seq += 1

    return result


def parse_director_log(path: Path) -> list[TimelineEvent]:
    if not path.is_file():
        return []
    events: list[TimelineEvent] = []
    t0: datetime | None = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        logged_at = entry.get("logged_at")
        if not isinstance(logged_at, str):
            continue
        try:
            ts = datetime.fromisoformat(logged_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        if t0 is None:
            t0 = ts
        t = (ts - t0).total_seconds()
        decision = entry.get("decision") or {}
        executed = bool(entry.get("executed"))
        blocked = entry.get("blocked_reason")
        suffix = "" if executed else f" (blocked: {blocked})" if blocked else " (skipped)"

        visual = decision.get("visual")
        if isinstance(visual, dict) and visual.get("clip_id"):
            projector = visual.get("projector") or "?"
            events.append(
                TimelineEvent(
                    t=t,
                    lane=f"video:{projector}",
                    category="director",
                    label=str(visual.get("clip_id")),
                    detail=f"director visual{suffix}",
                    source="director",
                )
            )
        sound = decision.get("sound")
        if isinstance(sound, dict) and sound.get("cue_id"):
            events.append(
                TimelineEvent(
                    t=t,
                    lane="sound",
                    category="director",
                    label=str(sound.get("cue_id")),
                    detail=f"director sound{suffix}",
                    source="director",
                )
            )
        light = decision.get("light")
        if isinstance(light, dict) and light.get("scene_id"):
            events.append(
                TimelineEvent(
                    t=t,
                    lane="light",
                    category="director",
                    label=str(light.get("scene_id")),
                    detail=f"director light{suffix}",
                    source="director",
                )
            )
    return events


def _lane_order(events: list[TimelineEvent]) -> list[str]:
    ordered = [lane for lane in LANE_ORDER if any(e.lane == lane for e in events)]
    extras = sorted({e.lane for e in events if e.lane not in ordered})
    return ordered + extras


def _events_by_lane(events: list[TimelineEvent]) -> dict[str, list[TimelineEvent]]:
    lanes = _lane_order(events)
    grouped: dict[str, list[TimelineEvent]] = {lane: [] for lane in lanes}
    for event in sorted(events, key=lambda e: (e.global_seq, e.t, e.lane)):
        grouped.setdefault(event.lane, []).append(event)
    return grouped


def write_lane_report(events: list[TimelineEvent], output: Path, *, run_id: str | None = None) -> None:
    grouped = _events_by_lane(events)
    lines: list[str] = []
    title_run = run_id or (events[0].run_id if events else "?")
    lines.append(f"Theatermaschine — Sendereihenfolge (Run: {title_run})")
    lines.append("")
    for lane, lane_events in grouped.items():
        if not lane_events:
            continue
        lines.append(f"## {_lane_display(lane)} ({len(lane_events)} Signale)")
        for index, event in enumerate(lane_events, start=1):
            dry = " [dry-run]" if event.dry_run else ""
            avatar = " [avatar]" if _is_avatar_label(event.label) else ""
            lines.append(f"  {index:3d}. {event.label}{avatar}{dry}")
        lines.append("")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Text-Report: {output}")


def plot_sequential_outputs(
    events: list[TimelineEvent],
    *,
    run_id: str | None = None,
    title: str | None = None,
    output: Path | None = None,
    show: bool = False,
) -> None:
    try:
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyBboxPatch
    except ImportError as exc:
        raise SystemExit(
            "matplotlib fehlt. Im Projekt-venv installieren:\n"
            "  cd backend && .venv/bin/pip install -e \".[viz]\"\n"
            "Oder: make visualize-logs"
        ) from exc

    if not events:
        raise SystemExit("Keine Events zum Plotten.")

    grouped = _events_by_lane(events)
    lanes = [lane for lane, lane_events in grouped.items() if lane_events]
    max_count = max(len(grouped[lane]) for lane in lanes)
    colors = {
        "video:adam": "#e8b84a",
        "video:eva": "#c45cff",
        "video:rz21": "#5fd4ff",
        "video:led": "#f4efe6",
        "sound": "#6fdc8c",
        "light": "#ff8c5a",
    }

    cell_w = 0.9
    fig_w = min(36.0, max(12.0, max_count * cell_w + 2.5))
    fig_h = max(4.5, len(lanes) * 1.15 + 1.5)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    fig.patch.set_facecolor("#0f0d12")
    ax.set_facecolor("#141018")
    ax.tick_params(colors="#b9b0a6")
    for spine in ax.spines.values():
        spine.set_color("#3a3340")

    for row, lane in enumerate(lanes):
        lane_events = grouped[lane]
        color = colors.get(lane, "#aaaaaa")
        for col, event in enumerate(lane_events):
            x = col * cell_w
            edge = "#ffffff" if _is_avatar_label(event.label) else color
            linewidth = 1.4 if _is_avatar_label(event.label) else 0.6
            alpha = 0.35 if event.dry_run else 0.9
            patch = FancyBboxPatch(
                (x, row - 0.36),
                cell_w * 0.92,
                0.72,
                boxstyle="round,pad=0.02,rounding_size=0.08",
                facecolor=color,
                edgecolor=edge,
                linewidth=linewidth,
                alpha=alpha,
            )
            ax.add_patch(patch)
            label = event.label if len(event.label) <= 22 else event.label[:20] + "…"
            ax.text(
                x + cell_w * 0.46,
                row,
                label,
                ha="center",
                va="center",
                fontsize=6.5,
                color="#101010" if lane != "video:led" else "#202020",
                rotation=90,
                clip_on=True,
            )
            ax.text(
                x + cell_w * 0.08,
                row + 0.42,
                str(col + 1),
                ha="left",
                va="bottom",
                fontsize=5.5,
                color="#8a8078",
            )

    ax.set_yticks(range(len(lanes)))
    ax.set_yticklabels([_lane_display(lane) for lane in lanes], color="#f4efe6")
    ax.set_ylabel("Ausgänge", color="#f4efe6")
    ax.set_xlabel("Sende-Reihenfolge (#)", color="#f4efe6")
    ax.set_xlim(-0.2, max_count * cell_w + 0.3)
    ax.set_ylim(-0.7, len(lanes) - 0.3)
    ax.grid(axis="x", color="#2a2430", alpha=0.35, linestyle="--")

    resolved_run = run_id or (events[0].run_id if events else None)
    if title is None:
        title = "Theatermaschine — Letzter Durchlauf"
        if resolved_run:
            title += f" ({resolved_run})"
    ax.set_title(title, color="#f4efe6", fontsize=13, pad=12)

    counts = ", ".join(f"{_lane_display(lane)}={len(grouped[lane])}" for lane in lanes)
    fig.text(0.01, 0.01, counts, color="#8a8078", fontsize=8)

    fig.tight_layout()
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, dpi=150, facecolor=fig.get_facecolor())
        print(f"Gespeichert: {output}")
    if show:
        plt.show()
    plt.close(fig)


def plot_timeline(
    events: list[TimelineEvent],
    *,
    queue_markers: list[tuple[float, int]] | None = None,
    title: str = "Theatermaschine — Show Timeline",
    output: Path | None = None,
    show: bool = False,
) -> None:
    try:
        import matplotlib.pyplot as plt
        from matplotlib.patches import Patch
    except ImportError as exc:
        raise SystemExit(
            "matplotlib fehlt. Im Projekt-venv installieren:\n"
            "  cd backend && .venv/bin/pip install -e \".[viz]\"\n"
            "Oder: make visualize-logs"
        ) from exc

    if not events:
        raise SystemExit("Keine Events zum Plotten — ist die Log-Datei leer?")

    lanes = _lane_order(events)
    lane_y = {lane: idx for idx, lane in enumerate(lanes)}
    t_min = min(e.t for e in events)
    t_max = max(e.t for e in events)
    pad = max(0.5, (t_max - t_min) * 0.02)
    t_min -= pad
    t_max += pad

    colors = {
        "video:adam": "#e8b84a",
        "video:eva": "#c45cff",
        "video:rz21": "#5fd4ff",
        "video:led": "#f4efe6",
        "sound": "#6fdc8c",
        "light": "#ff8c5a",
    }
    category_marker = {"video": "o", "sound": "s", "light": "D", "director": "^"}

    fig, ax_main = plt.subplots(1, 1, figsize=(14, 6))
    fig.patch.set_facecolor("#0f0d12")
    ax_main.set_facecolor("#141018")
    ax_main.tick_params(colors="#b9b0a6")
    for spine in ax_main.spines.values():
        spine.set_color("#3a3340")

    for ev in events:
        y = lane_y.get(ev.lane, 0)
        color = colors.get(ev.lane, "#aaaaaa")
        marker = category_marker.get(ev.category, "o")
        alpha = 0.45 if ev.dry_run else 0.95
        if ev.source == "director":
            alpha = 0.75
            marker = "^"
        ax_main.scatter(
            [ev.t],
            [y],
            c=color,
            marker=marker,
            s=70 if ev.source == "director" else 45,
            alpha=alpha,
            edgecolors="white" if ev.source == "director" else "none",
            linewidths=0.4,
            zorder=3,
        )
        if ev.category in {"video", "sound", "light"}:
            ax_main.annotate(
                ev.label[:28],
                (ev.t, y),
                textcoords="offset points",
                xytext=(4, 6),
                fontsize=6,
                color="#d8d0c4",
                alpha=0.9,
                rotation=35,
                ha="left",
            )

    ax_main.set_yticks(range(len(lanes)))
    ax_main.set_yticklabels([_lane_display(lane) for lane in lanes], color="#f4efe6")
    ax_main.set_ylabel("Ausgänge", color="#f4efe6")
    ax_main.set_xlabel("Zeit (s seit Log-Start)", color="#f4efe6")
    ax_main.set_title(title, color="#f4efe6", fontsize=14, pad=12)
    ax_main.grid(axis="x", color="#2a2430", alpha=0.6, linestyle="--")

    if queue_markers:
        for t, depth in queue_markers:
            ax_main.axvline(t, color="#ffffff", alpha=0.08, linewidth=1)
            ax_main.text(
                t,
                len(lanes) - 0.15,
                f"q={depth}",
                fontsize=7,
                color="#888",
                rotation=90,
                va="top",
            )

    legend_handles = [
        Patch(facecolor=colors.get("video:adam", "#e8b84a"), label="Adam"),
        Patch(facecolor=colors.get("video:eva", "#c45cff"), label="Eva"),
        Patch(facecolor=colors.get("video:rz21", "#5fd4ff"), label="RZ21"),
        Patch(facecolor=colors.get("video:led", "#f4efe6"), label="LED"),
        Patch(facecolor=colors.get("sound", "#6fdc8c"), label="Sound"),
        Patch(facecolor=colors.get("light", "#ff8c5a"), label="Licht"),
    ]
    ax_main.legend(handles=legend_handles, loc="upper right", fontsize=8, framealpha=0.2)

    fig.tight_layout()
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, dpi=150, facecolor=fig.get_facecolor())
        print(f"Gespeichert: {output}")
    if show:
        plt.show()
    plt.close(fig)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Visualisiere Theatermaschine Show-Ausgaben.")
    parser.add_argument(
        "--trace",
        type=Path,
        default=None,
        help="Signal-Trace JSONL (Default: logs/signal_trace.jsonl wenn vorhanden)",
    )
    parser.add_argument(
        "--osc",
        type=Path,
        default=Path("logs/osc.log"),
        help="Fallback: logs/osc.log",
    )
    parser.add_argument(
        "--director",
        type=Path,
        default=None,
        help="Optional: logs/director.log als Overlay (nur --mode timeline)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("logs/show_timeline.png"),
        help="PNG-Ausgabe (Default: logs/show_timeline.png)",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("logs/show_timeline.txt"),
        help="Text-Report pro Ausgang (Default: logs/show_timeline.txt)",
    )
    parser.add_argument(
        "--mode",
        choices=("sequential", "timeline"),
        default="sequential",
        help="sequential = Sendereihenfolge pro Ausgang (Default), timeline = Zeitachse",
    )
    parser.add_argument("--show", action="store_true", help="Interaktives Fenster öffnen")
    parser.add_argument(
        "--run-id",
        default=None,
        help="Nur diesen run_id aus dem Signal-Trace (Default: letzter run.started)",
    )
    parser.add_argument(
        "--all-runs",
        action="store_true",
        help="Nicht auf letzten Durchlauf beschränken (nur osc.log / timeline)",
    )
    parser.add_argument("--from", dest="t_from", type=float, default=None, help="Zeitfenster ab (s)")
    parser.add_argument("--to", dest="t_to", type=float, default=None, help="Zeitfenster bis (s)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    note_labels = load_sound_note_labels()
    events: list[TimelineEvent] = []
    run_id: str | None = None
    queue_markers: list[tuple[float, int]] = []
    warnings: list[str] = []

    trace_path = resolve_signal_trace_path(args.trace)
    use_trace = trace_path is not None and not args.all_runs

    if use_trace and trace_path is not None:
        parsed = parse_signal_trace(trace_path, run_id=args.run_id, note_labels=note_labels)
        events = list(parsed.events)
        run_id = parsed.run_id
        warnings.extend(parsed.warnings)
        if not events:
            warnings.append("Signal-Trace ohne Sende-Events — Fallback auf osc.log")
            use_trace = False

    if not use_trace:
        osc_path = _repo_path(args.osc)
        min_line = 1 if args.all_runs else find_osc_session_start_line(osc_path)
        parsed = parse_osc_log(osc_path, note_labels=note_labels, min_line=min_line)
        events = list(parsed.events)
        queue_markers = parsed.queue_markers
        warnings.extend(parsed.warnings)
        if min_line > 1 and not args.all_runs:
            warnings.append(f"OSC: nur Session ab Zeile {min_line}")

    if args.director and args.mode == "timeline":
        events.extend(parse_director_log(_repo_path(args.director)))

    if args.t_from is not None:
        events = [e for e in events if e.t >= args.t_from]
    if args.t_to is not None:
        events = [e for e in events if e.t <= args.t_to]

    for warning in warnings:
        print(warning, file=sys.stderr)

    if not events:
        print("Keine plotbaren Events.", file=sys.stderr)
        return 1

    grouped = _events_by_lane(events)
    lane_summary = ", ".join(
        f"{_lane_display(lane)}={len(grouped[lane])}" for lane in grouped if grouped[lane]
    )
    print(
        f"{len(events)} Events · {lane_summary} · "
        f"Quelle={'signal_trace' if use_trace else 'osc.log'}"
        + (f" · run={run_id}" if run_id else "")
    )

    output = _repo_path(args.output)
    report = _repo_path(args.report)

    if args.mode == "sequential":
        write_lane_report(events, report, run_id=run_id)
        plot_sequential_outputs(events, run_id=run_id, output=output, show=args.show)
    else:
        plot_timeline(
            events,
            queue_markers=queue_markers,
            title="Theatermaschine — Show Timeline",
            output=output,
            show=args.show,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
