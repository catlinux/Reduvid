# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Pure decisions for encoding probed media with a selected profile."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.probe import (
    AudioStream,
    MediaInfo,
    SubtitleStream,
    VideoStream,
)
from reduvid.core.probe import (
    estimate_stream_bytes as estimate_stream_bytes,
)
from reduvid.core.profiles import PROFILES, QUALITY_CRFS, Profile


@dataclass(frozen=True)
class PlanOptions:
    destination: str = "cinecat"
    quality: str = "balanced"
    container: Literal["mkv", "mp4"] | None = None
    max_height: int | None = None
    audio_languages: frozenset[str] | None = None
    subtitle_languages: frozenset[str] | None = None
    audio_tracks: frozenset[int] | None = None
    one_audio_per_language: bool = False
    reduce_audio: bool = False


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
    channels: int | None = None


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


def resolve_container(options: PlanOptions) -> Literal["mkv", "mp4"]:
    """Return the explicit container or the automatic one for the destination."""
    if options.container is not None:
        return options.container
    return "mp4" if options.destination == "cinecat" else "mkv"


def _target_height(stream: VideoStream, profile: Profile, max_height: int | None) -> int | None:
    if max_height is None:
        # Cinecat's H.264 level 4.1 profile tops out at 1080p; other profiles keep it.
        limit = 1080 if profile.name == "cinecat" else None
    else:
        # Even heights keep yuv420p encoders happy, so round the limit down.
        limit = max_height - max_height % 2
    if limit is None or limit < 2 or stream.height <= limit:
        return None
    return limit


def _video_decision(
    stream: VideoStream,
    profile: Profile,
    crf: int,
    ffmpeg_info: FFmpegInfo,
    warnings: list[Warning],
    max_height: int | None,
) -> VideoDecision:
    cinecat = profile.name == "cinecat"
    target_height = _target_height(stream, profile, max_height)
    if target_height is not None:
        warnings.append(
            Warning(
                "resolution_reduced",
                {
                    "stream_index": stream.index,
                    "from_height": stream.height,
                    "to_height": target_height,
                },
            )
        )

    filters: tuple[str, ...] = ()
    if stream.hdr and cinecat:
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
        pixel_format=("yuv420p10le" if stream.hdr and not cinecat else profile.pixel_format),
        filters=filters,
        target_height=target_height,
    )


def rank_audio_key(stream: AudioStream) -> tuple[int, int, int, int]:
    """Sort key for audio stream quality: channels, bitrate, is_default, -index."""
    return (
        stream.channels,
        stream.bitrate or 0,
        1 if stream.is_default else 0,
        -stream.index,
    )


def rank_audio(streams: Sequence[AudioStream]) -> list[AudioStream]:
    """Return audio streams ranked from best to worst quality."""
    return sorted(streams, key=rank_audio_key, reverse=True)


def _aac_bitrate(channels: int) -> str:
    # 384k is the usual transparent rate for 5.1 AAC; 192k for mono and stereo.
    return "384k" if channels > 2 else "192k"


def _audio_decision(
    stream: AudioStream,
    warnings: list[Warning],
    reduce_audio: bool = False,
    *,
    destination: str,
) -> AudioDecision:
    if reduce_audio:
        target_bitrate = "256k" if stream.channels > 2 else "128k"
        target_bps = 256_000 if stream.channels > 2 else 128_000
        if (
            stream.codec.lower() == "aac"
            and stream.bitrate is not None
            and stream.bitrate <= target_bps
        ):
            return AudioDecision(stream.index, "copy")
        warnings.append(
            Warning("audio_reduced", {"stream_index": stream.index, "bitrate": target_bitrate})
        )
        channels = 6 if destination == "cinecat" and stream.channels > 6 else None
        return AudioDecision(stream.index, "encode", "aac", target_bitrate, channels)

    if destination == "cinecat":
        # Chrome and Firefox cannot decode AC-3/E-AC-3; browsers play AAC/MP3 directly.
        if stream.codec.lower() in {"aac", "mp3"}:
            return AudioDecision(stream.index, "copy")
        channels = 6 if stream.channels > 6 else None
        bitrate = _aac_bitrate(stream.channels)
        warnings.append(Warning("audio_recoded", {"stream_index": stream.index, "codec": "aac"}))
        return AudioDecision(stream.index, "encode", "aac", bitrate, channels)

    # Modern and archive keep the previous audio rules.
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
            # MKV keeps PGS/VobSub; players that cannot draw them have to burn them in.
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

    selected_audio: list[AudioStream]
    if options.audio_tracks is not None:
        selected_audio = [
            stream for stream in media.audio_streams if stream.index in options.audio_tracks
        ]
        if media.audio_streams and not selected_audio:
            # Keeping some audio beats producing a silent video, even if none matches.
            selected_audio = list(media.audio_streams)
            warnings.append(Warning("audio_filter_kept_all"))
    elif options.audio_languages is not None:
        audio_languages = _language_filter(options.audio_languages)
        selected_audio = [
            stream
            for stream in media.audio_streams
            if _language_allowed(stream.language, audio_languages)
        ]
        if media.audio_streams and not selected_audio:
            # Keeping some audio beats producing a silent video, even if none matches.
            selected_audio = list(media.audio_streams)
            warnings.append(Warning("audio_filter_kept_all"))
    else:
        selected_audio = list(media.audio_streams)

    if options.one_audio_per_language and selected_audio:
        groups: dict[str, list[AudioStream]] = {}
        for stream in selected_audio:
            lang = _normalized_language(stream.language)
            groups.setdefault(lang, []).append(stream)
        chosen_indices = {rank_audio(group)[0].index for group in groups.values()}
        selected_audio = [stream for stream in selected_audio if stream.index in chosen_indices]

    audios = tuple(
        _audio_decision(
            stream,
            warnings,
            options.reduce_audio,
            destination=profile.name,
        )
        for stream in selected_audio
    )

    container = resolve_container(options)
    subtitle_languages = _language_filter(options.subtitle_languages)
    selected_subtitles = [
        stream
        for stream in media.subtitle_streams
        if _language_allowed(stream.language, subtitle_languages)
    ]
    subtitles = tuple(
        _subtitle_decision(stream, container, warnings) for stream in selected_subtitles
    )
    return EncodePlan(
        destination=profile.name,
        quality=options.quality,
        container=container,
        videos=videos,
        audios=audios,
        subtitles=subtitles,
        warnings=tuple(warnings),
    )


def _language_filter(languages: frozenset[str] | None) -> frozenset[str] | None:
    if languages is None:
        return None
    return frozenset(_normalized_language(language) for language in languages)


def _normalized_language(language: str | None) -> str:
    normalized = (language or "").strip().lower()
    return normalized or "und"


def _language_allowed(language: str | None, languages: frozenset[str] | None) -> bool:
    return languages is None or _normalized_language(language) in languages
