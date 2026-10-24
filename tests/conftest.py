# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Generate isolated real media fixtures for FFmpeg integration tests.

Fixtures use pytest's default function scope to keep generated files isolated.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from reduvid.core.ffmpeg import FFmpegInfo, detect_ffmpeg


@pytest.fixture
def ffmpeg_info() -> FFmpegInfo:
    """Detect FFmpeg for each test so unavailable installations skip cleanly."""
    info = detect_ffmpeg()
    if info is None:
        pytest.skip("FFmpeg not available")
    return info


def _generate_video(ffmpeg_info: FFmpegInfo, arguments: list[str]) -> None:
    subprocess.run(
        [str(ffmpeg_info.ffmpeg_path), "-hide_banner", "-loglevel", "error", *arguments],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def video_with_streams(ffmpeg_info: FFmpegInfo, tmp_path: Path) -> Path:
    """Build a function-scoped MKV with two audios, text subtitles, and chapters."""
    subtitle_path = tmp_path / "example.srt"
    subtitle_path.write_text(
        "1\n00:00:00,500 --> 00:00:02,500\nGenerated integration subtitle.\n",
        encoding="utf-8",
    )
    metadata_path = tmp_path / "chapters.txt"
    metadata_path.write_text(
        ";FFMETADATA1\n"
        "[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=2000\ntitle=Opening\n"
        "[CHAPTER]\nTIMEBASE=1/1000\nSTART=2000\nEND=4000\ntitle=Main\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "source.mkv"
    _generate_video(
        ffmpeg_info,
        [
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=duration=4:size=640x360:rate=25",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=4",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=880:duration=4",
            "-i",
            str(subtitle_path),
            "-f",
            "ffmetadata",
            "-i",
            str(metadata_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-map",
            "2:a:0",
            "-map",
            "3:s:0",
            "-map_metadata",
            "4",
            "-map_chapters",
            "4",
            "-metadata:s:a:0",
            "language=eng",
            "-metadata:s:a:1",
            "language=spa",
            "-metadata:s:s:0",
            "language=eng",
            "-c:v",
            "ffv1",
            "-level",
            "3",
            "-c:a",
            "pcm_s16le",
            "-c:s",
            "srt",
            str(output_path),
        ],
    )
    return output_path.resolve()


@pytest.fixture
def ten_bit_video(ffmpeg_info: FFmpegInfo, tmp_path: Path) -> Path:
    """Build a real ten-bit source when this FFmpeg provides libx265."""
    if not ffmpeg_info.has_libx265:
        pytest.skip("FFmpeg 10-bit encoder not available")
    output_path = tmp_path / "ten-bit.mkv"
    _generate_video(
        ffmpeg_info,
        [
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=duration=4:size=320x180:rate=25",
            "-c:v",
            "libx265",
            "-preset",
            "ultrafast",
            "-x265-params",
            "pools=1:frame-threads=1",
            "-pix_fmt",
            "yuv420p10le",
            "-an",
            str(output_path),
        ],
    )
    return output_path.resolve()


@pytest.fixture
def long_video(ffmpeg_info: FFmpegInfo, tmp_path: Path) -> Path:
    """Build an isolated ten-second source for a real mid-encode cancellation."""
    output_path = tmp_path / "long-source.mkv"
    _generate_video(
        ffmpeg_info,
        [
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=duration=10:size=320x180:rate=25",
            "-c:v",
            "ffv1",
            "-level",
            "3",
            "-an",
            str(output_path),
        ],
    )
    return output_path.resolve()
