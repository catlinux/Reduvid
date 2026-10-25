# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""User-facing error message with optional technical details."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QToolButton, QVBoxLayout, QWidget

from reduvid.i18n import _
from reduvid.messages import error_text


class ErrorView(QWidget):
    """Show a translated error and a collapsible, copyable technical detail."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("errorView")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.message_label = QLabel(self)
        self.message_label.setObjectName("errorMessage")
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        self.details_button = QToolButton(self)
        self.details_button.setObjectName("detailsButton")
        self.details_button.setAccessibleName(_("Show technical details"))
        self.details_button.setCheckable(True)
        self.details_button.setText(_("Show technical details"))
        self.details_button.toggled.connect(self._toggle_details)
        layout.addWidget(self.details_button)

        self.details = QPlainTextEdit(self)
        self.details.setObjectName("technicalDetails")
        self.details.setAccessibleName(_("Technical details"))
        self.details.setReadOnly(True)
        self.details.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.details.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.details.setVisible(False)
        layout.addWidget(self.details)

    def set_error(self, code: str, reason: str | None = None) -> None:
        """Show the translated text for *code* and hide the details again."""
        self.message_label.setText(error_text(code))
        self.details.setPlainText(reason or "")
        self.details_button.setChecked(False)
        self.details.setVisible(False)
        self.details_button.setVisible(bool(reason))
        self._toggle_details(False)

    def toggle_details(self) -> None:
        self.details_button.setChecked(not self.details_button.isChecked())

    def _toggle_details(self, visible: bool) -> None:
        self.details.setVisible(visible)
        self.details_button.setText(
            _("Hide technical details") if visible else _("Show technical details")
        )
