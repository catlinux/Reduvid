# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from pathlib import Path

from reduvid.core.compat import cinecat_status
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.plan import PlanOptions, build_plan
from reduvid.core.probe import AudioStream, MediaInfo, SubtitleStream, VideoStream


def media(
    *,
    videos: list[VideoStream] | None = None,
    audios: list[AudioStream] | None = None,
    subtitles: list[SubtitleStream] | None = None,
) -> MediaInfo:
    return MediaInfo(
        Path("input.mkv"), "matroska", 60, 1, videos or [], audios or [], subtitles or [], []
    )


def ffmpeg(*filters: str) -> FFmpegInfo:
    return FFmpegInfo(Path("ffmpeg"), Path("ffprobe"), "test", frozenset(), frozenset(filters), ())


def test_cinecat_profile_direct_plays() -> None:
    video = VideoStream(0, "h264", 1920, 1080, 24)
    audio = AudioStream(1, "aac", 2, "spa", True)
    plan = build_plan(media(videos=[video], audios=[audio]), ffmpeg(), PlanOptions())

    status = cinecat_status(plan)

    assert status.level == "direct"
    assert status.reasons == ()


def test_non_cinecat_profile_and_container_are_partial() -> None:
    video = VideoStream(0, "h264", 1920, 1080, 24)
    plan = build_plan(media(videos=[video]), ffmpeg(), PlanOptions(destination="modern"))

    status = cinecat_status(plan)

    assert status.level == "partial"
    assert [warning.code for warning in status.reasons] == [
        "not_direct_play_profile",
        "not_direct_play_container",
    ]


def test_mkv_cinecat_is_partial() -> None:
    video = VideoStream(0, "h264", 1920, 1080, 24)
    plan = build_plan(
        media(videos=[video]), ffmpeg(), PlanOptions(destination="cinecat", container="mkv")
    )

    status = cinecat_status(plan)

    assert status.level == "partial"
    assert [warning.code for warning in status.reasons] == ["not_direct_play_container"]


def test_image_subtitles_are_partial() -> None:
    subtitles = [SubtitleStream(1, "hdmv_pgs_subtitle", "eng", True, False, False)]
    plan = build_plan(media(subtitles=subtitles), ffmpeg(), PlanOptions(container="mp4"))

    status = cinecat_status(plan)

    assert status.level == "partial"
    assert [warning.code for warning in status.reasons] == ["image_subtitle_dropped_mp4"]


def test_ten_bit_output_is_partial() -> None:
    video = VideoStream(0, "hevc", 3840, 2160, 24, hdr=True, hdr_variant="hdr10")
    plan = build_plan(media(videos=[video]), ffmpeg(), PlanOptions(destination="archive"))

    status = cinecat_status(plan)

    assert status.level == "partial"
    assert [warning.code for warning in status.reasons] == [
        "not_direct_play_profile",
        "not_direct_play_container",
        "ten_bit_video",
    ]


def test_blocking_warning_blocks_and_takes_precedence() -> None:
    video = VideoStream(0, "hevc", 1920, 1080, 24, hdr=True, hdr_variant="hdr10")
    subtitles = [SubtitleStream(1, "hdmv_pgs_subtitle", "eng", True, False, False)]
    plan = build_plan(media(videos=[video], subtitles=subtitles), ffmpeg(), PlanOptions())

    status = cinecat_status(plan)

    assert status.level == "blocked"
    assert [warning.code for warning in status.reasons] == ["hdr_tonemap_unavailable"]
