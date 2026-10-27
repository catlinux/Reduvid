# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Advanced mode: every option on a single page, sharing the wizard state."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.gui.wizard.step_destination import StepDestination
from reduvid.gui.wizard.step_keep import StepKeep
from reduvid.gui.wizard.step_summary import StepSummary
from reduvid.gui.wizard.step_videos import StepVideos
from reduvid.gui.wizard_state import WizardState
from reduvid.i18n import _

DEFAULT_MAX_HEIGHT = 1080
DEFAULT_THREADS = 4


class AdvancedPage(QWidget):
    """Flat form with all CLI options plus the shared summary and start button."""

    def __init__(
        self,
        state: WizardState,
        ffmpeg_info: FFmpegInfo,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("advancedPage")
        self._state = state
        self._ffmpeg_info = ffmpeg_info
        self._build_ui()
        state.changed.connect(self._on_state_changed)
        self.refresh()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        heading = QLabel(_("Advanced"), self)
        heading.setProperty("role", "heading")
        heading.setWordWrap(True)
        lead = QLabel(_("All options in one place. They are shared with the assistant."), self)
        lead.setProperty("role", "muted")
        lead.setWordWrap(True)
        outer.addWidget(heading)
        outer.addWidget(lead)

        scroll = QScrollArea(self)
        scroll.setObjectName("advancedScroll")
        scroll.setWidgetResizable(True)
        scroll.setAccessibleName(_("Advanced options"))
        content = QWidget(scroll)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self.videos = StepVideos(self._state, self._ffmpeg_info.ffprobe_path, parent=content)
        layout.addWidget(self.videos)

        form_group = QWidget(content)
        form = QFormLayout(form_group)
        form.setContentsMargins(0, 0, 0, 0)
        self.destination_combo = QComboBox(form_group)
        self.destination_combo.setObjectName("advancedDestination")
        self.destination_combo.setAccessibleName(_("Destination"))
        for label, value in (
            (_("Jellyfin"), "jellyfin"),
            (_("Modern devices"), "modern"),
            (_("Save for archive"), "archive"),
        ):
            self.destination_combo.addItem(label, value)
        self.quality_combo = QComboBox(form_group)
        self.quality_combo.setObjectName("advancedQuality")
        self.quality_combo.setAccessibleName(_("Quality"))
        for label, value in (
            (_("High"), "high"),
            (_("Balanced"), "balanced"),
            (_("Maximum savings"), "max_savings"),
        ):
            self.quality_combo.addItem(label, value)

        height_row = QHBoxLayout()
        self.max_height_check = QCheckBox(_("&Maximum height"), form_group)
        self.max_height_check.setObjectName("advancedMaxHeight")
        self.max_height_check.setAccessibleName(_("&Maximum height"))
        self.max_height_spin = QSpinBox(form_group)
        self.max_height_spin.setObjectName("advancedMaxHeightSpin")
        self.max_height_spin.setAccessibleName(_("Maximum height in pixels"))
        self.max_height_spin.setRange(240, 4320)
        self.max_height_spin.setSingleStep(2)
        self.max_height_spin.setValue(DEFAULT_MAX_HEIGHT)
        height_row.addWidget(self.max_height_check)
        height_row.addWidget(self.max_height_spin)
        height_row.addStretch(1)

        threads_row = QHBoxLayout()
        self.threads_check = QCheckBox(_("&Limit encoding threads"), form_group)
        self.threads_check.setObjectName("advancedThreads")
        self.threads_check.setAccessibleName(_("&Limit encoding threads"))
        self.threads_spin = QSpinBox(form_group)
        self.threads_spin.setObjectName("advancedThreadsSpin")
        self.threads_spin.setAccessibleName(_("Number of encoding threads"))
        self.threads_spin.setRange(1, 64)
        self.threads_spin.setValue(DEFAULT_THREADS)
        threads_row.addWidget(self.threads_check)
        threads_row.addWidget(self.threads_spin)
        threads_row.addStretch(1)

        form.addRow(_("Destination"), self.destination_combo)
        form.addRow(_("Quality"), self.quality_combo)
        form.addRow(height_row)
        form.addRow(threads_row)
        layout.addWidget(form_group)

        self.destination = StepDestination(self._state, content)
        layout.addWidget(self.destination)
        self.keep = StepKeep(self._state, self._ffmpeg_info, content)
        layout.addWidget(self.keep)
        self.summary = StepSummary(self._state, self._ffmpeg_info, content)
        layout.addWidget(self.summary)
        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        self.destination_combo.currentIndexChanged.connect(self._destination_changed)
        self.quality_combo.currentIndexChanged.connect(self._quality_changed)
        self.max_height_check.toggled.connect(self._height_toggled)
        self.max_height_spin.valueChanged.connect(self._height_value_changed)
        self.threads_check.toggled.connect(self._threads_toggled)
        self.threads_spin.valueChanged.connect(self._threads_value_changed)
        QWidget.setTabOrder(self.destination_combo, self.quality_combo)
        QWidget.setTabOrder(self.quality_combo, self.max_height_check)
        QWidget.setTabOrder(self.max_height_check, self.max_height_spin)
        QWidget.setTabOrder(self.max_height_spin, self.threads_check)
        QWidget.setTabOrder(self.threads_check, self.threads_spin)

    def refresh(self) -> None:
        self.refresh_controls()
        self.summary.refresh(prompt_blocking=False)

    def refresh_controls(self) -> None:
        widgets = (
            self.destination_combo,
            self.quality_combo,
            self.max_height_check,
            self.max_height_spin,
            self.threads_check,
            self.threads_spin,
        )
        for widget in widgets:
            widget.blockSignals(True)
        self.destination_combo.setCurrentIndex(
            max(0, self.destination_combo.findData(self._state.destination))
        )
        self.quality_combo.setCurrentIndex(max(0, self.quality_combo.findData(self._state.quality)))
        max_height = self._state.max_height
        self.max_height_check.setChecked(max_height is not None)
        self.max_height_spin.setValue(max_height or DEFAULT_MAX_HEIGHT)
        self.max_height_spin.setEnabled(max_height is not None)
        threads = self._state.threads
        self.threads_check.setChecked(threads is not None)
        self.threads_spin.setValue(threads or DEFAULT_THREADS)
        self.threads_spin.setEnabled(threads is not None)
        for widget in widgets:
            widget.blockSignals(False)

    def _on_state_changed(self) -> None:
        self.refresh_controls()
        self.summary.refresh(prompt_blocking=False)

    def _destination_changed(self) -> None:
        destination = self.destination_combo.currentData()
        if destination is not None:
            self._state.set_destination(str(destination))

    def _quality_changed(self) -> None:
        quality = self.quality_combo.currentData()
        if quality is not None:
            self._state.set_quality(str(quality))

    def _height_toggled(self, checked: bool) -> None:
        self.max_height_spin.setEnabled(checked)
        self._state.set_max_height(self.max_height_spin.value() if checked else None)

    def _height_value_changed(self, value: int) -> None:
        if self.max_height_check.isChecked():
            self._state.set_max_height(value)

    def _threads_toggled(self, checked: bool) -> None:
        self.threads_spin.setEnabled(checked)
        self._state.set_threads(self.threads_spin.value() if checked else None)

    def _threads_value_changed(self, value: int) -> None:
        if self.threads_check.isChecked():
            self._state.set_threads(value)
