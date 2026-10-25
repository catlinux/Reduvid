# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Back and next controls for the assistant."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from reduvid.gui.widgets.primary_button import PrimaryButton
from reduvid.i18n import _


class WizardNav(QWidget):
    """Navigation bar with a contextual next button."""

    back_clicked = Signal()
    next_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("wizardNav")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.back_button = QPushButton(_("&Back"), self)
        self.back_button.setObjectName("backButton")
        self.back_button.setAccessibleName(_("&Back"))
        self.back_button.setMinimumWidth(0)
        self.back_button.clicked.connect(self.back_clicked.emit)
        self.next_button = PrimaryButton(_("&Next"), self)
        self.next_button.setObjectName("nextButton")
        self.next_button.setAccessibleName(_("&Next"))
        self.next_button.setMinimumWidth(0)
        self.next_button.clicked.connect(self.next_clicked.emit)
        layout.addWidget(self.back_button)
        layout.addStretch(1)
        layout.addWidget(self.next_button)
        QWidget.setTabOrder(self.back_button, self.next_button)

    def set_back_enabled(self, enabled: bool) -> None:
        self.back_button.setEnabled(enabled)

    def set_next_enabled(self, enabled: bool) -> None:
        self.next_button.setEnabled(enabled)

    def set_next_text(self, step: str | None) -> None:
        if step is None:
            self.next_button.setText(_("&Next"))
            self.next_button.setAccessibleName(_("&Next"))
            return
        self.next_button.setText(_("&Next: {step}").format(step=step))
        self.next_button.setAccessibleName(_("&Next: {step}").format(step=step))
