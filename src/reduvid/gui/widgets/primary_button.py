# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Primary action button with the Riso offset-shadow motif."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import QPushButton, QWidget

from reduvid.gui.theme.active import active_tokens
from reduvid.gui.widgets.motifs import draw_offset_shadow


class PrimaryButton(QPushButton):
    """A primary button; Riso paints its misregistered ink shadow."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setProperty("role", "primary")
        self.style().unpolish(self)
        self.style().polish(self)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        tokens = active_tokens()
        if tokens.fold is not None or tokens.accent3 is not None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.0, 0.0, -1.0, -1.0)
        draw_offset_shadow(painter, rect, tokens)
        painter.end()
