"""ETC EOS OSC helpers for Unter Tieren (Kanal-Übersicht).

ETC syntax (see OSC Dictionary):
  /eos/chan/71  + arg 62   → channel 71 intensity 62 %
  /eos/chan/71/full        → channel 71 to fixture Full level
  /eos/group/2  + arg 50   → group 2 intensity 50 %

``/eos/chan/N/at`` is NOT a valid EOS channel-level command (``/at`` is the keypad).
"""

from __future__ import annotations

import re
from typing import Any

EOS_CHAN_LEVEL = "/eos/chan/{channel}"
EOS_CHAN_FULL = "/eos/chan/{channel}/full"
EOS_GROUP_LEVEL = "/eos/group/{group}"
EOS_GROUP_FULL = "/eos/group/{group}/full"
EOS_KEY_OUT = "/eos/key/out"
EOS_CHAN_ADDRESS_RE = re.compile(r"^/eos/chan/(\d+)(?:/(full))?$")
EOS_CHAN_LEGACY_RE = re.compile(r"^/eos/chan/(\d+)/at$")
EOS_GROUP_ADDRESS_RE = re.compile(r"^/eos/group/(\d+)(?:/(full|level))?$")


def expand_channels(specs: list[str]) -> list[int]:
    """Expand channel specs like 11-19, 92+94, 6 into sorted unique channel numbers."""
    channels: list[int] = []
    for spec in specs:
        token = spec.strip()
        if not token:
            continue
        if re.fullmatch(r"\d+\s*-\s*\d+", token):
            start_s, end_s = re.split(r"\s*-\s*", token, maxsplit=1)
            start_n, end_n = int(start_s), int(end_s)
            if start_n > end_n:
                start_n, end_n = end_n, start_n
            channels.extend(range(start_n, end_n + 1))
            continue
        for part in re.split(r"\s*\+\s*", token):
            part = part.strip()
            if part:
                channels.append(int(part))
    return sorted(set(channels))


def light_intensity_to_percent(intensity: float) -> int:
    """Map normalized intensity 0–1 to EOS percentage 0–100."""
    return max(0, min(100, round(float(intensity) * 100)))


def eos_chan_full(channel: int) -> tuple[str, list[float]]:
    return EOS_CHAN_FULL.format(channel=channel), []


def eos_chan_level(channel: int, intensity: float = 1.0) -> tuple[str, list[float]]:
    """Set channel intensity — ETC: /eos/chan/N with percent arg (0–100)."""
    percent = light_intensity_to_percent(intensity)
    if percent >= 100:
        return eos_chan_full(channel)
    return EOS_CHAN_LEVEL.format(channel=channel), [float(percent)]


def eos_group_level(group: int, intensity: float = 1.0) -> tuple[str, list[float]]:
    percent = light_intensity_to_percent(intensity)
    if percent >= 100:
        return EOS_GROUP_FULL.format(group=group), []
    return EOS_GROUP_LEVEL.format(group=group), [float(percent)]


def eos_key_out() -> tuple[str, list[str]]:
    return EOS_KEY_OUT, []


def parse_eos_chan_address(address: str) -> int | None:
    parsed = parse_eos_chan_command(address)
    if parsed is None:
        return None
    return parsed[0]


def parse_eos_chan_command(address: str, args: list[Any] | None = None) -> tuple[int, float] | None:
    match = EOS_CHAN_ADDRESS_RE.match(address)
    if match:
        channel = int(match.group(1))
        if match.group(2) == "full":
            return channel, 1.0
        if args:
            return channel, float(args[0]) / 100.0
        return channel, 1.0

    legacy = EOS_CHAN_LEGACY_RE.match(address)
    if legacy and args:
        return int(legacy.group(1)), float(args[0]) / 100.0
    return None


def parse_eos_group_command(address: str, args: list[Any] | None = None) -> tuple[int, float] | None:
    match = EOS_GROUP_ADDRESS_RE.match(address)
    if not match:
        return None
    group = int(match.group(1))
    kind = match.group(2)
    if kind == "full":
        return group, 1.0
    if args:
        return group, float(args[0]) / 100.0
    if kind == "level":
        return group, 1.0
    return group, 1.0
