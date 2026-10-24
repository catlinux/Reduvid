# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Preferences dialog: theme, colour mode, language, motion and FFmpeg path."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from reduvid.core.config import Config, save_config
from reduvid.core.ffmpeg import detect_ffmpeg
from reduvid.gui.theme.manager import ThemeManager
from reduvid.i18n import _

THEMES = (("Plegat", "plegat"), ("Riso", "riso"), ("Cinta", "cinta"))


def _languages() -> tuple[tuple[str, str], ...]:
    return (
        ("", _("System language")),
        ("ca", "Català"),
        ("es", "Castellano"),
        ("en", "English"),
    )


class PreferencesDialog(QDialog):
    """Edit the user configuration without touching the rest of its fields."""

    def __init__(
        self, config: Config, theme_manager: ThemeManager, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("preferencesDialog")
        self.setWindowTitle(_("Preferences"))
        self._config = config
        self._theme_manager = theme_manager
        self.config = config
        self._build_ui()
        self._load(config)

    def _build_ui(self) -> None:
        self.theme_combo = QComboBox(self)
        self.theme_combo.setObjectName("themeCombo")
        self.theme_combo.setAccessibleName(_("Theme"))
        for label, value in THEMES:
            self.theme_combo.addItem(label, value)

        self.mode_combo = QComboBox(self)
        self.mode_combo.setObjectName("colorModeCombo")
        self.mode_combo.setAccessibleName(_("Colour mode"))
        for label, value in (
            (_("System"), "system"),
            (_("Light"), "light"),
            (_("Dark"), "dark"),
        ):
            self.mode_combo.addItem(label, value)

        self.language_combo = QComboBox(self)
        self.language_combo.setObjectName("languageCombo")
        self.language_combo.setAccessibleName(_("Language"))
        for value, label in _languages():
            self.language_combo.addItem(label, value)

        language_hint = QLabel(_("Language changes take effect when Reduvid is restarted."), self)
        language_hint.setProperty("role", "muted")
        language_hint.setWordWrap(True)

        self.reduce_motion = QCheckBox(_("Reduce animations"), self)
        self.reduce_motion.setObjectName("reduceMotionCheck")
        self.reduce_motion.setAccessibleName(_("Reduce animations"))

        self.ffmpeg_edit = QLineEdit(self)
        self.ffmpeg_edit.setObjectName("ffmpegPathEdit")
        self.ffmpeg_edit.setAccessibleName(_("FFmpeg path"))
        self.browse_button = QPushButton(_("Browse…"), self)
        self.browse_button.setObjectName("browseFfmpegButton")
        self.browse_button.setAccessibleName(_("Browse for ffmpeg"))
        self.browse_button.clicked.connect(self._browse_ffmpeg)
        self.check_button = QPushButton(_("Check"), self)
        self.check_button.setObjectName("checkFfmpegButton")
        self.check_button.setAccessibleName(_("Check FFmpeg"))
        self.check_button.clicked.connect(self._check_ffmpeg)

        path_row = QHBoxLayout()
        path_row.addWidget(self.ffmpeg_edit, 1)
        path_row.addWidget(self.browse_button)
        path_row.addWidget(self.check_button)

        self.ffmpeg_status = QLabel(self)
        self.ffmpeg_status.setObjectName("ffmpegStatus")
        self.ffmpeg_status.setProperty("role", "muted")
        self.ffmpeg_status.setWordWrap(True)

        form = QFormLayout()
        form.addRow(_("Theme"), self.theme_combo)
        form.addRow(_("Colour mode"), self.mode_combo)
        form.addRow(_("Language"), self.language_combo)
        form.addRow("", language_hint)
        form.addRow("", self.reduce_motion)
        form.addRow(_("FFmpeg path"), path_row)
        form.addRow("", self.ffmpeg_status)
        self.form = form

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(_("Accept"))
        buttons.button(QDialogButtonBox.StandardButton.Ok).setAccessibleName(_("Accept"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(_("Cancel"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setAccessibleName(_("Cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.buttons = buttons

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _load(self, config: Config) -> None:
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(config.theme)))
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(config.color_mode)))
        self.language_combo.setCurrentIndex(
            max(0, self.language_combo.findData(config.language or ""))
        )
        self.reduce_motion.setChecked(config.reduce_motion)
        self.ffmpeg_edit.setText(str(config.ffmpeg_path) if config.ffmpeg_path else "")

    def _ffmpeg_path(self) -> Path | None:
        text = self.ffmpeg_edit.text().strip()
        return Path(text).expanduser() if text else None

    def _browse_ffmpeg(self) -> None:
        start = self.ffmpeg_edit.text().strip() or str(Path.home())
        filename, _filter = QFileDialog.getOpenFileName(
            self, _("Choose the ffmpeg executable"), start
        )
        if filename:
            self.ffmpeg_edit.setText(filename)

    def _check_ffmpeg(self) -> None:
        try:
            info = detect_ffmpeg(self._ffmpeg_path())
        except OSError as error:
            self.ffmpeg_status.setText(_("Could not inspect FFmpeg: {error}").format(error=error))
            return
        if info is None:
            self.ffmpeg_status.setText(_("FFmpeg was not found at that path."))
        else:
            self.ffmpeg_status.setText(_("FFmpeg {version} detected.").format(version=info.version))

    def accept(self) -> None:
        """Save the configuration and apply the theme immediately."""
        config = replace(
            self._config,
            theme=self.theme_combo.currentData(),
            color_mode=self.mode_combo.currentData(),
            language=self.language_combo.currentData() or None,
            reduce_motion=self.reduce_motion.isChecked(),
            ffmpeg_path=self._ffmpeg_path(),
        )
        save_config(config)
        self._theme_manager.apply(config.theme, config.color_mode)
        self._config = config
        self.config = config
        super().accept()
