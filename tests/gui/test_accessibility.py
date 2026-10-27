# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Accessibility, mnemonics, focus styles and font scaling tests."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QWidget,
)

from reduvid.core.config import Config
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.probe import AudioStream, MediaInfo, SubtitleStream, VideoStream
from reduvid.gui.error_view import ErrorView
from reduvid.gui.ffmpeg_missing import FFmpegMissingWidget
from reduvid.gui.main_window import MainWindow
from reduvid.gui.preferences import PreferencesDialog
from reduvid.gui.queue_panel import QueuePanel
from reduvid.gui.theme.manager import ThemeManager
from reduvid.gui.theme.qss import build_qss
from reduvid.gui.theme.tokens import THEMES
from reduvid.gui.widgets.option_card import OptionCard
from reduvid.i18n import setup_language

INTERACTIVE = (
    QAbstractButton,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QListWidget,
    QTextEdit,
    QPlainTextEdit,
)


def ffmpeg_info() -> FFmpegInfo:
    return FFmpegInfo(
        Path("ffmpeg"), Path("ffprobe"), "test", frozenset({"libx264"}), frozenset(), ()
    )


def media(path: Path) -> MediaInfo:
    return MediaInfo(
        path,
        "matroska",
        60.0,
        1000,
        [VideoStream(0, "h264", 1920, 1080, 24)],
        [
            AudioStream(1, "aac", 2, "eng", True),
            AudioStream(2, "aac", 2, "spa", False),
        ],
        [SubtitleStream(3, "subrip", "eng", False, False, False)],
        [],
    )


def build_widgets(tmp_path: Path, qapp) -> list[tuple[str, QWidget]]:
    manager = ThemeManager(qapp)
    window = MainWindow(Config(), ffmpeg_info(), manager)
    video = tmp_path / "video.mkv"
    video.touch()
    window.wizard_state.add_paths([video])
    window.wizard_state.set_media(video, media(video))
    window.set_current_step(5)
    preferences = PreferencesDialog(Config(), manager)
    missing = FFmpegMissingWidget(Config())
    queue = QueuePanel()
    error = ErrorView()
    error.set_error("unknown", "technical detail")
    pages: list[tuple[str, QWidget]] = [
        ("window", window),
        ("topBar", window.findChild(QWidget, "topBar")),
        ("wizardNav", window.wizard_nav),
        ("queue", queue),
        ("preferences", preferences),
        ("missing", missing),
        ("error", error),
        ("advanced", window.advanced_page),
    ]
    for index in range(window.content.count()):
        page = window.content.widget(index)
        if page is not None:
            pages.append((f"step{index}", page))
    return [entry for entry in pages if entry[1] is not None]


def _has_accessible_name(control: QWidget) -> bool:
    if control.accessibleName().strip():
        return True
    if isinstance(control, QAbstractButton):
        return bool(control.text().replace("&", "").strip())
    window = control.window()
    for label in window.findChildren(QLabel):
        if label.buddy() is control and label.text().strip():
            return True
    return False


def test_every_interactive_control_has_a_name(tmp_path: Path, qapp) -> None:
    missing: list[str] = []
    for page_name, page in build_widgets(tmp_path, qapp):
        if page_name == "window":
            continue
        for control in page.findChildren(QWidget):
            if not isinstance(control, INTERACTIVE):
                continue
            if control.objectName().startswith("qt_"):
                continue
            if isinstance(control.parent(), QSpinBox):
                continue
            if not _has_accessible_name(control):
                missing.append(f"{page_name}: {type(control).__name__} {control.objectName()!r}")
    assert missing == []


def test_option_cards_keep_a_description(tmp_path: Path, qapp) -> None:
    for page_name, page in build_widgets(tmp_path, qapp):
        if page_name == "window":
            continue
        for card in page.findChildren(OptionCard):
            assert card.accessibleName()
            assert card.accessibleDescription()


def test_option_card_estimate_and_notes_stay_hidden_until_set(qapp) -> None:
    card = OptionCard("Jellyfin", "Recommended", "Streams to your TV")
    description = card.accessibleDescription()

    card.set_estimate("")

    assert card.estimate_label.isHidden()
    assert card.notes_label.isHidden()
    assert card.accessibleDescription() == description


def test_option_card_estimate_and_notes_feed_the_description(qapp) -> None:
    card = OptionCard("Jellyfin", "Recommended", "Streams to your TV")

    card.set_estimate("About 1.2 GB")
    card.set_notes(["Keeps HDR", "Same audio tracks"])

    assert not card.estimate_label.isHidden()
    assert card.estimate_label.objectName() == "cardEstimate"
    assert not card.notes_label.isHidden()
    assert card.notes_label.objectName() == "cardNotes"
    assert card.notes_label.text() == "• Keeps HDR\n• Same audio tracks"
    description = card.accessibleDescription()
    assert "About 1.2 GB" in description
    assert "Keeps HDR" in description
    assert "Same audio tracks" in description

    card.set_notes([])

    assert card.notes_label.isHidden()
    assert "About 1.2 GB" in card.accessibleDescription()


def _mnemonics(root: QWidget) -> list[str]:
    values: list[str] = []
    for button in root.findChildren(QAbstractButton):
        match = re.search(r"&(?!&)(.)", button.text())
        if match is not None:
            values.append(match.group(1).casefold())
    return values


def test_mnemonics_are_unique_within_each_page(tmp_path: Path, qapp) -> None:
    expected = {
        "topBar": {"w", "a", "p"},
        "wizardNav": {"b", "n"},
        "queue": {"p", "c"},
        "preferences": {"a", "c", "b"},
        "missing": {"c", "s"},
        "step5": {"s"},
    }
    for page_name, page in build_widgets(tmp_path, qapp):
        if page_name == "window":
            continue
        values = _mnemonics(page)
        assert len(values) == len(set(values)), f"{page_name}: duplicated mnemonic in {values}"
        if page_name in expected:
            assert set(values) == expected[page_name]


@pytest.mark.parametrize(
    ("language", "next_text", "start_text"),
    [
        ("ca", "&Següent", "&Comença"),
        ("es", "&Siguiente", "&Comenzar"),
    ],
)
def test_translated_mnemonics_are_kept(
    language: str, next_text: str, start_text: str, tmp_path: Path, qapp
) -> None:
    setup_language(language)
    try:
        window = MainWindow(Config(), ffmpeg_info(), ThemeManager(qapp))
        assert window.wizard_nav.next_button.text().startswith(next_text)
        assert window.step_summary.start_button.text().startswith(start_text)
        assert window.queue_panel.pause_button.text().startswith("&")
        assert window.preferences_button.text().startswith("&")
        dialog = PreferencesDialog(Config(), ThemeManager(qapp))
        ok_button = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert ok_button is not None
        assert ok_button.text().startswith("&")
        for page_name, page in build_widgets(tmp_path, qapp):
            if page_name == "window":
                continue
            values = _mnemonics(page)
            assert len(values) == len(set(values)), f"{page_name}: {values}"
    finally:
        setup_language("en")


def test_focus_rules_exist_for_all_themes() -> None:
    selectors = (
        "QPushButton:focus",
        "QLineEdit:focus",
        "QComboBox:focus",
        "QSpinBox:focus",
        "QCheckBox:focus",
        "QRadioButton:focus",
        "QListWidget:focus",
        "QAbstractButton#card:focus",
        "#stepList QPushButton:focus",
        "QToolButton:focus",
        "QPlainTextEdit:focus",
    )
    for key in THEMES:
        stylesheet = build_qss(THEMES[key])
        for selector in selectors:
            assert selector in stylesheet, f"{key}: missing {selector}"


@pytest.mark.parametrize("scale", [1.5, 2.0])
def test_scaled_fonts_keep_long_texts_wrapped(scale: float, qapp) -> None:
    original = QFont(qapp.font())
    scaled = QFont(original)
    scaled.setPointSizeF(max(1.0, original.pointSizeF() * scale))
    qapp.setFont(scaled)
    try:
        window = MainWindow(Config(ui_mode="advanced"), ffmpeg_info(), ThemeManager(qapp))
        window.resize(1400, 900)
        window.show()
        qapp.processEvents()
        pages = [window.step_list, window.advanced_page]
        for index in range(window.content.count()):
            page = window.content.widget(index)
            if page is not None:
                pages.append(page)
        for page in pages:
            for label in page.findChildren(QLabel):
                if len(label.text()) > 40:
                    assert label.wordWrap(), f"label without wrap: {label.text()[:60]!r}"
            for control in page.findChildren(QWidget):
                if isinstance(control, (QPushButton, QLineEdit, QComboBox, QSpinBox)):
                    assert control.sizeHint().width() <= 900, (
                        f"{type(control).__name__} too wide: {control.sizeHint().width()}"
                    )
        window.close()
    finally:
        qapp.setFont(original)
