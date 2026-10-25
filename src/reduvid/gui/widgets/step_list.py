# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Step list with done, current and pending states."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QPushButton, QVBoxLayout, QWidget

from reduvid.i18n import _


class StepList(QWidget):
    """Accessible list of steps that reports the chosen one."""

    selected = Signal(int)

    def __init__(self, titles: Sequence[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("stepList")
        self.setAccessibleName(_("Wizard steps"))
        self._current = 0
        self._buttons: list[QPushButton] = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 20, 14, 20)
        layout.setSpacing(4)
        for index, title in enumerate(titles):
            button = QPushButton(f"{index + 1}. {title}", self)
            button.setObjectName("stepButton")
            button.setAccessibleName(title)
            button.setCheckable(True)
            button.setMinimumWidth(0)
            self._group.addButton(button, index)
            layout.addWidget(button)
            self._buttons.append(button)
        layout.addStretch(1)
        self._group.idClicked.connect(self.selected.emit)
        self.set_current(0)

    @property
    def current(self) -> int:
        return self._current

    @property
    def buttons(self) -> tuple[QPushButton, ...]:
        return tuple(self._buttons)

    @property
    def states(self) -> tuple[str, ...]:
        return tuple(
            "done" if index < self._current else "current" if index == self._current else "pending"
            for index in range(len(self._buttons))
        )

    def set_current(self, index: int) -> None:
        if not 0 <= index < len(self._buttons):
            raise IndexError(index)
        self._current = index
        for position, button in enumerate(self._buttons):
            state = "done" if position < index else "current" if position == index else "pending"
            button.setProperty("state", state)
            button.setChecked(position == index)
            button.style().unpolish(button)
            button.style().polish(button)
