# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Pure decisions for encoding probed media with a selected profile."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.probe import AudioStream, MediaInfo, SubtitleStream, VideoStream
from reduvid.core.profiles import PROFILES, QUALITY_CRFS, Profile


@dataclass(frozen=True)
class PlanOptions:
    destination: str = "jellyfin"
    quality: str = "balanced"
    container: Literal["mkv", "mp4"] = "mkv"
    max_height: int | None = None


@dataclass(frozen=True)
class Warning:
    code: str
    params: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class VideoDecision:
    stream_index: int
    action: Literal["encode"]
    codec: str
    crf: int
    preset: str
    profile: str | None
    level: str | None
    pixel_format: str | None
    filters: tuple[str, ...]
    target_height: int | None


@dataclass(frozen=True)
class AudioDecision:
    stream_index: int
    action: Literal["copy", "encode"]
    codec: str | None = None
    bitrate: str | None = None


@dataclass(frozen=True)
class SubtitleDecision:
    stream_index: int
    action: Literal["copy", "convert", "drop"]
    codec: str | None = None


@dataclass(frozen=True)
class EncodePlan:
    destination: str
    quality: str
    container: str
    videos: tuple[VideoDecision, ...]
    audios: tuple[AudioDecision, ...]
    subtitles: tuple[SubtitleDecision, ...]
    warnings: tuple[Warning, ...]


def _profile(destination: str) -> Profile:
    try:
        return PROFILES[destination]
    except KeyError as error:
        raise ValueError(f"Unknown destination profile: {destination}") from error


def _crf(quality: str, codec: str) -> int:
    try:
        return QUALITY_CRFS[quality][codec]
    except KeyError as error:
        raise ValueError(f"Unknown quality level: {quality}") from error


def _video_decision(
    stream: VideoStream,
    profile: Profile,
    crf: int,
    ffmpeg_info: FFmpegInfo,
    warnings: list[Warning],
    max_height: int | None,
) -> VideoDecision:
    jellyfin = profile.name == "jellyfin"
    # Level 4.1 tops out at 1080p by default; max_height can override that limit.
    height_limit = max_height if max_height is not None else 1080
    should_reduce = jellyfin and (stream.width > 1920 or stream.height > height_limit)
    target_height = height_limit if should_reduce else None
    if target_height is not None:
        warnings.append(Warning("resolution_reduced_4k_to_1080p", {"stream_index": stream.index}))

    filters: tuple[str, ...] = ()
    if stream.hdr and jellyfin:
        if ffmpeg_info.has_zscale and ffmpeg_info.has_tonemap:
            filters = ("zscale", "tonemap")
            warnings.append(Warning("hdr_converted_to_sdr", {"stream_index": stream.index}))
        else:
            warnings.append(
                Warning(
                    "hdr_tonemap_unavailable",
                    {"stream_index": stream.index, "blocking": True},
                )
            )

    return VideoDecision(
        stream_index=stream.index,
        action="encode",
        codec=profile.video_codec,
        crf=crf,
        preset=profile.preset,
        profile=profile.video_profile,
        level=profile.video_level,
        pixel_format=("yuv420p10le" if stream.hdr and not jellyfin else profile.pixel_format),
        filters=filters,
        target_height=target_height,
    )


def _audio_decision(stream: AudioStream, warnings: list[Warning]) -> AudioDecision:
    # Jellyfin clients generally direct-play these codecs.
    if stream.codec.lower() in {"aac", "ac3", "eac3"}:
        return AudioDecision(stream.index, "copy")
    # AC3 640k preserves multichannel compatibility; AAC 192k suits mono and stereo.
    codec, bitrate = ("ac3", "640k") if stream.channels > 2 else ("aac", "192k")
    warnings.append(Warning("audio_recoded", {"stream_index": stream.index, "codec": codec}))
    return AudioDecision(stream.index, "encode", codec, bitrate)


def _subtitle_decision(
    stream: SubtitleStream, container: str, warnings: list[Warning]
) -> SubtitleDecision:
    if stream.is_image:
        if container == "mkv":
            # Jellyfin can burn image subtitles in during playback.
            warnings.append(Warning("image_subtitle_burn_in", {"stream_index": stream.index}))
            return SubtitleDecision(stream.index, "copy")
        # MP4 cannot preserve PGS/VobSub as a playable text subtitle.
        warnings.append(Warning("image_subtitle_dropped_mp4", {"stream_index": stream.index}))
        return SubtitleDecision(stream.index, "drop")
    if container == "mp4":
        # MP4 stores text subtitles as mov_text.
        return SubtitleDecision(stream.index, "convert", "mov_text")
    return SubtitleDecision(stream.index, "copy")


def build_plan(
    media: MediaInfo, ffmpeg_info: FFmpegInfo, options: PlanOptions | None = None
) -> EncodePlan:
    """Return per-stream encoding decisions without invoking external tools."""
    if options is None:
        options = PlanOptions()
    profile = _profile(options.destination)
    crf = _crf(options.quality, profile.video_codec)
    warnings: list[Warning] = []
    videos = tuple(
        _video_decision(stream, profile, crf, ffmpeg_info, warnings, options.max_height)
        for stream in media.video_streams
    )
    audios = tuple(_audio_decision(stream, warnings) for stream in media.audio_streams)
    subtitles = tuple(
        _subtitle_decision(stream, options.container, warnings) for stream in media.subtitle_streams
    )
    return EncodePlan(
        destination=profile.name,
        quality=options.quality,
        container=options.container,
        videos=videos,
        audios=audios,
        subtitles=subtitles,
        warnings=tuple(warnings),
    )
