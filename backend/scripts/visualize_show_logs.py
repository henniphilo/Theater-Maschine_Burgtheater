#!/usr/bin/env python3
"""Visualisiert Show-Logs (Video/Beamer, Sound, Licht) als Matplotlib-Timeline.

Liest primär ``logs/osc.log`` (OSC + MIDI) und optional ``logs/director.log`` (JSON).

Beispiel::

    cd backend
    source .venv/bin/activate   # oder: backend/.venv/bin/pip install -e ".[viz]"
    pip install -e ".[viz]"

    python scripts/visualize_show_logs.py \\
        --osc ../logs/osc.log \\
        -o ../logs/show_timeline.png

    # Oder vom Projektroot:
    make visualize-logs
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
EOS_CHAN = re.compile(r"/eos/chan/(\d+)")
EOS_GROUP = re.compile(r"/eos/group/(\d+)")

PROJECTOR_PREFIXES: tuple[tuple[str, str], ...] = (
    ("KI_Adam.", "adam"),
    ("KI_Eva.", "eva"),
    ("KI_RZ21.", "rz21"),
    ("KI_LED.", "led"),
)


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


@dataclass
class ParseResult:
    events: list[TimelineEvent] = field(default_factory=list)
    queue_markers: list[tuple[float, int]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _repo_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


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


def _parse_floats(rest: str) -> list[float]:
    return [float(x) for x in re.findall(r"[-+]?\d*\.\d+|\d+", rest)]


def parse_osc_log(path: Path, *, note_labels: dict[int, str] | None = None) -> ParseResult:
    note_labels = note_labels or {}
    result = ParseResult()
    if not path.is_file():
        result.warnings.append(f"OSC-Log nicht gefunden: {path}")
        return result

    fallback_t = 0.0
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line_no, line in enumerate(lines, start=1):
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
                )
            )
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
                )
            )
            continue

        if bridge == "light":
            chan = EOS_CHAN.search(rest)
            group = EOS_GROUP.search(rest)
            floats = _parse_floats(rest)
            level = floats[-1] if floats else None
            if chan:
                target = f"ch {chan.group(1)}"
            elif group:
                target = f"group {group.group(1)}"
            elif "blackout" in rest.lower() or "disconnect" in rest.lower():
                target = "desk"
            else:
                target = "eos"
            result.events.append(
                TimelineEvent(
                    t=t,
                    lane="light",
                    category="light",
                    label=target,
                    detail=rest[:80],
                    intensity=level,
                    dry_run=dry_run,
                )
            )
            continue

        if bridge == "sound" and "/sound/" in rest:
            result.events.append(
                TimelineEvent(
                    t=t,
                    lane="sound",
                    category="sound",
                    label=rest.split()[0] if rest else "sound",
                    detail=rest[:80],
                    dry_run=dry_run,
                )
            )

    result.events.sort(key=lambda e: (e.t, e.lane, e.label))
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
    video_lanes = sorted({e.lane for e in events if e.lane.startswith("video:")})
    ordered = video_lanes + ["sound", "light"]
    extras = sorted({e.lane for e in events if e.lane not in ordered})
    return [lane for lane in ordered + extras if any(e.lane == lane for e in events)]


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

    fig, (ax_main, ax_light) = plt.subplots(
        2,
        1,
        figsize=(14, 8),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1.2]},
    )
    fig.patch.set_facecolor("#0f0d12")
    for ax in (ax_main, ax_light):
        ax.set_facecolor("#141018")
        ax.tick_params(colors="#b9b0a6")
        for spine in ax.spines.values():
            spine.set_color("#3a3340")

    for ev in events:
        if ev.category == "light" and ev.intensity is not None:
            continue
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
        if ev.category in {"video", "sound"}:
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
    ax_main.set_yticklabels([lane.replace("video:", "beamer ") for lane in lanes], color="#f4efe6")
    ax_main.set_ylabel("Ausgänge", color="#f4efe6")
    ax_main.set_title(title, color="#f4efe6", fontsize=14, pad=12)
    ax_main.grid(axis="x", color="#2a2430", alpha=0.6, linestyle="--")

    light_points = [(e.t, e.intensity) for e in events if e.category == "light" and e.intensity is not None]
    if light_points:
        times, levels = zip(*light_points)
        ax_light.scatter(times, levels, c="#ff8c5a", s=18, alpha=0.7)
        ax_light.plot(times, levels, color="#ff8c5a", alpha=0.25, linewidth=1)
    ax_light.set_ylabel("Licht\nIntensität", color="#f4efe6", fontsize=9)
    ax_light.set_ylim(-0.05, 1.05)
    ax_light.set_xlabel("Zeit (s seit Log-Start)", color="#f4efe6")
    ax_light.grid(axis="x", color="#2a2430", alpha=0.6, linestyle="--")

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
    parser = argparse.ArgumentParser(description="Visualisiere Theatermaschine OSC/MIDI Logs.")
    parser.add_argument(
        "--osc",
        type=Path,
        default=Path("logs/osc.log"),
        help="Pfad zu logs/osc.log (Default: logs/osc.log)",
    )
    parser.add_argument(
        "--director",
        type=Path,
        default=None,
        help="Optional: logs/director.log als Overlay (Regie-Entscheidungen)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("logs/show_timeline.png"),
        help="PNG-Ausgabe (Default: logs/show_timeline.png)",
    )
    parser.add_argument("--show", action="store_true", help="Interaktives Fenster öffnen")
    parser.add_argument("--from", dest="t_from", type=float, default=None, help="Zeitfenster ab (s)")
    parser.add_argument("--to", dest="t_to", type=float, default=None, help="Zeitfenster bis (s)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    osc_path = _repo_path(args.osc)
    note_labels = load_sound_note_labels()

    parsed = parse_osc_log(osc_path, note_labels=note_labels)
    events = list(parsed.events)

    if args.director:
        events.extend(parse_director_log(_repo_path(args.director)))

    if args.t_from is not None:
        events = [e for e in events if e.t >= args.t_from]
    if args.t_to is not None:
        events = [e for e in events if e.t <= args.t_to]

    for warning in parsed.warnings:
        print(warning, file=sys.stderr)

    if not events:
        print("Keine plotbaren Events.", file=sys.stderr)
        return 1

    print(
        f"{len(events)} Events · "
        f"{len({e.lane for e in events if e.lane.startswith('video:')})} Beamer · "
        f"Zeitspanne {min(e.t for e in events):.1f}–{max(e.t for e in events):.1f}s"
    )

    plot_timeline(
        events,
        queue_markers=parsed.queue_markers,
        output=_repo_path(args.output),
        show=args.show,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
