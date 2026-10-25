# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Primary/danger roles and the recommended option-card state."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from reduvid.core.config import Config
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.gui.main_window import MainWindow
from reduvid.gui.theme.active import set_active_tokens
from reduvid.gui.theme.manager import ThemeManager
from reduvid.gui.theme.tokens import THEMES
from reduvid.gui.widgets.primary_button import PrimaryButton


def ffmpeg_info() -> FFmpegInfo:
    return FFmpegInfo(
        Path("ffmpeg"), Path("ffprobe"), "test", frozenset({"libx264"}), frozenset(), ()
    )


def test_main_actions_use_primary_and_danger_roles(qapp) -> None:
    window = MainWindow(Config(), ffmpeg_info(), ThemeManager(qapp))

    assert window.wizard_nav.next_button.property("role") == "primary"
    assert window.step_summary.start_button.property("role") == "primary"
    assert window.advanced_page.summary.start_button.property("role") == "primary"
    assert window.queue_panel.cancel_button.property("role") == "danger"
    assert not window.queue_panel.pause_button.property("role")
    assert not window.wizard_nav.back_button.property("role")


def test_quality_cards_mark_the_recommended_one(qapp) -> None:
    window = MainWindow(Config(), ffmpeg_info(), ThemeManager(qapp))
    quality = window.content.widget(2)

    assert quality.cards["balanced"].property("recommended") is True
    assert quality.cards["high"].property("recommended") is False

    quality.cards["high"].click()
    assert quality.cards["high"].isChecked()
    assert quality.cards["balanced"].property("recommended") is True

    window.wizard_state.set_destination("archive")

    assert quality.cards["max_savings"].property("recommended") is True
    assert quality.cards["balanced"].property("recommended") is False


def test_primary_button_paints_in_riso(qapp) -> None:
    set_active_tokens(THEMES[("riso", "light")])
    button = PrimaryButton("&Start")
    button.resize(140, 36)
    try:
        assert not button.grab().isNull()
    finally:
        button.deleteLater()
        set_active_tokens(THEMES[("plegat", "light")])
