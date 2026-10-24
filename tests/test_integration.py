# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from reduvid.core.command import build_command
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.naming import build_output_path, build_temp_path, finalize_output
from reduvid.core.plan import PlanOptions, build_plan
from reduvid.core.probe import MediaInfo, probe_media
from reduvid.core.runner import EncodeHandle, EncodeResult
from reduvid.core.verify import VerificationResult, verify_output


def _conversion_destination(ffmpeg_info: FFmpegInfo) -> str:
    if ffmpeg_info.has_libx264:
        return "jellyfin"
    if ffmpeg_info.has_libx265:
        return "modern"
    pytest.skip("FFmpeg H.264/H.265 encoder not available")


def _convert(
    ffmpeg_info: FFmpegInfo, input_path: Path, destination_dir: Path
) -> tuple[Path, VerificationResult]:
    destination_dir.mkdir(parents=True, exist_ok=True)
    media = probe_media(ffmpeg_info.ffprobe_path, input_path)
    plan = build_plan(
        media,
        ffmpeg_info,
        PlanOptions(destination=_conversion_destination(ffmpeg_info), quality="balanced"),
    )
    output_path = build_output_path(input_path, destination_dir, plan.container)
    temp_path = build_temp_path(output_path)
    command = build_command(media, plan, input_path, temp_path)
    result = EncodeHandle(
        command,
        media.duration,
        temp_path,
        threads=2,
        ffmpeg_path=ffmpeg_info.ffmpeg_path,
    ).run()
    assert not result.cancelled
    assert result.returncode == 0

    verification = verify_output(
        ffmpeg_info.ffprobe_path,
        input_path,
        media.duration,
        media.size,
        temp_path,
    )
    if verification.passed:
        finalize_output(temp_path, output_path)
    else:
        temp_path.unlink(missing_ok=True)
    return output_path, verification


@pytest.mark.ffmpeg
def test_conversion_verifies_size_duration_subtitles_and_chapters(
    ffmpeg_info: FFmpegInfo, video_with_streams: Path, tmp_path: Path
) -> None:
    original = probe_media(ffmpeg_info.ffprobe_path, video_with_streams)
    assert [audio.language for audio in original.audio_streams] == ["eng", "spa"]
    assert len(original.subtitle_streams) == 1
    assert len(original.chapters) == 2

    output_path, verification = _convert(ffmpeg_info, video_with_streams, tmp_path / "output")

    assert verification.passed
    assert output_path.is_file()
    assert output_path.stat().st_size < video_with_streams.stat().st_size
    converted = probe_media(ffmpeg_info.ffprobe_path, output_path)
    assert abs(converted.duration - original.duration) <= 0.25
    assert len(converted.subtitle_streams) == len(original.subtitle_streams)
    assert len(converted.chapters) == len(original.chapters)


@pytest.mark.ffmpeg
def test_second_conversion_uses_a_numeric_suffix_without_overwriting(
    ffmpeg_info: FFmpegInfo, video_with_streams: Path, tmp_path: Path
) -> None:
    destination_dir = tmp_path / "output"
    first_path, first_verification = _convert(ffmpeg_info, video_with_streams, destination_dir)
    first_size = first_path.stat().st_size
    second_candidate = build_output_path(video_with_streams, destination_dir, "mkv")

    second_path, second_verification = _convert(ffmpeg_info, video_with_streams, destination_dir)

    assert first_verification.passed
    assert second_verification.passed
    assert second_candidate == first_path.with_name(f"{first_path.stem} (2){first_path.suffix}")
    assert second_path == second_candidate
    assert first_path.is_file() and second_path.is_file()
    assert first_path.stat().st_size == first_size


@pytest.mark.ffmpeg
def test_cancel_removes_partial_temporary_output(
    ffmpeg_info: FFmpegInfo, long_video: Path, tmp_path: Path
) -> None:
    media = probe_media(ffmpeg_info.ffprobe_path, long_video)
    plan = build_plan(
        media, ffmpeg_info, PlanOptions(destination=_conversion_destination(ffmpeg_info))
    )
    output_path = build_output_path(long_video, tmp_path, plan.container)
    temp_path = build_temp_path(output_path)
    command = build_command(media, plan, long_video, temp_path)
    command.insert(command.index("-i"), "-re")
    progress_received = threading.Event()
    handle = EncodeHandle(
        command,
        media.duration,
        temp_path,
        lambda _event: progress_received.set(),
        threads=2,
        ffmpeg_path=ffmpeg_info.ffmpeg_path,
    )
    results: list[EncodeResult] = []
    errors: list[Exception] = []

    def run_encode() -> None:
        try:
            results.append(handle.run())
        except Exception as error:
            errors.append(error)

    thread = threading.Thread(target=run_encode)
    thread.start()
    received_progress = progress_received.wait(timeout=5)
    handle.cancel()
    thread.join(timeout=10)

    assert received_progress
    assert not thread.is_alive()
    assert not errors
    assert len(results) == 1 and results[0].cancelled
    assert not temp_path.exists()
    assert not output_path.exists()


@pytest.mark.ffmpeg
def test_ten_bit_fixture_is_detected_by_probe(ffmpeg_info: FFmpegInfo, ten_bit_video: Path) -> None:
    media: MediaInfo = probe_media(ffmpeg_info.ffprobe_path, ten_bit_video)

    assert media.video_streams[0].bit_depth == 10
