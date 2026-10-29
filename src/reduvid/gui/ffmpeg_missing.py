# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Screen shown when FFmpeg is not available."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from reduvid.core.config import Config, save_config
from reduvid.core.ffmpeg import describe_search, detect_ffmpeg
from reduvid.i18n import _


class FFmpegMissingWidget(QWidget):
    """Explain how to install FFmpeg and let the user point to it."""

    ffmpeg_found = Signal(object)

    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ffmpegMissing")
        self._config = config
        self._build_ui()

    @property
    def config(self) -> Config:
        return self._config

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(12)

        heading = QLabel(_("FFmpeg is required"), self)
        heading.setObjectName("ffmpegMissingTitle")
        heading.setProperty("role", "heading")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        explanation = QLabel(
            _(
                "Reduvid uses FFmpeg to convert videos. Install it, or choose the "
                "ffmpeg executable if you already have it."
            ),
            self,
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        layout.addWidget(self._command_row(_("Windows"), "winget install Gyan.FFmpeg"))
        layout.addWidget(self._command_row(_("Debian / Ubuntu"), "sudo apt install ffmpeg"))
        layout.addWidget(self._command_row(_("Fedora"), "sudo dnf install ffmpeg"))

        buttons = QHBoxLayout()
        self.choose_button = QPushButton(_("&Choose ffmpeg…"), self)
        self.choose_button.setObjectName("chooseFfmpegButton")
        self.choose_button.setAccessibleName(_("&Choose ffmpeg…"))
        self.choose_button.clicked.connect(self._choose_ffmpeg)
        self.retry_button = QPushButton(_("&Search again"), self)
        self.retry_button.setObjectName("retryFfmpegButton")
        self.retry_button.setAccessibleName(_("&Search again"))
        self.retry_button.clicked.connect(self._retry)
        buttons.addWidget(self.choose_button)
        buttons.addWidget(self.retry_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        QWidget.setTabOrder(self.choose_button, self.retry_button)

        self.status_label = QLabel(self)
        self.status_label.setObjectName("ffmpegMissingStatus")
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.details_label = QLabel(self)
        self.details_label.setObjectName("ffmpegMissingDetails")
        self.details_label.setProperty("role", "muted")
        self.details_label.setWordWrap(True)
        self.details_label.setAccessibleName(_("Technical details"))
        self.details_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.details_label)
        self._show_details(self._config.ffmpeg_path)
        layout.addStretch(1)

    def _command_row(self, title: str, command: str) -> QWidget:
        row = QWidget(self)
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        label = QLabel(title, row)
        label.setProperty("role", "kicker")
        field = QLineEdit(command, row)
        field.setReadOnly(True)
        field.setObjectName("installCommand")
        field.setAccessibleName(_("Install command for {system}").format(system=title))
        layout.addWidget(label)
        layout.addWidget(field)
        return row

    def _choose_ffmpeg(self) -> None:
        start = str(self._config.ffmpeg_path or Path.home())
        filename, _filter = QFileDialog.getOpenFileName(
            self, _("Choose the ffmpeg executable"), start
        )
        if not filename:
            return
        self._config = replace(self._config, ffmpeg_path=Path(filename))
        save_config(self._config)
        self._try_path(self._config.ffmpeg_path)

    def _retry(self) -> None:
        self._try_path(self._config.ffmpeg_path)

    def _try_path(self, path: Path | None) -> None:
        try:
            info = detect_ffmpeg(path)
        except OSError:
            info = None
        if info is None:
            self.status_label.setText(_("FFmpeg was still not found."))
            self._show_details(path)
            return
        self.ffmpeg_found.emit(info)

    def _show_details(self, path: Path | None) -> None:
        text = describe_search(path)
        self.details_label.setText(f"{_('Technical details')}:{os.linesep}{text}")
