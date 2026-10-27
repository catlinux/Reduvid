# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Widget-free logic for steps 4-6."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from reduvid.core.config import Config
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.plan import PlanOptions, build_plan
from reduvid.core.probe import (
    AudioStream,
    MediaInfo,
    SubtitleStream,
    VideoStream,
    format_size,
)
from reduvid.gui.wizard_logic import (
    audio_size_summary,
    change_notes,
    collect_languages,
    format_duration,
    language_name,
    quality_note,
    subtitle_container_note,
    summarize,
    track_rows,
)
from reduvid.gui.wizard_state import VideoEntry, WizardState


def media(
    path: Path,
    *,
    video: VideoStream | None = None,
    audios: list[AudioStream] | None = None,
    subtitles: list[SubtitleStream] | None = None,
    size: int = 1000,
    duration: float = 60.0,
) -> MediaInfo:
    return MediaInfo(
        path,
        "matroska",
        duration,
        size,
        [video] if video is not None else [],
        audios or [],
        subtitles or [],
        [],
    )


def ffmpeg(*filters: str) -> FFmpegInfo:
    return FFmpegInfo(Path("ffmpeg"), Path("ffprobe"), "test", frozenset(), frozenset(filters), ())


def add_video(state: WizardState, tmp_path: Path, name: str, info: MediaInfo) -> Path:
    path = tmp_path / name
    path.touch()
    state.add_paths([path])
    state.set_media(path, info)
    return path.resolve()


def test_language_names_and_aliases() -> None:
    assert language_name("ca") == "Catalan"
    assert language_name("cat") == "Catalan"
    assert language_name("spa") == "Spanish"
    assert language_name("eng") == "English"
    assert language_name("fre") == "French"
    assert language_name("deu") == "German"
    assert language_name("jpn") == "Japanese"
    assert language_name("und") == "No language indicated"
    assert language_name(None) == "No language indicated"
    assert language_name("xyz") == "xyz"


def test_collect_languages_keeps_order_and_treats_missing_as_und(tmp_path: Path) -> None:
    first = WizardState(Config())
    add_video(
        first,
        tmp_path,
        "one.mkv",
        media(
            tmp_path / "one.mkv",
            audios=[
                AudioStream(1, "aac", 2, "eng", True),
                AudioStream(2, "aac", 2, None, False),
            ],
            subtitles=[
                SubtitleStream(3, "subrip", "spa", False, False, False),
                SubtitleStream(4, "subrip", "", False, False, False),
            ],
        ),
    )
    add_video(
        first,
        tmp_path,
        "two.mkv",
        media(
            tmp_path / "two.mkv",
            audios=[AudioStream(1, "aac", 2, "eng", True)],
            subtitles=[SubtitleStream(2, "subrip", "und", False, False, False)],
        ),
    )

    assert collect_languages(first.videos, "audio") == ("eng", "und")
    assert collect_languages(first.videos, "subtitle") == ("spa", "und")


def test_options_use_none_when_everything_is_selected(tmp_path: Path) -> None:
    state = WizardState(Config())
    add_video(
        state,
        tmp_path,
        "video.mkv",
        media(
            tmp_path / "video.mkv",
            audios=[
                AudioStream(1, "aac", 2, "eng", True),
                AudioStream(2, "aac", 2, "spa", False),
            ],
            subtitles=[SubtitleStream(3, "subrip", "eng", False, False, False)],
        ),
    )

    options = state.options()

    assert options.audio_languages is None
    assert options.subtitle_languages is None

    state.set_audio_languages({"eng"})

    assert state.options().audio_languages == frozenset({"eng"})
    assert state.options().subtitle_languages is None

    state.set_audio_languages({"eng", "spa"})

    assert state.options().audio_languages is None


def test_reduce_4k_is_only_applied_for_cinecat_with_4k_video(tmp_path: Path) -> None:
    state = WizardState(Config())
    video = VideoStream(0, "hevc", 3840, 2160, 24)
    add_video(state, tmp_path, "uhd.mkv", media(tmp_path / "uhd.mkv", video=video))

    assert state.options().max_height is None

    state.set_reduce_4k(False)
    assert state.options().max_height == 2160

    state.set_destination("modern")
    assert state.options().max_height is None

    state.set_destination("cinecat")
    state.set_reduce_4k(True)
    assert state.options().max_height is None


def test_container_output_and_replace_defaults(tmp_path: Path) -> None:
    output_dir = tmp_path / "converted"
    state = WizardState(Config(container="mp4", output_dir=output_dir))

    assert state.container == "mp4"
    assert state.output_dir == output_dir
    assert state.replace_original is False

    state.set_container("mkv")
    state.set_output_dir(None)
    state.set_replace_original(True)

    assert state.options().container == "mkv"
    assert state.replace_original is True


def test_summaries_include_traffic_light_and_blocking_warnings(tmp_path: Path) -> None:
    state = WizardState(Config())
    direct = VideoStream(0, "h264", 1920, 1080, 24)
    hdr = VideoStream(0, "hevc", 1920, 1080, 24, hdr=True, hdr_variant="hdr10")
    add_video(state, tmp_path, "direct.mkv", media(tmp_path / "direct.mkv", video=direct))
    add_video(state, tmp_path, "hdr.mkv", media(tmp_path / "hdr.mkv", video=hdr))
    options = state.options()

    direct_summary = summarize(state.videos[0], ffmpeg(), options)
    hdr_summary = summarize(state.videos[1], ffmpeg(), options)

    assert direct_summary is not None
    assert direct_summary.status.level == "direct"
    assert direct_summary.blocking == ()
    assert hdr_summary is not None
    assert hdr_summary.status.level == "blocked"
    assert [warning.code for warning in hdr_summary.blocking] == ["hdr_tonemap_unavailable"]


def test_size_and_duration_formatting() -> None:
    assert format_size(1_500_000_000) == "1.5 GB"
    assert format_size(250_000_000) == "250 MB"
    assert format_duration(3725) == "1:02:05"
    assert format_duration(65) == "1:05"


def test_track_rows_list_audio_and_subtitles_with_estimates(tmp_path: Path) -> None:
    info = media(
        tmp_path / "video.mkv",
        duration=100.0,
        audios=[
            AudioStream(1, "eac3", 6, "spa", True, bitrate=640_000),
            AudioStream(2, "ac3", 2, "eng", False),
        ],
        subtitles=[
            SubtitleStream(3, "hdmv_pgs_subtitle", "spa", True, False, False),
            SubtitleStream(4, "subrip", "eng", False, True, False),
        ],
    )

    rows = track_rows(info)

    assert [row.index for row in rows] == [1, 2, 3, 4]
    assert [row.kind for row in rows] == ["audio", "audio", "subtitle", "subtitle"]
    assert rows[0].channels == 6
    assert rows[0].bitrate == 640_000
    assert rows[0].estimated_bytes == 8_000_000
    assert rows[0].is_default is True
    assert rows[1].estimated_bytes is None
    assert rows[2].is_image is True
    assert rows[2].estimated_bytes is None
    assert rows[3].is_default is True


def test_audio_size_summary_with_two_audio_tracks(tmp_path: Path) -> None:
    info = media(
        tmp_path / "video.mkv",
        duration=100.0,
        audios=[
            AudioStream(1, "eac3", 6, "spa", True, bitrate=640_000),
            AudioStream(2, "ac3", 6, "spa", False, bitrate=640_000),
        ],
    )
    entries = [VideoEntry(tmp_path / "video.mkv", info)]

    everything = audio_size_summary(entries, PlanOptions(), ffmpeg())

    assert everything.current_bytes == 16_000_000
    # Cinecat recodes E-AC-3/AC-3 5.1 to AAC at 384k: 384_000 * 100 / 8 per track.
    assert everything.final_bytes == 9_600_000

    one_track = audio_size_summary(entries, PlanOptions(audio_tracks=frozenset({1})), ffmpeg())

    assert one_track.current_bytes == 8_000_000
    assert one_track.final_bytes == 4_800_000

    reduced = audio_size_summary(
        entries,
        PlanOptions(audio_tracks=frozenset({1}), reduce_audio=True),
        ffmpeg(),
    )

    assert reduced.current_bytes == 8_000_000
    assert reduced.final_bytes == 3_200_000


def test_audio_size_summary_is_none_when_a_bitrate_is_missing(tmp_path: Path) -> None:
    info = media(
        tmp_path / "video.mkv",
        duration=100.0,
        audios=[AudioStream(1, "aac", 6, "spa", True)],
    )
    entries = [VideoEntry(tmp_path / "video.mkv", info)]

    summary = audio_size_summary(entries, PlanOptions(), ffmpeg())

    assert summary.current_bytes is None
    assert summary.final_bytes is None


def test_subtitle_container_note_for_each_case(tmp_path: Path) -> None:
    text = media(
        tmp_path / "text.mkv",
        subtitles=[SubtitleStream(1, "subrip", "spa", False, True, False)],
    )
    image = media(
        tmp_path / "image.mkv",
        subtitles=[SubtitleStream(1, "hdmv_pgs_subtitle", "spa", True, True, False)],
    )

    assert subtitle_container_note([text], "mp4") == "none"
    assert subtitle_container_note([image], "mp4") == "image_dropped_mp4"
    assert subtitle_container_note([image], "mkv") == "image_kept_mkv"


def _notes(
    video: VideoStream, destination: str = "modern", quality: str = "balanced", **options: object
) -> tuple[str, ...]:
    info = media(Path("/media/a.mkv"), video=video)
    plan = build_plan(
        info,
        ffmpeg("zscale", "tonemap"),
        PlanOptions(
            destination=destination,
            quality=quality,
            **options,  # type: ignore[arg-type]
        ),
    )
    return change_notes(info, plan)


def test_change_notes_for_modern_keeps_resolution_and_names_h265() -> None:
    notes = _notes(VideoStream(0, "h264", 1920, 1080, 24.0))

    assert any("H.265" in note for note in notes)
    assert any("stays at 1920x1080" in note for note in notes)
    assert not any("scaled down" in note for note in notes)


def test_change_notes_for_cinecat_4k_hdr_mentions_scaling_and_sdr() -> None:
    notes = _notes(
        VideoStream(0, "hevc", 3840, 2160, 24.0, bit_depth=10, hdr=True), destination="cinecat"
    )

    assert any("H.264" in note for note in notes)
    assert any("from 2160p to 1080p" in note for note in notes)
    assert any("SDR" in note for note in notes)


def test_quality_note_describes_each_level() -> None:
    assert "stays large" in quality_note("high")
    assert "slightly smoothed" in quality_note("balanced")
    assert "softer" in quality_note("max_savings")
    assert quality_note("unknown") == ""


def test_change_notes_leave_the_quality_sentence_out() -> None:
    notes = _notes(VideoStream(0, "h264", 1280, 720, 24.0), quality="max_savings")

    assert not any("softer" in note for note in notes)
    assert not any("stays large" in note for note in notes)


def test_change_notes_say_when_ten_bit_becomes_eight_bit() -> None:
    notes = _notes(VideoStream(0, "hevc", 1920, 1080, 24.0, bit_depth=10), destination="cinecat")

    assert any("10 to 8 bits" in note for note in notes)


def test_change_notes_are_empty_without_video() -> None:
    info = media(Path("/media/a.mkv"))
    plan = build_plan(info, ffmpeg(), PlanOptions())

    assert change_notes(info, plan) == ()
