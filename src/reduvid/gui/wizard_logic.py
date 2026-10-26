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
from reduvid.core.probe import MediaInfo, estimate_stream_bytes
from reduvid.core.probe import format_duration as format_duration
from reduvid.core.sample import audio_bytes_for_plan
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
        plan = build_plan(media, ffmpeg_info, options)
        current, final = audio_bytes_for_plan(media, plan)
        current_parts.append(current)
        final_parts.append(final)
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


def change_notes(media: MediaInfo, plan: EncodePlan) -> tuple[str, ...]:
    """Plain sentences saying what the video conversion changes.

    They are the same for every quality level, so the step shows them once; the
    quality-specific sentence lives in :func:`quality_note`.
    """
    if not plan.videos:
        return ()
    decision = plan.videos[0]
    source = next(
        (stream for stream in media.video_streams if stream.index == decision.stream_index),
        None,
    )
    notes: list[str] = []

    if decision.codec == "libx265":
        notes.append(
            _(
                "The video is re-encoded to H.265. It takes less space than H.264 at the "
                "same look, but some older TVs and browsers cannot play it."
            )
        )
    else:
        notes.append(
            _(
                "The video is re-encoded to H.264, which plays on almost any device but "
                "takes more space than H.265."
            )
        )

    if source is not None:
        if decision.target_height is not None:
            notes.append(
                _("The picture is scaled down from {from_height}p to {to_height}p.").format(
                    from_height=source.height, to_height=decision.target_height
                )
            )
        else:
            notes.append(
                _("The resolution stays at {width}x{height}.").format(
                    width=source.width, height=source.height
                )
            )
        if decision.filters:
            notes.append(
                _("HDR becomes standard colour (SDR); colours may look slightly different.")
            )
        elif source.hdr:
            notes.append(_("HDR is kept."))
        elif source.bit_depth > 8 and decision.pixel_format == "yuv420p":
            notes.append(
                _(
                    "The video goes from 10 to 8 bits per colour; smooth gradients may "
                    "show faint bands."
                )
            )

    if decision.preset == "slow":
        notes.append(_("The slower encoding setting saves a bit more space but takes longer."))
    return tuple(notes)


_QUALITY_NOTES = {
    "high": lambda: _("Very little detail is lost, so the file stays large."),
    "balanced": lambda: _(
        "Very fine detail, such as film grain or textures in dark scenes, is slightly smoothed."
    ),
    "max_savings": lambda: _(
        "Dark scenes, film grain and fast movement look softer and may show blocks."
    ),
}


def quality_note(quality: str) -> str:
    """Sentence saying what each quality level can cost, or "" for an unknown one."""
    note = _QUALITY_NOTES.get(quality)
    return note() if note is not None else ""


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
