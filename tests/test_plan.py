# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from pathlib import Path

import pytest

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


def test_jellyfin_crfs_and_resolution() -> None:
    video = VideoStream(0, "hevc", 3840, 2160, 24)
    for quality, expected in (("high", 19), ("balanced", 22), ("max_savings", 25)):
        plan = build_plan(media(videos=[video]), ffmpeg(), PlanOptions(quality=quality))
        assert plan.videos[0].crf == expected
        assert plan.videos[0].target_height == 1080
        assert any(item.code == "resolution_reduced_4k_to_1080p" for item in plan.warnings)


def test_jellyfin_explicit_max_height() -> None:
    video = VideoStream(0, "hevc", 1920, 1080, 24)
    plan = build_plan(media(videos=[video]), ffmpeg(), PlanOptions(max_height=720))

    assert plan.videos[0].target_height == 720
    assert any(item.code == "resolution_reduced_4k_to_1080p" for item in plan.warnings)


def test_jellyfin_video_below_max_height_is_not_reduced() -> None:
    video = VideoStream(0, "hevc", 1280, 720, 24)
    plan = build_plan(media(videos=[video]), ffmpeg(), PlanOptions(max_height=720))

    assert plan.videos[0].target_height is None
    assert not plan.warnings


@pytest.mark.parametrize("destination", ["modern", "archive"])
def test_non_jellyfin_profiles_ignore_max_height(destination: str) -> None:
    video = VideoStream(0, "hevc", 3840, 2160, 24)
    plan = build_plan(
        media(videos=[video]), ffmpeg(), PlanOptions(destination=destination, max_height=720)
    )

    assert plan.videos[0].target_height is None
    assert not any(item.code == "resolution_reduced_4k_to_1080p" for item in plan.warnings)


def test_hdr_jellyfin_and_modern() -> None:
    video = VideoStream(0, "hevc", 1920, 1080, 24, hdr=True, hdr_variant="hdr10")
    supported = build_plan(media(videos=[video]), ffmpeg("zscale", "tonemap"))
    assert supported.videos[0].filters == ("zscale", "tonemap")
    assert "hdr_tonemap_unavailable" not in {item.code for item in supported.warnings}
    unavailable = build_plan(media(videos=[video]), ffmpeg())
    assert any(item.code == "hdr_tonemap_unavailable" for item in unavailable.warnings)
    modern = build_plan(media(videos=[video]), ffmpeg(), PlanOptions(destination="modern"))
    assert modern.videos[0].filters == ()
    assert modern.videos[0].pixel_format == "yuv420p10le"


def test_audio_rules() -> None:
    audios = [
        AudioStream(1, "dts", 6, None, False),
        AudioStream(2, "dts", 2, None, False),
        AudioStream(3, "aac", 2, None, False),
    ]
    plan = build_plan(media(audios=audios), ffmpeg())
    assert [(item.action, item.codec, item.bitrate) for item in plan.audios] == [
        ("encode", "ac3", "640k"),
        ("encode", "aac", "192k"),
        ("copy", None, None),
    ]


def test_subtitle_rules_by_container() -> None:
    subtitles = [
        SubtitleStream(1, "hdmv_pgs_subtitle", None, True, False, False),
        SubtitleStream(2, "subrip", None, False, False, False),
    ]
    mkv = build_plan(media(subtitles=subtitles), ffmpeg())
    assert [item.action for item in mkv.subtitles] == ["copy", "copy"]
    assert any(item.code == "image_subtitle_burn_in" for item in mkv.warnings)
    mp4 = build_plan(media(subtitles=subtitles), ffmpeg(), PlanOptions(container="mp4"))
    assert [(item.action, item.codec) for item in mp4.subtitles] == [
        ("drop", None),
        ("convert", "mov_text"),
    ]
    assert any(item.code == "image_subtitle_dropped_mp4" for item in mp4.warnings)


@pytest.mark.parametrize(
    ("destination", "expected_codec", "crfs", "preset"),
    [
        ("jellyfin", "libx264", (19, 22, 25), "medium"),
        ("modern", "libx265", (21, 24, 27), "medium"),
        ("archive", "libx265", (21, 24, 27), "slow"),
    ],
)
def test_codec_quality_and_preset(
    destination: str, expected_codec: str, crfs: tuple[int, int, int], preset: str
) -> None:
    video = VideoStream(0, "h264", 1920, 1080, 24)
    for quality, expected_crf in zip(("high", "balanced", "max_savings"), crfs, strict=True):
        plan = build_plan(media(videos=[video]), ffmpeg(), PlanOptions(destination, quality))
        assert plan.videos[0].codec == expected_codec
        assert plan.videos[0].crf == expected_crf
        assert plan.videos[0].preset == preset


def test_audio_language_filter_keeps_only_matching_tracks() -> None:
    audios = [
        AudioStream(1, "aac", 2, "eng", True),
        AudioStream(2, "aac", 2, "spa", False),
        AudioStream(3, "aac", 2, "cat", False),
    ]
    plan = build_plan(
        media(audios=audios), ffmpeg(), PlanOptions(audio_languages=frozenset({"spa"}))
    )

    assert [item.stream_index for item in plan.audios] == [2]


def test_language_filter_is_case_insensitive_and_und_matches_missing() -> None:
    audios = [
        AudioStream(1, "aac", 2, None, False),
        AudioStream(2, "aac", 2, "", False),
        AudioStream(3, "aac", 2, "UND", False),
        AudioStream(4, "aac", 2, "SPA", False),
    ]
    without_language = build_plan(
        media(audios=audios), ffmpeg(), PlanOptions(audio_languages=frozenset({"und"}))
    )
    uppercase = build_plan(
        media(audios=audios), ffmpeg(), PlanOptions(audio_languages=frozenset({"spa"}))
    )

    assert [item.stream_index for item in without_language.audios] == [1, 2, 3]
    assert [item.stream_index for item in uppercase.audios] == [4]


def test_no_language_filter_keeps_every_track() -> None:
    audios = [AudioStream(1, "aac", 2, "eng", False), AudioStream(2, "aac", 2, "spa", False)]
    subtitles = [
        SubtitleStream(3, "subrip", "eng", False, False, False),
        SubtitleStream(4, "subrip", "spa", False, False, False),
    ]

    plan = build_plan(media(audios=audios, subtitles=subtitles), ffmpeg(), PlanOptions())

    assert [item.stream_index for item in plan.audios] == [1, 2]
    assert [item.stream_index for item in plan.subtitles] == [3, 4]
    assert not plan.warnings


def test_audio_filter_falls_back_to_all_when_nothing_matches() -> None:
    audios = [AudioStream(1, "aac", 2, "eng", False), AudioStream(2, "aac", 2, "spa", False)]
    plan = build_plan(
        media(audios=audios), ffmpeg(), PlanOptions(audio_languages=frozenset({"fra"}))
    )

    assert [item.stream_index for item in plan.audios] == [1, 2]
    assert [warning.code for warning in plan.warnings] == ["audio_filter_kept_all"]


def test_excluded_tracks_do_not_generate_warnings() -> None:
    audios = [
        AudioStream(1, "dts", 6, "eng", False),
        AudioStream(2, "aac", 2, "spa", False),
    ]
    subtitles = [
        SubtitleStream(3, "hdmv_pgs_subtitle", "eng", True, False, False),
        SubtitleStream(4, "subrip", "spa", False, False, False),
    ]
    plan = build_plan(
        media(audios=audios, subtitles=subtitles),
        ffmpeg(),
        PlanOptions(audio_languages=frozenset({"spa"}), subtitle_languages=frozenset({"spa"})),
    )

    assert [item.stream_index for item in plan.audios] == [2]
    assert [item.stream_index for item in plan.subtitles] == [4]
    assert not plan.warnings


def test_subtitle_filter_can_remove_every_subtitle() -> None:
    subtitles = [SubtitleStream(1, "subrip", "eng", False, False, False)]
    plan = build_plan(
        media(subtitles=subtitles),
        ffmpeg(),
        PlanOptions(subtitle_languages=frozenset({"fra"})),
    )

    assert plan.subtitles == ()
    assert not plan.warnings
