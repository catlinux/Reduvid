# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Build FFmpeg arguments from media and encoding decisions."""

from __future__ import annotations

from pathlib import Path

from reduvid.core.plan import HDR_TO_SDR_FILTERS, EncodePlan, VideoDecision
from reduvid.core.probe import MediaInfo


def build_video_arguments(video: VideoDecision, position: int) -> list[str]:
    """Return the map, encoder and filter arguments for one output video stream."""
    arguments = ["-map", f"0:{video.stream_index}"]
    arguments.extend([f"-c:v:{position}", video.codec])
    arguments.extend([f"-crf:v:{position}", str(video.crf)])
    arguments.extend([f"-preset:v:{position}", video.preset])
    if video.profile is not None:
        arguments.extend([f"-profile:v:{position}", video.profile])
    if video.level is not None:
        arguments.extend([f"-level:v:{position}", video.level])
    if video.pixel_format is not None:
        arguments.extend([f"-pix_fmt:v:{position}", video.pixel_format])
    filters: list[str] = []
    # Scaling first makes tone mapping a 4K source work on a quarter of the pixels.
    if video.target_height is not None:
        filters.append(f"scale=-2:{video.target_height}")
    filters.extend(video.filters)
    if filters:
        arguments.extend([f"-filter:v:{position}", ",".join(filters)])
    if video.filters == HDR_TO_SDR_FILTERS:
        # Without these tags players keep reading the SDR result as HDR (PQ).
        for option in ("color_primaries", "color_trc", "colorspace"):
            arguments.extend([f"-{option}:v:{position}", "bt709"])
    return arguments


def build_command(
    media: MediaInfo,
    plan: EncodePlan,
    input_path: Path,
    output_path: Path,
    *,
    hw_decode: bool = False,
) -> list[str]:
    """Return FFmpeg arguments; both paths must already be absolute."""
    if not input_path.is_absolute():
        raise ValueError("input_path must be absolute")
    if not output_path.is_absolute():
        raise ValueError("output_path must be absolute")

    arguments = ["-nostdin", "-hide_banner", "-y"]
    if hw_decode:
        arguments.extend(["-hwaccel", "auto"])
    arguments.extend(["-i", str(input_path)])

    for position, video in enumerate(plan.videos):
        arguments.extend(build_video_arguments(video, position))

    # Tracks keep source order, so FFmpeg marks the first remaining track of each
    # type as the default when the original default was filtered out.
    for position, audio in enumerate(plan.audios):
        arguments.extend(["-map", f"0:{audio.stream_index}"])
        arguments.extend([f"-c:a:{position}", audio.codec or "copy"])
        if audio.action == "encode" and audio.bitrate is not None:
            arguments.extend([f"-b:a:{position}", audio.bitrate])
        if audio.action == "encode" and audio.channels is not None:
            arguments.extend([f"-ac:a:{position}", str(audio.channels)])

    subtitle_position = 0
    for subtitle in plan.subtitles:
        if subtitle.action == "drop":
            continue
        arguments.extend(["-map", f"0:{subtitle.stream_index}"])
        arguments.extend([f"-c:s:{subtitle_position}", subtitle.codec or "copy"])
        subtitle_position += 1

    if plan.container == "mkv":
        for attachment in media.attachments:
            arguments.extend(["-map", f"0:{attachment.index}", "-c:t", "copy"])

    arguments.extend(["-map_metadata", "0", "-map_chapters", "0"])
    if plan.container == "mp4":
        # Faststart lets a browser start playback before the file finishes downloading.
        arguments.extend(["-movflags", "+faststart"])
    arguments.append(str(output_path))
    return arguments
