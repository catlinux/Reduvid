# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Themed progress bar tests for the six theme sets."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QTimer
from PySide6.QtGui import QPixmap

from reduvid.gui.theme.tokens import THEMES
from reduvid.gui.widgets.progress import ThemedProgressBar


@pytest.mark.parametrize("key", sorted(THEMES))
@pytest.mark.parametrize("value", [0, 25, 50, 75, 100])
def test_progress_paints_for_every_theme_and_value(key: tuple[str, str], value: int, qapp) -> None:
    bar = ThemedProgressBar(tokens=THEMES[key], reduce_motion=False)
    bar.resize(280, 20)
    bar.setRange(0, 100)
    bar.setValue(value)
    try:
        pixmap = bar.grab()
        assert not pixmap.isNull()
    finally:
        bar.deleteLater()


def test_progress_api_and_clamping(qapp) -> None:
    bar = ThemedProgressBar(tokens=THEMES[("plegat", "light")], reduce_motion=True)
    try:
        bar.setRange(0, 100)
        bar.setValue(42)
        assert bar.value() == 42
        assert bar.minimum() == 0
        assert bar.maximum() == 100

        bar.setValue(150)
        assert bar.value() == 100
        bar.setValue(-5)
        assert bar.value() == 0

        bar.setRange(10, 20)
        bar.setValue(15)
        assert bar.value() == 15
        bar.setRange(20, 10)
        assert bar.minimum() == 20
        assert bar.maximum() == 20
    finally:
        bar.deleteLater()


@pytest.mark.parametrize("reduce_motion", [True, False])
def test_progress_never_creates_timers(reduce_motion: bool, qapp) -> None:
    bar = ThemedProgressBar(tokens=THEMES[("riso", "dark")], reduce_motion=reduce_motion)
    try:
        assert bar.reduce_motion is reduce_motion
        assert bar.findChildren(QTimer) == []
        bar.setValue(30)
        bar.grab()
        assert bar.findChildren(QTimer) == []
    finally:
        bar.deleteLater()


def test_progress_accepts_theme_changes(qapp) -> None:
    bar = ThemedProgressBar(tokens=THEMES[("plegat", "light")], reduce_motion=True)
    try:
        bar.resize(200, 20)
        bar.setValue(50)
        for key in THEMES:
            bar.set_theme_tokens(THEMES[key])
            pixmap = QPixmap(200, 20)
            bar.render(pixmap)
            assert not pixmap.isNull()
    finally:
        bar.deleteLater()
