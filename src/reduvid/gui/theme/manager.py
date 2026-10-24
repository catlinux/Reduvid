# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Apply a theme and colour mode to the Qt application."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from reduvid.gui.theme.fonts import register_fonts
from reduvid.gui.theme.qss import build_qss
from reduvid.gui.theme.tokens import THEMES, ThemeTokens

THEME_NAMES = ("plegat", "riso", "cinta")
COLOR_MODES = ("system", "light", "dark")


class ThemeManager:
    """Keep the application stylesheet and font in sync with a theme."""

    def __init__(self, app: QApplication) -> None:
        self._app = app
        self._theme = "plegat"
        self._mode = "system"
        app.styleHints().colorSchemeChanged.connect(self._on_color_scheme_changed)

    @property
    def theme(self) -> str:
        return self._theme

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def tokens(self) -> ThemeTokens:
        return THEMES[(self._theme, self._resolved_mode())]

    def apply(self, theme: str, mode: str) -> None:
        """Apply *theme* with *mode*; ``system`` follows the desktop colour scheme."""
        if theme not in THEME_NAMES:
            raise ValueError(f"Unknown theme: {theme}")
        if mode not in COLOR_MODES:
            raise ValueError(f"Unknown colour mode: {mode}")

        self._theme = theme
        self._mode = mode
        tokens = THEMES[(theme, self._resolved_mode())]
        register_fonts()
        self._app.setFont(QFont(_first_family(tokens.body), -1, tokens.body_weight))
        self._app.setStyleSheet(build_qss(tokens))

    def _resolved_mode(self) -> str:
        if self._mode in ("light", "dark"):
            return self._mode
        scheme = self._app.styleHints().colorScheme()
        return "dark" if scheme == Qt.ColorScheme.Dark else "light"

    def _on_color_scheme_changed(self, *_args: object) -> None:
        if self._mode == "system":
            self.apply(self._theme, self._mode)


def _first_family(families: str) -> str:
    """Pick the first real family from a CSS-style family list."""
    return families.split(",", 1)[0].strip().strip("\"'")
