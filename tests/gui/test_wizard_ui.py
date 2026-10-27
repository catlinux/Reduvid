# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Assistant widgets, steps and navigation tests (offscreen, fake probes)."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QMimeData, QObject, QPointF, Qt, QUrl, Signal
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QButtonGroup

from reduvid.core.config import Config
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.probe import AudioStream, MediaInfo, VideoStream
from reduvid.core.sample import TotalEstimate
from reduvid.gui.main_window import MainWindow
from reduvid.gui.theme.manager import ThemeManager
from reduvid.gui.widgets.option_card import OptionCard
from reduvid.gui.widgets.step_list import StepList
from reduvid.gui.widgets.wizard_nav import WizardNav
from reduvid.gui.wizard.step_quality import StepQuality
from reduvid.gui.wizard.step_videos import StepVideos
from reduvid.gui.wizard_state import WizardState
from reduvid.messages import error_text


def media(path: Path, duration: float = 90.0) -> MediaInfo:
    return MediaInfo(path, "matroska", duration, 1000, [], [], [], [])


def ffmpeg_info() -> FFmpegInfo:
    return FFmpegInfo(
        Path("ffmpeg"), Path("ffprobe"), "test", frozenset({"libx264"}), frozenset(), ()
    )


def wait_until(predicate, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        QCoreApplication.processEvents()
        time.sleep(0.005)
        assert time.monotonic() < deadline, "condition not met before the timeout"


def test_option_card_is_accessible_and_cards_are_exclusive(qapp) -> None:
    first = OptionCard("First", "Tag", "First description")
    second = OptionCard("Second", "", "Second description")
    group = QButtonGroup()
    group.setExclusive(True)
    group.addButton(first, 0)
    group.addButton(second, 1)

    first.click()

    assert first.objectName() == "card"
    assert first.isCheckable()
    assert first.accessibleName() == "First"
    assert first.accessibleDescription()
    assert first.isChecked()
    assert first.property("checked") is True
    assert not second.isChecked()

    second.click()

    assert second.isChecked()
    assert not first.isChecked()


def test_step_list_tracks_done_current_and_pending(qapp) -> None:
    steps = StepList(["One", "Two", "Three"])
    selected: list[int] = []
    steps.selected.connect(selected.append)

    assert steps.objectName() == "stepList"
    assert [button.accessibleName() for button in steps.buttons] == ["One", "Two", "Three"]
    assert steps.states == ("current", "pending", "pending")

    steps.buttons[1].click()
    assert selected == [1]

    steps.set_current(1)

    assert steps.states == ("done", "current", "pending")
    assert steps.buttons[1].isChecked()


def test_wizard_nav_shows_the_next_step_and_can_disable_it(qapp) -> None:
    nav = WizardNav()

    nav.set_next_text("Quality")
    nav.set_next_enabled(False)
    nav.set_back_enabled(False)

    assert nav.next_button.text() == "&Next: Quality"
    assert not nav.next_button.isEnabled()
    assert not nav.back_button.isEnabled()


def test_navigation_needs_a_probed_video_and_step_list_navigates(tmp_path: Path, qapp) -> None:
    window = MainWindow(Config(), ffmpeg_info(), ThemeManager(qapp))
    window.show()
    try:
        assert window.current_step == 0
        assert not window.wizard_nav.next_button.isEnabled()
        assert not window.wizard_nav.back_button.isEnabled()

        video = tmp_path / "video.mkv"
        video.touch()
        window.wizard_state.add_paths([video])
        window.wizard_state.set_media(video, media(video))

        assert window.wizard_nav.next_button.isEnabled()
        window.wizard_nav.next_button.click()
        assert window.current_step == 1
        assert window.content.currentIndex() == 1
        assert window.wizard_nav.back_button.isEnabled()
        assert window.wizard_nav.next_button.text() == "&Next: Quality"

        window.wizard_nav.back_button.click()
        assert window.current_step == 0

        window.step_list.buttons[2].click()
        assert window.current_step == 2
        assert window.content.currentIndex() == 2
        assert window.step_list.states == (
            "done",
            "done",
            "current",
            "pending",
            "pending",
            "pending",
        )
    finally:
        window.close()


def test_target_cards_are_exclusive_and_unknown_uses_cinecat(qapp) -> None:
    window = MainWindow(Config(), ffmpeg_info(), ThemeManager(qapp))
    target = window.content.widget(1)

    target.cards["modern"].click()
    assert window.wizard_state.destination == "modern"
    assert target.cards["modern"].isChecked()
    assert not target.cards["cinecat"].isChecked()

    target.cards["unknown"].click()
    assert target.cards["unknown"].isChecked()
    assert window.wizard_state.options().destination == "cinecat"


def test_quality_recommendation_follows_the_destination(qapp) -> None:
    window = MainWindow(Config(), ffmpeg_info(), ThemeManager(qapp))
    quality = window.content.widget(2)

    assert quality.cards["balanced"].tag_label.text() == "Recommended"
    assert "Jellyfin" in quality.recommendation_label.text()

    window.wizard_state.set_destination("archive")

    assert quality.cards["max_savings"].tag_label.text() == "Recommended"
    assert quality.cards["balanced"].tag_label.text() == ""
    assert "Maximum savings" in quality.recommendation_label.text()


def test_drop_folder_with_fake_probe_filters_extensions(tmp_path: Path, qapp) -> None:
    folder = tmp_path / "media"
    nested = folder / "nested"
    nested.mkdir(parents=True)
    for path in (
        folder / "one.mkv",
        folder / "two.MP4",
        folder / "notes.txt",
        nested / "three.webm",
    ):
        path.touch()
    state = WizardState(Config())
    step = StepVideos(state, Path("ffprobe"), probe=lambda _ffprobe, path: media(path))
    data = QMimeData()
    data.setUrls([QUrl.fromLocalFile(str(folder))])
    event = QDropEvent(
        QPointF(0, 0),
        Qt.DropAction.CopyAction,
        data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    step.dropEvent(event)

    wait_until(lambda: len(state.videos) == 2 and all(entry.media for entry in state.videos))
    assert {entry.path.name for entry in state.videos} == {"one.mkv", "two.MP4"}
    assert "Ready" in step.video_list.item(0).text()


def test_probe_errors_are_visible_and_selected_videos_can_be_removed(tmp_path: Path, qapp) -> None:
    broken = tmp_path / "broken.mkv"
    good = tmp_path / "good.mkv"
    broken.touch()
    good.touch()

    def probe(_ffprobe: Path, path: Path) -> MediaInfo:
        if path == broken:
            raise RuntimeError("invalid media")
        return media(path)

    state = WizardState(Config())
    step = StepVideos(state, Path("ffprobe"), probe=probe)
    step.add_paths([broken])

    wait_until(lambda: state.videos and state.videos[0].error is not None)
    item = step.video_list.item(0)
    assert error_text("probe_failed") in item.text()
    assert item.toolTip() == "invalid media"

    step.add_paths([good])
    wait_until(lambda: any(entry.media for entry in state.videos))
    step.video_list.item(0).setSelected(True)
    step.remove_selected()

    assert [entry.path.name for entry in state.videos] == ["good.mkv"]


def quality_media(
    path: Path,
    *,
    height: int = 1080,
    duration: float = 60.0,
    size: int = 6_700_000_000,
    bitrate: int | None = 640_000,
) -> MediaInfo:
    return MediaInfo(
        path,
        "matroska",
        duration,
        size,
        [VideoStream(0, "h264", round(height * 16 / 9), height, 24)],
        [AudioStream(1, "aac", 2, "eng", True, bitrate=bitrate)],
        [],
        [],
    )


def add_quality_video(
    state: WizardState,
    tmp_path: Path,
    name: str,
    *,
    height: int = 1080,
    duration: float = 60.0,
    size: int = 6_700_000_000,
) -> Path:
    path = tmp_path / name
    path.touch()
    state.add_paths([path])
    state.set_media(path, quality_media(path, height=height, duration=duration, size=size))
    return path.resolve()


def install_levels_worker(
    step: StepQuality,
    *,
    paused: bool = False,
    estimates: dict[str, TotalEstimate] | None = None,
) -> list:
    instances: list = []
    payload = estimates if estimates is not None else level_estimates()

    class Worker(QObject):
        progress = Signal(float)
        done = Signal(object)
        failed = Signal(str, str)
        finished = Signal()

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            super().__init__()
            self.cancelled = False
            self.started = threading.Event()
            self.release = threading.Event()
            if not paused:
                self.release.set()
            instances.append(self)

        def run(self) -> None:
            self.started.set()
            self.release.wait(timeout=10)
            if self.cancelled:
                self.failed.emit("cancelled", "")
                self.finished.emit()
                return
            self.progress.emit(1.0)
            self.done.emit(payload)
            self.finished.emit()

        def cancel(self) -> None:
            self.cancelled = True
            self.release.set()

    step._levels_worker_factory = Worker
    return instances


def level_estimates() -> dict[str, TotalEstimate]:
    return {
        "high": TotalEstimate(4_000_000_000, 19_200_000, 0, 4_019_200_000, 0.6, 50.0),
        "balanced": TotalEstimate(3_480_800_000, 19_200_000, 0, 3_500_000_000, 0.52, 50.0),
        "max_savings": TotalEstimate(1_500_000_000, None, 0, None, None, 50.0),
    }


def test_quality_shows_notes_and_technical_details(tmp_path: Path, qapp) -> None:
    state = WizardState(Config())
    add_quality_video(state, tmp_path, "short.mkv", duration=30.0)
    add_quality_video(state, tmp_path, "long.mkv", duration=120.0, size=2_000_000_000)
    step = StepQuality(state, ffmpeg_info())

    assert not step.common_notes.isHidden()
    assert step.common_notes.text().count("• ") == 2
    assert "The video is re-encoded to H.264" in step.common_notes.text()
    assert "The resolution stays at 1920x1080" in step.common_notes.text()
    assert "Very little detail is lost" in step.cards["high"].notes_label.text()
    assert "H.264" not in step.cards["high"].notes_label.text()
    assert "slightly smoothed" in step.cards["balanced"].notes_label.text()
    assert "Dark scenes" in step.cards["max_savings"].notes_label.text()

    assert not step.reference_label.isHidden()
    assert "long.mkv" in step.reference_label.text()

    details = step.technical_details.content.text()
    assert "A video stores each frame" in details
    assert "Codec: libx264" in details
    assert "Preset: medium" in details
    assert "CRF: 22" in details
    assert "Profile: high" in details
    assert "Level: 4.1" in details
    assert "Pixel format: yuv420p" in details
    assert step.technical_details.button.text() == "Technical details"


def test_quality_without_media_hides_notes_and_button(tmp_path: Path, qapp) -> None:
    path = tmp_path / "pending.mkv"
    path.touch()
    state = WizardState(Config())
    state.add_paths([path])
    step = StepQuality(state, ffmpeg_info())

    assert step.cards["balanced"].notes_label.isHidden()
    assert step.common_notes.isHidden()
    assert step.levels_button.isHidden()
    assert not step.levels_button.isEnabled()
    assert step.levels_hint.isHidden()
    assert step.reference_label.isHidden()


def test_quality_hint_explains_how_long_the_estimate_takes(tmp_path: Path, qapp) -> None:
    state = WizardState(Config())
    add_quality_video(state, tmp_path, "movie.mkv")
    step = StepQuality(state, ffmpeg_info())

    assert not step.levels_hint.isHidden()
    assert step.levels_hint.property("role") == "muted"
    assert "couple of minutes" in step.levels_hint.text()


def test_quality_resolution_selector_follows_the_videos_and_the_state(tmp_path: Path, qapp) -> None:
    state = WizardState(Config())
    add_quality_video(state, tmp_path, "fullhd.mkv")
    step = StepQuality(state, ffmpeg_info())
    combo = step.resolution_combo

    assert not combo.isHidden()
    assert [combo.itemText(index) for index in range(combo.count())] == [
        "Automatic",
        "720p",
        "480p",
    ]
    assert combo.currentIndex() == 0

    combo.setCurrentIndex(combo.findText("720p"))

    assert state.max_height == 720
    assert step.levels_button.isEnabled()

    state.set_max_height(1080)

    assert combo.currentText() == "1080p"

    state.set_max_height(None)

    assert combo.currentText() == "Automatic"

    small = WizardState(Config())
    add_quality_video(small, tmp_path, "sd.mkv", height=480)
    small_step = StepQuality(small, ffmpeg_info())

    assert small_step.resolution_combo.isHidden()
    assert small_step.resolution_label.isHidden()


def test_quality_estimates_each_level_and_invalidates_on_state_changes(
    tmp_path: Path, qapp
) -> None:
    state = WizardState(Config())
    add_quality_video(state, tmp_path, "movie.mkv")
    step = StepQuality(state, ffmpeg_info())
    install_levels_worker(step)

    step.levels_button.click()

    wait_until(lambda: not step.cards["balanced"].estimate_label.isHidden())
    wait_until(lambda: step._levels_thread is None)
    assert step.cards["high"].estimate_label.text() == "About 4.0 GB (40% smaller)"
    assert step.cards["balanced"].estimate_label.text() == "About 3.5 GB (48% smaller)"
    assert step.cards["max_savings"].estimate_label.text() == "Video only: about 1.5 GB"
    assert step.levels_progress.isHidden()
    assert step.levels_cancel_button.isHidden()
    assert step.levels_button.isEnabled()

    step.cards["high"].click()

    assert not step.cards["balanced"].estimate_label.isHidden()

    state.set_destination("modern")

    assert step.cards["balanced"].estimate_label.isHidden()
    assert step.cards["high"].estimate_label.isHidden()

    step.levels_button.click()

    wait_until(lambda: not step.cards["balanced"].estimate_label.isHidden())
    wait_until(lambda: step._levels_thread is None)
    step.resolution_combo.setCurrentIndex(step.resolution_combo.findText("720p"))

    assert state.max_height == 720
    assert step.cards["balanced"].estimate_label.isHidden()


def test_quality_says_when_a_level_is_not_smaller_than_the_original(tmp_path: Path, qapp) -> None:
    state = WizardState(Config())
    add_quality_video(state, tmp_path, "movie.mkv")
    step = StepQuality(state, ffmpeg_info())
    install_levels_worker(
        step,
        estimates={
            "high": TotalEstimate(7_000_000_000, 19_200_000, 0, 7_019_200_000, 1.05, 50.0),
            "balanced": TotalEstimate(6_700_000_000, 0, 0, 6_700_000_000, 1.0, 50.0),
            "max_savings": TotalEstimate(1_500_000_000, None, 0, None, None, 50.0),
        },
    )

    step.levels_button.click()

    wait_until(lambda: not step.cards["high"].estimate_label.isHidden())
    wait_until(lambda: step._levels_thread is None)
    assert step.cards["high"].estimate_label.text() == (
        "About 7.0 GB (not smaller than the original)"
    )
    assert step.cards["balanced"].estimate_label.text() == (
        "About 6.7 GB (not smaller than the original)"
    )
    assert step.cards["max_savings"].estimate_label.text() == "Video only: about 1.5 GB"


def test_quality_cancel_returns_to_the_initial_state(tmp_path: Path, qapp) -> None:
    state = WizardState(Config())
    add_quality_video(state, tmp_path, "movie.mkv")
    step = StepQuality(state, ffmpeg_info())
    instances = install_levels_worker(step, paused=True)

    step.levels_button.click()

    wait_until(lambda: instances and instances[0].started.is_set())
    assert not step.levels_progress.isHidden()
    assert not step.levels_cancel_button.isHidden()
    assert not step.levels_button.isEnabled()

    step.levels_cancel_button.click()

    assert instances[0].cancelled
    assert step.levels_progress.isHidden()
    assert step.levels_cancel_button.isHidden()
    assert step.cards["balanced"].estimate_label.isHidden()
    assert step.levels_button.isEnabled()
    assert step._levels_thread is None


def test_closing_the_window_cancels_a_running_quality_estimate(tmp_path: Path, qapp) -> None:
    window = MainWindow(Config(), ffmpeg_info(), ThemeManager(qapp))
    add_quality_video(window.wizard_state, tmp_path, "movie.mkv")
    instances = install_levels_worker(window.step_quality, paused=True)

    window.step_quality.levels_button.click()
    wait_until(lambda: instances and instances[0].started.is_set())

    window.close()

    assert instances[0].cancelled
    assert window.step_quality.levels_progress.isHidden()
    assert window.step_quality._levels_thread is None
