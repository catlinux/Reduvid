# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Wizard state tests (no widgets, no real probes)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from reduvid.core.config import Config
from reduvid.core.probe import AudioStream, MediaInfo
from reduvid.gui.wizard_state import WizardState


def media(path: Path, audios: list[AudioStream] | None = None) -> MediaInfo:
    return MediaInfo(path, "matroska", 90.0, 1000, [], audios or [], [], [])


def test_initial_values_come_from_the_config() -> None:
    state = WizardState(Config(destination="modern", quality="high"))

    options = state.options()

    assert options.destination == "modern"
    assert options.quality == "high"
    assert state.videos == ()
    assert not state.ready


def test_add_folder_filters_extensions_and_recursion(tmp_path: Path) -> None:
    folder = tmp_path / "media"
    nested = folder / "nested"
    nested.mkdir(parents=True)
    for path in (
        folder / "one.MKV",
        folder / "notes.txt",
        nested / "two.mp4",
        nested / "readme.md",
    ):
        path.touch()

    state = WizardState(Config())
    flat = state.add_paths([folder])
    state = WizardState(Config())
    recursive = state.add_paths([folder], recursive=True)

    assert sorted(path.name for path in flat) == ["one.MKV"]
    assert sorted(path.name for path in recursive) == ["one.MKV", "two.mp4"]


def test_duplicate_paths_are_ignored(tmp_path: Path) -> None:
    video = tmp_path / "video.mkv"
    video.touch()
    state = WizardState(Config())

    assert state.add_paths([video, video]) == [video.resolve()]
    assert len(state.videos) == 1


def test_probe_results_and_errors_set_readiness(tmp_path: Path) -> None:
    good = tmp_path / "good.mkv"
    bad = tmp_path / "bad.mkv"
    good.touch()
    bad.touch()
    state = WizardState(Config())
    state.add_paths([good, bad])

    state.set_media(good, media(good))
    assert state.ready

    state.set_error(bad, "broken")
    entry = next(entry for entry in state.videos if entry.path == bad.resolve())
    assert entry.error == "broken"
    assert entry.media is None


def test_remove_paths_notifies_once(tmp_path: Path) -> None:
    first = tmp_path / "one.mkv"
    second = tmp_path / "two.mkv"
    first.touch()
    second.touch()
    state = WizardState(Config())
    state.add_paths([first, second])
    changes: list[int] = []
    state.changed.connect(lambda: changes.append(1))

    state.remove_paths([first.resolve()])
    state.remove_paths([first.resolve()])

    assert len(changes) == 1
    assert [entry.path.name for entry in state.videos] == ["two.mkv"]


def test_unknown_destination_is_rejected() -> None:
    state = WizardState(Config())

    with pytest.raises(ValueError):
        state.set_destination("unknown")
    with pytest.raises(ValueError):
        state.set_quality("ultra")


def test_single_video_needs_exactly_one_probed_video(tmp_path: Path) -> None:
    first = tmp_path / "one.mkv"
    second = tmp_path / "two.mkv"
    first.touch()
    second.touch()
    state = WizardState(Config())

    assert state.single_video is None

    state.add_paths([first])
    assert state.single_video is None

    state.set_media(first, media(first))
    assert state.single_video is not None
    assert state.single_video.path == first.resolve()

    state.add_paths([second])
    assert state.single_video is None


def test_audio_track_selection_and_options(tmp_path: Path) -> None:
    video = tmp_path / "video.mkv"
    other = tmp_path / "other.mkv"
    video.touch()
    other.touch()
    state = WizardState(Config())
    state.add_paths([video])
    state.set_media(
        video,
        media(
            video,
            audios=[
                AudioStream(1, "aac", 2, "spa", True),
                AudioStream(2, "ac3", 6, "spa", False),
            ],
        ),
    )

    assert state.selected_audio_tracks() == frozenset({1, 2})
    assert state.options().audio_tracks is None

    state.set_audio_tracks([1])

    assert state.selected_audio_tracks() == frozenset({1})
    assert state.options().audio_tracks == frozenset({1})

    state.set_audio_tracks([1, 2])

    assert state.options().audio_tracks is None

    state.set_audio_tracks([2])
    state.add_paths([other])
    state.set_media(other, media(other))

    assert state.audio_tracks is None
    assert state.options().audio_tracks is None


def test_audio_track_selection_resets_when_videos_are_removed(tmp_path: Path) -> None:
    video = tmp_path / "video.mkv"
    video.touch()
    state = WizardState(Config())
    state.add_paths([video])
    state.set_media(video, media(video, audios=[AudioStream(1, "aac", 2, "spa", True)]))
    state.set_audio_tracks([1])

    state.remove_paths([video])

    assert state.audio_tracks is None


def test_audio_track_setters_only_notify_on_change() -> None:
    state = WizardState(Config())
    changes: list[int] = []
    state.changed.connect(lambda: changes.append(1))

    state.set_audio_tracks(None)
    state.set_one_audio_per_language(False)
    state.set_reduce_audio(False)

    assert changes == []

    state.set_audio_tracks([1, 2])
    state.set_one_audio_per_language(True)
    state.set_reduce_audio(True)

    assert len(changes) == 3


def test_audio_options_use_safe_defaults(tmp_path: Path) -> None:
    state = WizardState(Config())
    video = tmp_path / "video.mkv"
    video.touch()
    state.add_paths([video])
    state.set_media(video, media(video))

    options = state.options()

    assert options.audio_tracks is None
    assert options.one_audio_per_language is False
    assert options.reduce_audio is False

    state.set_one_audio_per_language(True)
    state.set_reduce_audio(True)

    options = state.options()

    assert options.one_audio_per_language is True
    assert options.reduce_audio is True
