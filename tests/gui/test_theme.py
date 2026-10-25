# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Stylesheet, font registration and theme manager tests."""

from __future__ import annotations

import re

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt

from reduvid.gui.theme.fonts import FONTS_DIR, register_fonts
from reduvid.gui.theme.manager import ThemeManager
from reduvid.gui.theme.qss import build_qss
from reduvid.gui.theme.tokens import THEMES

UNRESOLVED_MARKER = re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?")


@pytest.mark.parametrize(("theme", "mode"), sorted(THEMES))
def test_build_qss_substitutes_every_token(theme: str, mode: str, qapp) -> None:
    tokens = THEMES[(theme, mode)]
    stylesheet = build_qss(tokens)

    assert not UNRESOLVED_MARKER.search(stylesheet)
    assert tokens.bg in stylesheet
    assert tokens.accent in stylesheet
    assert "#stepList" in stylesheet
    assert "#queuePanel" in stylesheet
    assert "#warnChip" in stylesheet
    assert 'QFrame#card[checked="true"]' in stylesheet
    assert 'QPushButton[role="primary"]' in stylesheet
    assert "QProgressBar::chunk" in stylesheet


def test_register_fonts_loads_every_bundled_file(qapp) -> None:
    font_files = sorted(FONTS_DIR.rglob("*.ttf"))

    loaded = register_fonts()

    assert len(font_files) == 14
    assert len(loaded) == len(font_files)
    assert all(loaded.values())


def test_register_fonts_is_idempotent(qapp) -> None:
    assert register_fonts() == register_fonts()


@pytest.mark.parametrize(("theme", "mode"), sorted(THEMES))
def test_manager_applies_every_theme(theme: str, mode: str, qapp) -> None:
    manager = ThemeManager(qapp)

    manager.apply(theme, mode)

    assert manager.theme == theme
    assert manager.mode == mode
    assert qapp.styleSheet() == build_qss(THEMES[(theme, mode)])
    assert qapp.font().family()


class FakeSignal:
    def __init__(self) -> None:
        self.slots: list[object] = []

    def connect(self, slot: object) -> None:
        self.slots.append(slot)

    def emit(self, *args: object) -> None:
        for slot in self.slots:
            slot(*args)  # type: ignore[operator]


class FakeStyleHints:
    def __init__(self, scheme: Qt.ColorScheme) -> None:
        self.scheme = scheme
        self.colorSchemeChanged = FakeSignal()

    def colorScheme(self) -> Qt.ColorScheme:
        return self.scheme


class FakeApp:
    def __init__(self, hints: FakeStyleHints) -> None:
        self.hints = hints
        self.stylesheet = ""
        self.font = None
        self.style_name: str | None = None

    def styleHints(self) -> FakeStyleHints:
        return self.hints

    def setFont(self, font: object) -> None:
        self.font = font

    def setStyleSheet(self, stylesheet: str) -> None:
        self.stylesheet = stylesheet

    def setStyle(self, style_name: str) -> None:
        self.style_name = style_name


def test_manager_resolves_system_mode(qapp) -> None:
    manager = ThemeManager(qapp)

    manager.apply("plegat", "system")

    assert qapp.styleSheet() in {
        build_qss(THEMES[("plegat", "light")]),
        build_qss(THEMES[("plegat", "dark")]),
    }


def test_manager_follows_system_scheme_changes(qapp) -> None:
    hints = FakeStyleHints(Qt.ColorScheme.Dark)
    app = FakeApp(hints)
    manager = ThemeManager(app)  # type: ignore[arg-type]

    manager.apply("riso", "system")
    assert app.stylesheet == build_qss(THEMES[("riso", "dark")])

    hints.scheme = Qt.ColorScheme.Light
    hints.colorSchemeChanged.emit(Qt.ColorScheme.Light)
    assert app.stylesheet == build_qss(THEMES[("riso", "light")])

    manager.apply("cinta", "light")
    hints.scheme = Qt.ColorScheme.Dark
    hints.colorSchemeChanged.emit(Qt.ColorScheme.Dark)
    assert app.stylesheet == build_qss(THEMES[("cinta", "light")])


def test_manager_rejects_unknown_values(qapp) -> None:
    manager = ThemeManager(qapp)

    with pytest.raises(ValueError, match="theme"):
        manager.apply("otro", "light")
    with pytest.raises(ValueError, match="mode"):
        manager.apply("plegat", "auto")
