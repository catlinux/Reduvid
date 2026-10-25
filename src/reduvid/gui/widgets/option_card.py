# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Selectable card used for destination and quality choices."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class OptionCard(QAbstractButton):
    """A checkable card with a name, an optional tag and a description."""

    def __init__(
        self,
        name: str,
        label: str,
        description: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setAccessibleName(name)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        header = QHBoxLayout()
        self.title_label = QLabel(name, self)
        self.title_label.setWordWrap(True)
        self.tag_label = QLabel(label, self)
        self.tag_label.setProperty("role", "kicker")
        self.tag_label.setWordWrap(True)
        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(self.tag_label)
        layout.addLayout(header)

        self.description_label = QLabel(description, self)
        self.description_label.setProperty("role", "muted")
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)

        self.set_label(label)
        self.toggled.connect(self._on_toggled)

    def set_label(self, label: str) -> None:
        """Show or hide the card tag and refresh its accessible description."""
        self.tag_label.setText(label)
        self.tag_label.setVisible(bool(label))
        parts = [self.accessibleName(), label, self.description_label.text()]
        description = ". ".join(part for part in parts if part)
        self.setAccessibleDescription(description)

    def _on_toggled(self, _checked: bool) -> None:
        # Repolish so the QSS [checked="true"] rule takes effect immediately.
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
