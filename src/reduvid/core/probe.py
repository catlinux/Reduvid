# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Run ffprobe and convert its JSON output into typed media information."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ProbeError(RuntimeError):
    """Raised when ffprobe fails or returns invalid JSON."""


@dataclass(frozen=True)
class VideoStream:
    index: int
    codec: str
    width: int
    height: int
    fps: float
    bit_depth: int = 8
    hdr: bool = False
    hdr_variant: str | None = None
    language: str | None = None
    is_default: bool = False


@dataclass(frozen=True)
class AudioStream:
    index: int
    codec: str
    channels: int
    language: str | None
    is_default: bool
    sample_rate: int | None = None


@dataclass(frozen=True)
class SubtitleStream:
    index: int
    codec: str
    language: str | None
    is_image: bool
    is_default: bool
    forced: bool


@dataclass(frozen=True)
class Chapter:
    index: int
    start: float
    end: float
    title: str | None


@dataclass(frozen=True)
class MediaInfo:
    path: Path
    format: str
    duration: float
    size: int
    video_streams: list[VideoStream]
    audio_streams: list[AudioStream]
    subtitle_streams: list[SubtitleStream]
    chapters: list[Chapter]


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _int(value: object, default: int = 0) -> int:
    if not isinstance(value, (str, int, float)):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _fps(stream: dict[str, Any]) -> float:
    rate = stream.get("avg_frame_rate") or stream.get("r_frame_rate")
    if isinstance(rate, str) and "/" in rate:
        numerator, denominator = rate.split("/", maxsplit=1)
        divisor = _float(denominator)
        return _float(numerator) / divisor if divisor else 0.0
    return _float(rate)


def _tags(stream: dict[str, Any]) -> dict[str, Any]:
    return _mapping(stream.get("tags"))


def _disposition(stream: dict[str, Any]) -> dict[str, Any]:
    return _mapping(stream.get("disposition"))


def _language(stream: dict[str, Any]) -> str | None:
    language = _tags(stream).get("language")
    return language if isinstance(language, str) else None


def _video(stream: dict[str, Any]) -> VideoStream:
    transfer = stream.get("color_transfer")
    variant = None
    if isinstance(transfer, str):
        variant = {"smpte2084": "hdr10", "arib-std-b67": "hlg"}.get(transfer)
    side_data = stream.get("side_data_list")
    if isinstance(side_data, list) and any(
        "dovi" in str(_mapping(item).get("side_data_type", "")).lower()
        or "dolby vision" in str(_mapping(item).get("side_data_type", "")).lower()
        for item in side_data
    ):
        variant = "dolby_vision"
    raw_depth = stream.get("bits_per_raw_sample")
    depth = _int(raw_depth, 0)
    if depth <= 0:
        pixel_format = str(stream.get("pix_fmt") or "")
        depth = next(
            (candidate for candidate in (16, 14, 12, 10) if f"p{candidate}" in pixel_format),
            8,
        )
    return VideoStream(
        index=_int(stream.get("index")),
        codec=str(stream.get("codec_name") or "unknown"),
        width=_int(stream.get("width")),
        height=_int(stream.get("height")),
        fps=_fps(stream),
        bit_depth=depth,
        hdr=variant is not None,
        hdr_variant=variant,
        language=_language(stream),
        is_default=bool(_disposition(stream).get("default", 0)),
    )


def _parse(payload: object, path: Path) -> MediaInfo:
    root = _mapping(payload)
    form = _mapping(root.get("format"))
    raw_streams = root.get("streams")
    streams = raw_streams if isinstance(raw_streams, list) else []
    videos: list[VideoStream] = []
    audios: list[AudioStream] = []
    subtitles: list[SubtitleStream] = []
    for raw_stream in streams:
        stream = _mapping(raw_stream)
        codec_type = stream.get("codec_type")
        if codec_type == "video":
            videos.append(_video(stream))
        elif codec_type == "audio":
            audios.append(
                AudioStream(
                    index=_int(stream.get("index")),
                    codec=str(stream.get("codec_name") or "unknown"),
                    channels=_int(stream.get("channels")),
                    language=_language(stream),
                    is_default=bool(_disposition(stream).get("default", 0)),
                    sample_rate=(
                        _int(stream.get("sample_rate"))
                        if stream.get("sample_rate") is not None
                        else None
                    ),
                )
            )
        elif codec_type == "subtitle":
            codec = str(stream.get("codec_name") or "unknown")
            subtitles.append(
                SubtitleStream(
                    index=_int(stream.get("index")),
                    codec=codec,
                    language=_language(stream),
                    is_image=codec.lower() in {"hdmv_pgs_subtitle", "dvd_subtitle", "vobsub"},
                    is_default=bool(_disposition(stream).get("default", 0)),
                    forced=bool(_disposition(stream).get("forced", 0)),
                )
            )
    raw_chapters = root.get("chapters")
    chapters: list[Chapter] = []
    if isinstance(raw_chapters, list):
        for position, raw_chapter in enumerate(raw_chapters):
            chapter = _mapping(raw_chapter)
            title = _mapping(chapter.get("tags")).get("title")
            chapters.append(
                Chapter(
                    index=_int(chapter.get("id"), position),
                    start=_float(chapter.get("start_time")),
                    end=_float(chapter.get("end_time")),
                    title=title if isinstance(title, str) else None,
                )
            )
    return MediaInfo(
        path=path,
        format=str(form.get("format_name") or "unknown"),
        duration=_float(form.get("duration")),
        size=_int(form.get("size")),
        video_streams=videos,
        audio_streams=audios,
        subtitle_streams=subtitles,
        chapters=chapters,
    )


def probe_media(ffprobe_path: Path, media_path: Path) -> MediaInfo:
    """Probe an absolute media path; failures raise :class:`ProbeError`."""
    if not media_path.is_absolute():
        raise ValueError("media_path must be absolute")
    result = subprocess.run(  # noqa: S603
        [
            str(ffprobe_path),
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            "-show_chapters",
            str(media_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ProbeError(f"ffprobe exited with code {result.returncode}: {result.stderr.strip()}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ProbeError("ffprobe returned invalid JSON") from error
    return _parse(payload, media_path)
