# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Saving and loading saved profiles from the Quality step."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QInputDialog

from reduvid.core.config import Config
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.plan import PlanOptions
from reduvid.core.probe import AudioStream, MediaInfo, SubtitleStream, VideoStream
from reduvid.core.profile_store import list_profiles, load_profile, save_profile
from reduvid.gui.wizard.step_quality import StepQuality
from reduvid.gui.wizard_state import WizardState


def ffmpeg_info() -> FFmpegInfo:
    return FFmpegInfo(
        Path("ffmpeg"), Path("ffprobe"), "test", frozenset({"libx264"}), frozenset(), ()
    )


def state_with_video(tmp_path: Path) -> WizardState:
    path = tmp_path / "película ñ.mkv"
    path.touch()
    info = MediaInfo(
        path,
        "matroska",
        60.0,
        100_000_000,
        [VideoStream(0, "h264", 1920, 1080, 24)],
        [
            AudioStream(1, "aac", 2, "eng", True),
            AudioStream(2, "aac", 2, "spa", False),
        ],
        [
            SubtitleStream(3, "subrip", "eng", False, False, False),
            SubtitleStream(4, "subrip", "spa", False, False, False),
        ],
        [],
    )
    state = WizardState(Config())
    state.add_paths([path])
    state.set_media(path, info)
    return state


def test_empty_profile_list_disables_controls(tmp_path: Path, qapp) -> None:
    page = StepQuality(state_with_video(tmp_path), ffmpeg_info(), profiles_dir=tmp_path)

    assert page.profile_combo.count() == 0
    assert not page.profile_combo.isEnabled()
    assert not page.apply_profile_button.isEnabled()


def test_saving_a_profile_lists_it_in_the_combo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, qapp
) -> None:
    state = state_with_video(tmp_path)
    state.set_destination("modern")
    state.set_quality("high")
    page = StepQuality(state, ffmpeg_info(), profiles_dir=tmp_path)
    monkeypatch.setattr(
        QInputDialog, "getText", staticmethod(lambda *_args, **_kwargs: ("Cine", True))
    )

    page.save_profile_button.click()

    assert list_profiles(tmp_path) == ("Cine",)
    assert page.profile_combo.count() == 1
    assert page.profile_combo.currentData() == "Cine"
    assert page.profile_combo.isEnabled()
    assert page.apply_profile_button.isEnabled()
    assert load_profile("Cine", tmp_path) == state.options()
    assert page.profile_status.text() == "Profile saved."


def test_empty_name_does_not_create_a_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, qapp
) -> None:
    page = StepQuality(state_with_video(tmp_path), ffmpeg_info(), profiles_dir=tmp_path)
    monkeypatch.setattr(
        QInputDialog, "getText", staticmethod(lambda *_args, **_kwargs: ("   ", True))
    )

    page.save_profile_button.click()

    assert list_profiles(tmp_path) == ()
    assert page.profile_status.text() == "The profile name cannot be empty."


def test_applying_a_profile_fills_the_whole_state(tmp_path: Path, qapp) -> None:
    state = state_with_video(tmp_path)
    options = PlanOptions(
        destination="archive",
        quality="max_savings",
        container="mp4",
        max_height=720,
        audio_languages=frozenset({"eng"}),
        subtitle_languages=frozenset({"eng"}),
    )
    save_profile("Archivo", options, tmp_path)
    page = StepQuality(state, ffmpeg_info(), profiles_dir=tmp_path)

    index = page.profile_combo.findData("Archivo")
    page.profile_combo.setCurrentIndex(index)
    page.apply_profile_button.click()

    assert state.destination == "archive"
    assert state.quality == "max_savings"
    assert state.container == "mp4"
    assert state.max_height == 720
    assert state.selected_audio_languages() == frozenset({"eng"})
    assert state.selected_subtitle_languages() == frozenset({"eng"})
    assert state.options() == options
    assert page.profile_status.text() == "Profile applied."


def test_applying_unfiltered_languages_selects_all(tmp_path: Path, qapp) -> None:
    state = state_with_video(tmp_path)
    save_profile("Todo", PlanOptions(), tmp_path)
    page = StepQuality(state, ffmpeg_info(), profiles_dir=tmp_path)

    page.profile_combo.setCurrentIndex(page.profile_combo.findData("Todo"))
    page.apply_profile_button.click()

    assert state.options().audio_languages is None
    assert state.options().subtitle_languages is None
    assert state.selected_audio_languages() == frozenset({"eng", "spa"})
