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
from reduvid.core.plan import AudioDecision, EncodePlan, PlanOptions, Warning, build_plan
from reduvid.core.probe import MediaInfo, estimate_stream_bytes, parse_bitrate
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


@dataclass(frozen=True)
class TrackRow:
    """One audio or subtitle track shown in the assistant, with its estimate."""

    index: int
    kind: Literal["audio", "subtitle"]
    language: str | None
    codec: str
    channels: int | None
    bitrate: int | None
    estimated_bytes: int | None
    is_image: bool
    is_default: bool


@dataclass(frozen=True)
class AudioSizeSummary:
    """Estimated audio size before and after applying the current plan."""

    current_bytes: int | None
    final_bytes: int | None


def track_rows(media: MediaInfo) -> tuple[TrackRow, ...]:
    """Return the audio and subtitle tracks of one media, in stream order."""
    audio = (
        TrackRow(
            index=stream.index,
            kind="audio",
            language=stream.language,
            codec=stream.codec,
            channels=stream.channels,
            bitrate=stream.bitrate,
            estimated_bytes=estimate_stream_bytes(stream.bitrate, media.duration),
            is_image=False,
            is_default=stream.is_default,
        )
        for stream in media.audio_streams
    )
    subtitles = (
        TrackRow(
            index=stream.index,
            kind="subtitle",
            language=stream.language,
            codec=stream.codec,
            channels=None,
            bitrate=None,
            estimated_bytes=None,
            is_image=stream.is_image,
            is_default=stream.is_default,
        )
        for stream in media.subtitle_streams
    )
    return tuple(sorted((*audio, *subtitles), key=lambda row: row.index))


def audio_size_summary(
    entries: Iterable[VideoEntry], options: PlanOptions, ffmpeg_info: FFmpegInfo
) -> AudioSizeSummary:
    """Estimate the audio size kept now and after the plan, over the ready videos."""
    current_parts: list[int | None] = []
    final_parts: list[int | None] = []
    for entry in entries:
        media = entry.media
        if media is None:
            continue
        streams = {stream.index: stream for stream in media.audio_streams}
        plan = build_plan(media, ffmpeg_info, options)
        for decision in plan.audios:
            stream = streams.get(decision.stream_index)
            if stream is None:
                current_parts.append(None)
                final_parts.append(None)
                continue
            current = estimate_stream_bytes(stream.bitrate, media.duration)
            current_parts.append(current)
            final_parts.append(_decision_bytes(decision, current, media.duration))
    return AudioSizeSummary(_sum_or_none(current_parts), _sum_or_none(final_parts))


def subtitle_container_note(
    media_list: Iterable[MediaInfo], container: str
) -> Literal["none", "image_dropped_mp4", "image_kept_mkv"]:
    """Describe what happens to image subtitles with the chosen container."""
    has_image = any(
        subtitle.is_image for media in media_list for subtitle in media.subtitle_streams
    )
    if not has_image:
        return "none"
    return "image_dropped_mp4" if container == "mp4" else "image_kept_mkv"


def _decision_bytes(
    decision: AudioDecision, copied_bytes: int | None, duration: float
) -> int | None:
    if decision.action == "copy":
        return copied_bytes
    bitrate = parse_bitrate(decision.bitrate)
    return estimate_stream_bytes(bitrate, duration)


def _sum_or_none(parts: Iterable[int | None]) -> int | None:
    total = 0
    for part in parts:
        if part is None:
            return None
        total += part
    return total


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


def format_duration(duration: float) -> str:
    seconds = int(duration) if duration > 0 else 0
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02}:{seconds:02}"
    return f"{minutes}:{seconds:02}"
