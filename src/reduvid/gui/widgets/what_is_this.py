# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Collapsible explanation used in the assistant steps."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QToolButton, QVBoxLayout, QWidget

from reduvid.i18n import _


class WhatIsThis(QWidget):
    """A small disclosure with the plain-language explanation of a concept."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("whatIsThis")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.button = QToolButton(self)
        self.button.setObjectName("whatIsThisButton")
        self.button.setCheckable(True)
        self.button.setText(_("&What is this?"))
        self.button.setAccessibleName(_("&What is this?"))
        self.button.toggled.connect(self._toggle)
        layout.addWidget(self.button)

        self.content = QLabel(text, self)
        self.content.setObjectName("whatIsThisContent")
        self.content.setAccessibleName(_("Explanation"))
        self.content.setWordWrap(True)
        self.content.setVisible(False)
        layout.addWidget(self.content)

    def set_text(self, text: str) -> None:
        self.content.setText(text)

    def _toggle(self, visible: bool) -> None:
        self.content.setVisible(visible)
