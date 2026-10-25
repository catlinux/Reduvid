# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Widget-free logic shared by the last assistant steps."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from reduvid.core.compat import CompatStatus, jellyfin_status
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.plan import EncodePlan, PlanOptions, Warning, build_plan
from reduvid.core.probe import MediaInfo
from reduvid.gui.wizard_state import VideoEntry
from reduvid.i18n import _

LANGUAGE_ALIASES = {
    "cat": "ca",
    "spa": "es",
    "eng": "en",
    "fre": "fr",
    "fra": "fr",
    "ger": "de",
    "deu": "de",
    "ita": "it",
    "por": "pt",
    "jpn": "ja",
    "kor": "ko",
    "chi": "zh",
    "zho": "zh",
    "rus": "ru",
}


def language_name(code: str | None) -> str:
    """Return a readable language name for an ISO code, or the code itself."""
    normalized = (code or "").strip().lower()
    if not normalized or normalized == "und":
        return _("No language indicated")
    two_letter = LANGUAGE_ALIASES.get(normalized, normalized)
    if two_letter == "ca":
        return _("Catalan")
    if two_letter == "es":
        return _("Spanish")
    if two_letter == "en":
        return _("English")
    if two_letter == "fr":
        return _("French")
    if two_letter == "de":
        return _("German")
    if two_letter == "it":
        return _("Italian")
    if two_letter == "pt":
        return _("Portuguese")
    if two_letter == "ja":
        return _("Japanese")
    if two_letter == "ko":
        return _("Korean")
    if two_letter == "zh":
        return _("Chinese")
    if two_letter == "ru":
        return _("Russian")
    return code if code else normalized


def collect_languages(
    videos: Iterable[VideoEntry], kind: Literal["audio", "subtitle"]
) -> tuple[str, ...]:
    """Return the languages present in the probed videos, in appearance order."""
    codes: list[str] = []
    for entry in videos:
        media = entry.media
        if media is None:
            continue
        streams = media.audio_streams if kind == "audio" else media.subtitle_streams
        for stream in streams:
            code = (stream.language or "").strip().lower() or "und"
            if code not in codes:
                codes.append(code)
    return tuple(codes)


@dataclass(frozen=True)
class VideoSummary:
    path: Path
    media: MediaInfo
    plan: EncodePlan
    status: CompatStatus
    warnings: tuple[Warning, ...]
    blocking: tuple[Warning, ...]


def summarize(
    entry: VideoEntry, ffmpeg_info: FFmpegInfo, options: PlanOptions
) -> VideoSummary | None:
    """Build the plan and compatibility status for one probed video."""
    if entry.media is None:
        return None
    plan = build_plan(entry.media, ffmpeg_info, options)
    blocking = tuple(warning for warning in plan.warnings if warning.params.get("blocking") is True)
    return VideoSummary(
        path=entry.path,
        media=entry.media,
        plan=plan,
        status=jellyfin_status(plan),
        warnings=plan.warnings,
        blocking=blocking,
    )


def format_size(size: int) -> str:
    if size >= 1_000_000_000:
        return f"{size / 1_000_000_000:.1f} GB"
    return f"{size / 1_000_000:.0f} MB"


def format_duration(duration: float) -> str:
    seconds = int(duration) if duration > 0 else 0
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02}:{seconds:02}"
    return f"{minutes}:{seconds:02}"
