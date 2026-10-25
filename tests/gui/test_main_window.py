# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Main window skeleton tests."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from reduvid.core.config import Config
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.gui.main_window import MainWindow
from reduvid.gui.theme.manager import ThemeManager
from reduvid.gui.theme.tokens import THEMES


def ffmpeg_info() -> FFmpegInfo:
    return FFmpegInfo(
        Path("ffmpeg"), Path("ffprobe"), "test", frozenset({"libx264"}), frozenset(), ()
    )


@pytest.mark.parametrize(("theme", "mode"), sorted(THEMES))
def test_window_is_created_for_every_theme(theme: str, mode: str, qapp) -> None:
    manager = ThemeManager(qapp)
    manager.apply(theme, mode)

    window = MainWindow(Config(theme=theme, color_mode=mode), ffmpeg_info(), manager)

    assert window.objectName() == "mainWindow"
    assert window.centralWidget() is not None
    assert window.content.count() == 6


def test_panels_have_the_expected_names_and_accessible_names(qapp) -> None:
    window = MainWindow(Config(), ffmpeg_info(), ThemeManager(qapp))

    assert window.step_list.objectName() == "stepList"
    assert window.content.objectName() == "content"
    assert window.queue_panel.objectName() == "queuePanel"
    assert window.splitter.objectName() == "bodySplitter"
    for widget in (
        window.step_list,
        window.content,
        window.queue_panel,
        window.preferences_button,
        window.wizard_button,
        window.advanced_button,
    ):
        assert widget.accessibleName()


def test_ui_mode_is_reflected_in_the_toggle(qapp) -> None:
    window = MainWindow(Config(ui_mode="advanced"), ffmpeg_info(), ThemeManager(qapp))

    assert window.ui_mode == "advanced"
    assert window.advanced_button.isChecked()
    assert not window.wizard_button.isChecked()

    window.wizard_button.click()

    assert window.ui_mode == "wizard"
    assert window.wizard_button.isChecked()
    assert not window.advanced_button.isChecked()


def test_layout_stacks_below_the_compact_width(qapp) -> None:
    window = MainWindow(Config(), ffmpeg_info(), ThemeManager(qapp))
    window.show()
    try:
        window.resize(800, 600)
        qapp.processEvents()
        assert window.splitter.orientation() == Qt.Orientation.Vertical

        window.resize(1200, 800)
        qapp.processEvents()
        assert window.splitter.orientation() == Qt.Orientation.Horizontal
    finally:
        window.close()


class FakeThread:
    def __init__(self) -> None:
        self.running = True
        self.quit_called = False
        self.waited = False

    def isRunning(self) -> bool:
        return self.running

    def quit(self) -> None:
        self.quit_called = True

    def wait(self, _timeout: int = 0) -> bool:
        self.waited = True
        self.running = False
        return True


class FakeWorker:
    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


class FakeMessageBox:
    Icon = QMessageBox.Icon
    ButtonRole = QMessageBox.ButtonRole
    choice = 0

    def __init__(self, _parent=None) -> None:
        self.buttons: list[str] = []

    def setIcon(self, _icon) -> None:
        pass

    def setWindowTitle(self, _title) -> None:
        pass

    def setText(self, _text) -> None:
        pass

    def setInformativeText(self, _text) -> None:
        pass

    def addButton(self, text: str, _role) -> str:
        self.buttons.append(text)
        return text

    def exec(self) -> None:
        pass

    def clickedButton(self) -> str:
        return self.buttons[self.choice]


def test_close_with_running_conversion_cancels_and_waits(
    monkeypatch: pytest.MonkeyPatch, qapp
) -> None:
    window = MainWindow(Config(), ffmpeg_info(), ThemeManager(qapp))
    thread = FakeThread()
    worker = FakeWorker()
    window.queue_thread = thread  # type: ignore[assignment]
    window.queue_worker = worker  # type: ignore[assignment]
    FakeMessageBox.choice = 0
    monkeypatch.setattr("reduvid.gui.main_window.QMessageBox", FakeMessageBox)

    assert window.close()

    assert worker.cancelled
    assert thread.quit_called
    assert thread.waited


def test_close_keeps_converting_when_the_user_declines(
    monkeypatch: pytest.MonkeyPatch, qapp
) -> None:
    window = MainWindow(Config(), ffmpeg_info(), ThemeManager(qapp))
    thread = FakeThread()
    worker = FakeWorker()
    window.queue_thread = thread  # type: ignore[assignment]
    window.queue_worker = worker  # type: ignore[assignment]
    FakeMessageBox.choice = 1
    monkeypatch.setattr("reduvid.gui.main_window.QMessageBox", FakeMessageBox)

    assert not window.close()

    assert not worker.cancelled
    assert not thread.quit_called
