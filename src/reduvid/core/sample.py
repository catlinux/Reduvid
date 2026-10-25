# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Build FFmpeg commands for sampling a video without duplicating the plan."""

from __future__ import annotations

from pathlib import Path

from reduvid.core.command import build_command
from reduvid.core.plan import EncodePlan
from reduvid.core.probe import MediaInfo

SAMPLE_POSITION = 0.4


def sample_window(
    total_duration_seconds: float, duration_seconds: float = 30.0
) -> tuple[float, float]:
    """Return the (start, duration) window at 40% of the video, clamped to its end."""
    if total_duration_seconds <= 0 or duration_seconds <= 0:
        return (0.0, 0.0)
    if total_duration_seconds < duration_seconds:
        return (0.0, total_duration_seconds)
    start = total_duration_seconds * SAMPLE_POSITION
    remaining = total_duration_seconds - start
    return (start, min(duration_seconds, remaining))


def build_sample_command(
    media: MediaInfo,
    plan: EncodePlan,
    input_path: Path,
    output_path: Path,
    start_seconds: float,
    duration_seconds: float,
) -> list[str]:
    """Return the normal encoding command with a fast seek and a time limit."""
    arguments = build_command(media, plan, input_path, output_path)
    input_index = arguments.index("-i")
    arguments[input_index:input_index] = ["-ss", _seconds(start_seconds)]
    input_index += 2
    arguments[input_index + 2 : input_index + 2] = ["-t", _seconds(duration_seconds)]
    return arguments


def extract_frame_command(
    input_path: Path, timestamp_seconds: float, output_path: Path
) -> list[str]:
    """Return a minimal FFmpeg command that extracts one PNG frame."""
    if not input_path.is_absolute():
        raise ValueError("input_path must be absolute")
    if not output_path.is_absolute():
        raise ValueError("output_path must be absolute")
    return [
        "-nostdin",
        "-hide_banner",
        "-y",
        "-ss",
        _seconds(timestamp_seconds),
        "-i",
        str(input_path),
        "-frames:v",
        "1",
        "-an",
        str(output_path),
    ]


def _seconds(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text or "0"
