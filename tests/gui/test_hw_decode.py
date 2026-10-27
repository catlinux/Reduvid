# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Hardware decoding option in preferences, workers and the main window."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

pytest.importorskip("PySide6")

from reduvid.core.config import Config
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.plan import PlanOptions
from reduvid.core.probe import MediaInfo, VideoStream
from reduvid.core.sample import SampleEstimate
from reduvid.gui.main_window import MainWindow
from reduvid.gui.preferences import PreferencesDialog
from reduvid.gui.theme.manager import ThemeManager
from reduvid.gui.wizard_state import WizardState
from reduvid.gui.workers import LevelsWorker, SampleWorker


def ffmpeg_info() -> FFmpegInfo:
    return FFmpegInfo(
        Path("ffmpeg"),
        Path("ffprobe"),
        "test",
        frozenset({"libx264"}),
        frozenset(),
        (),
        hwaccels=("cuda",),
    )


def sample_media(path: Path) -> MediaInfo:
    return MediaInfo(
        path,
        "matroska",
        10.0,
        100_000,
        [VideoStream(0, "h264", 1920, 1080, 24)],
        [],
        [],
        [],
    )


def test_preferences_checkbox_loads_and_saves_hw_decode(qapp) -> None:
    dialog = PreferencesDialog(Config(), ThemeManager(qapp))

    assert dialog.hw_decode.objectName() == "hwDecodeCheck"
    assert dialog.hw_decode.accessibleName()
    assert dialog.hw_decode.isChecked()
    assert dialog.hw_decode_hint.property("role") == "muted"

    dialog.hw_decode.setChecked(False)
    dialog.accept()

    assert dialog.config.hw_decode is False

    disabled = PreferencesDialog(Config(hw_decode=False), ThemeManager(qapp))
    assert not disabled.hw_decode.isChecked()


def test_wizard_state_tracks_hw_decode(qapp) -> None:
    state = WizardState(Config(hw_decode=False))
    changes: list[int] = []
    state.changed.connect(lambda: changes.append(1))

    assert state.hw_decode is False
    state.set_hw_decode(False)
    assert changes == []

    state.set_hw_decode(True)
    assert state.hw_decode is True
    assert changes == [1]


class RecordingSampleRunner:
    calls: ClassVar[list[dict[str, object]]] = []

    def __init__(self, *_args: object, **kwargs: object) -> None:
        type(self).calls.append(kwargs)

    def run(self) -> SampleEstimate:
        return SampleEstimate(500, 10.0, 5.0)

    def cancel(self) -> None:
        pass


class RecordingLevelsRunner:
    calls: ClassVar[list[dict[str, object]]] = []

    def __init__(self, *_args: object, **kwargs: object) -> None:
        type(self).calls.append(kwargs)

    def run(self) -> dict[str, object]:
        return {}

    def cancel(self) -> None:
        pass


def test_workers_pass_hw_decode_to_the_runner_factory(tmp_path: Path, qapp) -> None:
    path = (tmp_path / "movie.mkv").resolve()
    RecordingSampleRunner.calls = []
    RecordingLevelsRunner.calls = []

    sample = SampleWorker(
        ffmpeg_info(),
        sample_media(path),
        PlanOptions(),
        path,
        hw_decode=True,
        runner_factory=RecordingSampleRunner,
    )
    sample.run()
    levels = LevelsWorker(
        ffmpeg_info(),
        sample_media(path),
        PlanOptions(),
        path,
        hw_decode=True,
        runner_factory=RecordingLevelsRunner,
    )
    levels.run()

    assert RecordingSampleRunner.calls[0]["hw_decode"] is True
    assert RecordingLevelsRunner.calls[0]["hw_decode"] is True


def test_start_queue_uses_the_preferences_hw_decode(monkeypatch: pytest.MonkeyPatch, qapp) -> None:
    window = MainWindow(Config(), ffmpeg_info(), ThemeManager(qapp))
    captured: list[dict[str, object]] = []

    class FakeProcessor:
        def __init__(self, *_args: object, **kwargs: object) -> None:
            captured.append(kwargs)

    class FakeDialog:
        config = Config(hw_decode=False)

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def exec(self) -> int:
            return 1

    class FakeThread:
        def isRunning(self) -> bool:
            return False

    monkeypatch.setattr("reduvid.gui.main_window.FileProcessor", FakeProcessor)
    monkeypatch.setattr("reduvid.gui.main_window.PreferencesDialog", FakeDialog)
    monkeypatch.setattr("reduvid.gui.main_window.start_worker_thread", lambda _worker: FakeThread())

    window.open_preferences()
    assert window.wizard_state.hw_decode is False

    window.start_queue([], PlanOptions())

    assert captured[0]["hw_decode"] is False
