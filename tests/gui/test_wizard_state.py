# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Wizard state tests (no widgets, no real probes)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from reduvid.core.config import Config
from reduvid.core.probe import MediaInfo
from reduvid.gui.wizard_state import WizardState


def media(path: Path) -> MediaInfo:
    return MediaInfo(path, "matroska", 90.0, 1000, [], [], [], [])


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
