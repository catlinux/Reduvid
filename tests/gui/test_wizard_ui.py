# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Assistant widgets, steps and navigation tests (offscreen, fake probes)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QButtonGroup

from reduvid.core.config import Config
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.probe import MediaInfo
from reduvid.gui.main_window import MainWindow
from reduvid.gui.theme.manager import ThemeManager
from reduvid.gui.widgets.option_card import OptionCard
from reduvid.gui.widgets.step_list import StepList
from reduvid.gui.widgets.wizard_nav import WizardNav
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


def test_target_cards_are_exclusive_and_unknown_uses_jellyfin(qapp) -> None:
    window = MainWindow(Config(), ffmpeg_info(), ThemeManager(qapp))
    target = window.content.widget(1)

    target.cards["modern"].click()
    assert window.wizard_state.destination == "modern"
    assert target.cards["modern"].isChecked()
    assert not target.cards["jellyfin"].isChecked()

    target.cards["unknown"].click()
    assert target.cards["unknown"].isChecked()
    assert window.wizard_state.options().destination == "jellyfin"


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
