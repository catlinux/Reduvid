# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Advanced mode: shared state, saved ui_mode and CLI-equivalent options."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QScrollArea

from reduvid.core.config import Config, load_config
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.plan import PlanOptions
from reduvid.core.probe import AudioStream, MediaInfo, SubtitleStream, VideoStream
from reduvid.core.report import build_queue_report
from reduvid.gui.advanced_page import AdvancedPage
from reduvid.gui.main_window import MainWindow
from reduvid.gui.theme.manager import ThemeManager
from reduvid.gui.wizard_state import WizardState


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


def ffmpeg() -> FFmpegInfo:
    return FFmpegInfo(Path("ffmpeg"), Path("ffprobe"), "test", frozenset(), frozenset(), ())


def add_video(state: WizardState, tmp_path: Path, name: str, info: MediaInfo) -> Path:
    path = tmp_path / name
    path.touch()
    state.add_paths([path])
    state.set_media(path, info)
    return path.resolve()


def test_initial_mode_comes_from_the_config(qapp) -> None:
    window = MainWindow(Config(ui_mode="advanced"), ffmpeg(), ThemeManager(qapp))

    assert window.ui_mode == "advanced"
    assert window.step_list.isHidden()
    assert window.center_stack.currentWidget() is window.advanced_page
    assert window.advanced_button.isChecked()
    assert not window.wizard_button.isChecked()


def test_switching_modes_keeps_the_state_and_saves_ui_mode(
    tmp_path: Path, isolated_user_config: Path, qapp
) -> None:
    window = MainWindow(Config(destination="archive", quality="high"), ffmpeg(), ThemeManager(qapp))
    state = window.wizard_state
    video = add_video(
        state,
        tmp_path,
        "video.mkv",
        media(
            tmp_path / "video.mkv",
            video=VideoStream(0, "h264", 1920, 1080, 24),
            audios=[
                AudioStream(1, "aac", 2, "eng", True),
                AudioStream(2, "aac", 2, "spa", False),
            ],
        ),
    )
    state.set_audio_languages({"eng"})

    window.advanced_button.click()

    assert window.ui_mode == "advanced"
    assert window.step_list.isHidden()
    assert window.center_stack.currentWidget() is window.advanced_page
    saved, invalid = load_config(isolated_user_config)
    assert invalid == ()
    assert saved.ui_mode == "advanced"
    assert (saved.destination, saved.quality) == ("archive", "high")

    window.wizard_button.click()

    assert window.ui_mode == "wizard"
    assert not window.step_list.isHidden()
    assert window.center_stack.currentWidget() is window.wizard_panel
    assert [entry.path for entry in state.videos] == [video]
    assert state.options().destination == "archive"
    assert state.options().quality == "high"
    assert state.options().audio_languages == frozenset({"eng"})
    assert load_config(isolated_user_config)[0].ui_mode == "wizard"


def test_advanced_page_builds_cli_equivalent_options(tmp_path: Path, qapp) -> None:
    state = WizardState(Config())
    add_video(
        state,
        tmp_path,
        "video.mkv",
        media(
            tmp_path / "video.mkv",
            video=VideoStream(0, "h264", 1920, 1080, 24),
            audios=[
                AudioStream(1, "aac", 2, "eng", True),
                AudioStream(2, "aac", 2, "spa", False),
            ],
            subtitles=[SubtitleStream(3, "subrip", "eng", False, False, False)],
        ),
    )
    page = AdvancedPage(state, ffmpeg())

    page.destination_combo.setCurrentIndex(page.destination_combo.findData("modern"))
    page.quality_combo.setCurrentIndex(page.quality_combo.findData("high"))
    page.max_height_check.setChecked(True)
    page.max_height_spin.setValue(720)
    page.threads_check.setChecked(True)
    page.threads_spin.setValue(4)
    page.destination.container_cards["mp4"].click()
    page.keep.audio_track_checks[2].setChecked(False)

    assert state.options() == PlanOptions(
        destination="modern",
        quality="high",
        container="mp4",
        max_height=720,
        audio_tracks=frozenset({1}),
        subtitle_languages=None,
    )
    assert state.threads == 4


def test_advanced_page_has_outer_and_scroll_margins(qapp) -> None:
    page = AdvancedPage(WizardState(Config()), ffmpeg())

    margins = page.layout().contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
        16,
        20,
        16,
        12,
    )
    scroll = page.findChild(QScrollArea, "advancedScroll")
    assert scroll is not None
    assert scroll.widget() is not None
    content_layout = scroll.widget().layout()
    assert content_layout is not None
    assert content_layout.contentsMargins().right() > 0


def test_advanced_page_has_every_option(tmp_path: Path, qapp) -> None:
    page = AdvancedPage(WizardState(Config()), ffmpeg())

    assert page.objectName() == "advancedPage"
    for widget in (
        page.videos,
        page.destination_combo,
        page.quality_combo,
        page.max_height_check,
        page.max_height_spin,
        page.threads_check,
        page.threads_spin,
        page.destination,
        page.keep,
        page.summary,
    ):
        assert widget is not None
    assert page.destination_combo.currentData() == "cinecat"
    assert page.quality_combo.currentData() == "balanced"
    assert not page.max_height_check.isChecked()
    assert not page.threads_check.isChecked()


def test_mode_switch_is_disabled_while_a_conversion_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp
) -> None:
    window = MainWindow(Config(), ffmpeg(), ThemeManager(qapp))
    add_video(
        window.wizard_state,
        tmp_path,
        "direct.mkv",
        media(
            tmp_path / "direct.mkv",
            video=VideoStream(0, "h264", 1920, 1080, 24),
        ),
    )
    window.step_summary.refresh()

    class FakeWorker(QObject):
        finished = Signal(object)

    worker = FakeWorker()
    captured: dict[str, object] = {}

    def fake_start(paths, options, **kwargs):
        captured["paths"] = list(paths)
        return worker

    monkeypatch.setattr(window, "start_queue", fake_start)
    window.step_summary.start_button.click()

    assert captured["paths"] == [window.wizard_state.videos[0].path]
    assert not window.wizard_button.isEnabled()
    assert not window.advanced_button.isEnabled()

    worker.finished.emit(build_queue_report([]))

    assert window.wizard_button.isEnabled()
    assert window.advanced_button.isEnabled()
    assert "Total savings" in window.step_summary.report_label.text()


def test_advanced_start_uses_threads_and_max_height(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp
) -> None:
    window = MainWindow(Config(), ffmpeg(), ThemeManager(qapp))
    state = window.wizard_state
    add_video(
        state,
        tmp_path,
        "direct.mkv",
        media(
            tmp_path / "direct.mkv",
            video=VideoStream(0, "h264", 1920, 1080, 24),
        ),
    )
    window.advanced_button.click()
    page = window.advanced_page
    page.max_height_check.setChecked(True)
    page.max_height_spin.setValue(720)
    page.threads_check.setChecked(True)
    page.threads_spin.setValue(3)
    page.summary.refresh()
    captured: dict[str, object] = {}

    class FakeWorker(QObject):
        finished = Signal(object)

    def fake_start(paths, options, **kwargs):
        captured.update(paths=list(paths), options=options, kwargs=kwargs)
        return FakeWorker()

    monkeypatch.setattr(window, "start_queue", fake_start)
    page.summary.start_button.click()

    assert captured["paths"] == [state.videos[0].path]
    options = captured["options"]
    assert isinstance(options, PlanOptions)
    assert options.max_height == 720
    assert captured["kwargs"] == {
        "output_dir": state.output_dir,
        "threads": 3,
        "replace_original": False,
    }
