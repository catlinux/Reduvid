# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Early plan warnings in the Quality step for the first available video."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QLabel

from reduvid.core.config import Config
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.plan import Warning
from reduvid.core.probe import AudioStream, MediaInfo, SubtitleStream, VideoStream
from reduvid.gui.wizard.step_quality import StepQuality
from reduvid.gui.wizard_state import WizardState
from reduvid.messages import warning_text


def ffmpeg_info(*filters: str) -> FFmpegInfo:
    return FFmpegInfo(Path("ffmpeg"), Path("ffprobe"), "test", frozenset(), frozenset(filters), ())


def media(
    path: Path,
    *,
    video: VideoStream | None = None,
    audios: list[AudioStream] | None = None,
    subtitles: list[SubtitleStream] | None = None,
) -> MediaInfo:
    return MediaInfo(
        path,
        "matroska",
        60.0,
        1000,
        [video] if video is not None else [],
        audios or [],
        subtitles or [],
        [],
    )


def add_video(state: WizardState, tmp_path: Path, name: str, info: MediaInfo) -> None:
    path = tmp_path / name
    path.touch()
    state.add_paths([path])
    state.set_media(path, info)


def warning_labels(page: StepQuality) -> list[str]:
    labels: list[str] = []
    for index in range(page.warnings_layout.count()):
        widget = page.warnings_layout.itemAt(index).widget()
        if isinstance(widget, QLabel):
            labels.append(widget.text())
    return labels


def test_hdr_warning_is_shown_early(tmp_path: Path, qapp) -> None:
    state = WizardState(Config())
    add_video(
        state,
        tmp_path,
        "hdr.mkv",
        media(
            tmp_path / "hdr.mkv",
            video=VideoStream(0, "hevc", 1920, 1080, 24, hdr=True, hdr_variant="hdr10"),
        ),
    )
    page = StepQuality(state, ffmpeg_info(), profiles_dir=tmp_path)

    labels = warning_labels(page)

    expected = warning_text(
        Warning("hdr_tonemap_unavailable", {"stream_index": 0, "blocking": True})
    )
    assert expected in labels
    assert not page.warnings_container.isHidden()


def test_video_without_warnings_shows_nothing(tmp_path: Path, qapp) -> None:
    state = WizardState(Config())
    add_video(
        state,
        tmp_path,
        "clean.mkv",
        media(
            tmp_path / "clean.mkv",
            video=VideoStream(0, "h264", 1920, 1080, 24),
            audios=[AudioStream(1, "aac", 2, "eng", True)],
            subtitles=[SubtitleStream(2, "subrip", "eng", False, False, False)],
        ),
    )
    page = StepQuality(state, ffmpeg_info(), profiles_dir=tmp_path)

    assert warning_labels(page) == []
    assert page.warnings_container.isHidden()


def test_warnings_are_recalculated_when_destination_changes(tmp_path: Path, qapp) -> None:
    state = WizardState(Config())
    add_video(
        state,
        tmp_path,
        "hdr.mkv",
        media(
            tmp_path / "hdr.mkv",
            video=VideoStream(0, "hevc", 1920, 1080, 24, hdr=True, hdr_variant="hdr10"),
        ),
    )
    page = StepQuality(state, ffmpeg_info(), profiles_dir=tmp_path)
    assert warning_labels(page)

    state.set_destination("modern")

    assert warning_labels(page) == []
    assert page.warnings_container.isHidden()


def test_only_the_first_available_video_is_used(tmp_path: Path, qapp) -> None:
    state = WizardState(Config())
    add_video(
        state,
        tmp_path,
        "clean.mkv",
        media(
            tmp_path / "clean.mkv",
            video=VideoStream(0, "h264", 1920, 1080, 24),
        ),
    )
    add_video(
        state,
        tmp_path,
        "hdr.mkv",
        media(
            tmp_path / "hdr.mkv",
            video=VideoStream(0, "hevc", 1920, 1080, 24, hdr=True, hdr_variant="hdr10"),
        ),
    )
    page = StepQuality(state, ffmpeg_info(), profiles_dir=tmp_path)

    assert warning_labels(page) == []


def test_no_videos_does_not_break_the_step(tmp_path: Path, qapp) -> None:
    page = StepQuality(WizardState(Config()), ffmpeg_info(), profiles_dir=tmp_path)

    assert warning_labels(page) == []
    assert page.warnings_container.isHidden()
