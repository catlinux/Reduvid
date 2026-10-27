# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Queue panel: current file progress, controls, warnings and totals."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Literal

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from reduvid.core.plan import Warning
from reduvid.core.queue import QueueProgressEvent
from reduvid.core.report import FileReport, QueueReport
from reduvid.core.runner import ProgressEvent
from reduvid.gui.widgets.progress import ThemedProgressBar
from reduvid.gui.workers import QueueWorker
from reduvid.i18n import _
from reduvid.messages import error_text, warning_text

PanelState = Literal["idle", "converting", "paused", "cancelling", "finished"]


class QueuePanel(QWidget):
    """Show and control the conversion queue without owning any engine state."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("queuePanel")
        self.setAccessibleName(_("Conversion queue"))
        self._worker: QueueWorker | None = None
        self._state: PanelState = "idle"
        self._cancel_requested = False
        self._reports: dict[Path, FileReport] = {}
        self._items: dict[Path, tuple[QWidget, QLabel, QVBoxLayout]] = {}
        self._build_ui()
        self._set_state("idle")

    @property
    def state(self) -> PanelState:
        return self._state

    @property
    def warning_texts(self) -> tuple[str, ...]:
        return tuple(label.text() for label in self.findChildren(QLabel, "warningChip"))

    def connect_worker(self, worker: QueueWorker) -> None:
        """Connect the panel to *worker*; never call engine methods directly here."""
        self.reset()
        self._worker = worker
        worker.file_started.connect(self._on_file_started)
        worker.progress.connect(self._on_progress)
        worker.file_complete.connect(self._on_file_complete)
        worker.file_failed.connect(self._on_file_failed)
        worker.warnings.connect(self._on_warnings)
        worker.finished.connect(self._on_finished)

    def reset(self) -> None:
        self._reports.clear()
        while self.items_layout.count():
            entry = self.items_layout.takeAt(0)
            if entry is None:
                continue
            widget = entry.widget()
            if widget is not None:
                widget.deleteLater()
        self._items.clear()
        self.current_name.clear()
        self.size_label.clear()
        self.percent_label.clear()
        self.eta_label.clear()
        self.status_label.clear()
        self.total_label.clear()
        self.progress_bar.setValue(0)
        self.title_label.setText(_("Queue"))
        self._cancel_requested = False
        self._set_state("idle")

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 20, 18, 20)
        layout.setSpacing(10)

        self.title_label = QLabel(_("Queue"), self)
        self.title_label.setProperty("role", "kicker")
        layout.addWidget(self.title_label)

        self.current_name = QLabel(self)
        self.current_name.setObjectName("currentName")
        self.current_name.setWordWrap(True)
        layout.addWidget(self.current_name)

        meta = QHBoxLayout()
        self.size_label = QLabel(self)
        self.size_label.setObjectName("currentSize")
        self.percent_label = QLabel(self)
        self.percent_label.setObjectName("currentPercent")
        self.eta_label = QLabel(self)
        self.eta_label.setObjectName("currentEta")
        self.eta_label.setProperty("role", "muted")
        meta.addWidget(self.size_label)
        meta.addStretch(1)
        meta.addWidget(self.percent_label)
        meta.addWidget(self.eta_label)
        layout.addLayout(meta)

        self.progress_bar = ThemedProgressBar(self)
        self.progress_bar.setObjectName("queueProgress")
        self.progress_bar.setAccessibleName(_("Conversion progress"))
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        controls = QHBoxLayout()
        self.pause_button = QPushButton(_("&Pause"), self)
        self.pause_button.setObjectName("pauseButton")
        self.pause_button.setAccessibleName(_("Pause conversion"))
        self.pause_button.clicked.connect(self._toggle_pause)
        self.cancel_button = QPushButton(_("&Cancel"), self)
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.setAccessibleName(_("Cancel conversion"))
        self.cancel_button.clicked.connect(self._cancel)
        controls.addWidget(self.pause_button)
        controls.addWidget(self.cancel_button)
        controls.addStretch(1)
        layout.addLayout(controls)
        QWidget.setTabOrder(self.pause_button, self.cancel_button)

        self.status_label = QLabel(self)
        self.status_label.setObjectName("statusMessage")
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.items_container = QWidget(self)
        self.items_container.setObjectName("queueItems")
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(8)
        layout.addWidget(self.items_container)

        self.total_label = QLabel(self)
        self.total_label.setObjectName("queueTotal")
        self.total_label.setProperty("role", "muted")
        self.total_label.setWordWrap(True)
        layout.addWidget(self.total_label)
        layout.addStretch(1)

    def _set_state(self, state: PanelState) -> None:
        self._state = state
        self.pause_button.setEnabled(state in ("converting", "paused"))
        self.cancel_button.setEnabled(state in ("converting", "paused"))

    def _toggle_pause(self) -> None:
        if self._state == "paused":
            if self._worker is not None:
                self._worker.resume()
            self.pause_button.setText(_("&Pause"))
            self.status_label.clear()
            self._set_state("converting")
        elif self._state == "converting":
            if self._worker is not None:
                self._worker.pause()
            self.pause_button.setText(_("&Resume"))
            self.status_label.setText(_("Paused. You can keep using the computer as usual."))
            self._set_state("paused")

    def _cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
        self._cancel_requested = True
        self.status_label.setText(_("Cancelling…"))
        self._set_state("cancelling")

    def _on_file_started(self, path: Path, index: int, total: int) -> None:
        self.title_label.setText(_("Queue · {count} videos").format(count=total))
        self.current_name.setText(path.name)
        self.size_label.clear()
        self.percent_label.setText(_("{percent}%").format(percent=0))
        self.eta_label.clear()
        self.progress_bar.setValue(0)
        self.status_label.clear()
        self._ensure_item(path)
        self._set_state("converting")

    def _on_progress(self, event: QueueProgressEvent) -> None:
        fraction = min(max(event.fraction_completed, 0.0), 1.0)
        percent = round(fraction * 100)
        self.current_name.setText(event.file_path.name)
        self.percent_label.setText(_("{percent}%").format(percent=percent))
        self.progress_bar.setValue(percent)
        progress = event.file_progress
        self.eta_label.setText(self._eta_text(progress, fraction))
        if progress is not None and progress.total_size is not None:
            self.size_label.setText(_format_size(progress.total_size))

    def _eta_text(self, progress: ProgressEvent | None, fraction: float) -> str:
        if fraction >= 1.0:
            return _("verified")
        if progress is None or progress.tiempo_restante_segundos is None:
            return ""
        seconds = max(0.0, progress.tiempo_restante_segundos)
        if seconds < 60:
            return _("less than 1 min left")
        return _("{minutes} min left").format(minutes=math.ceil(seconds / 60))

    def _on_file_complete(self, report: FileReport) -> None:
        self._reports[report.path] = report
        self._update_item(report)
        self._update_total()
        if self._state == "converting":
            self.progress_bar.setValue(100)
            self.percent_label.setText(_("{percent}%").format(percent=100))
            self.eta_label.setText(_("verified"))

    def _on_file_failed(self, report: FileReport) -> None:
        self._reports[report.path] = report
        self._update_item(report)
        self._update_total()
        self.status_label.setText(error_text(report.error_code or "unknown"))

    def _on_warnings(self, path: Path, warnings: tuple[Warning, ...]) -> None:
        self._ensure_item(path)
        for warning in warnings:
            chip = QLabel(warning_text(warning), self.items_container)
            chip.setObjectName("warningChip")
            chip.setWordWrap(True)
            self._items[path][2].addWidget(chip)

    def _on_finished(self, report: QueueReport) -> None:
        self._set_state("finished")
        self.pause_button.setText(_("&Pause"))
        self.total_label.setText(
            _("Total: {original} → {final}").format(
                original=_format_size(report.original_size),
                final=_format_size(report.final_size),
            )
        )
        if self._cancel_requested:
            self.status_label.setText(_("Cancelled. No files are left half-written."))
        elif report.failed:
            self.status_label.setText(
                _("Finished with {count} failed file(s).").format(count=report.failed)
            )
        else:
            self.status_label.setText(
                _("Ready and verified: {percent}% smaller. The originals are untouched.").format(
                    percent=round(report.savings_percent)
                )
            )
        self._worker = None

    def _ensure_item(self, path: Path) -> None:
        if path in self._items:
            return
        container = QWidget(self.items_container)
        container.setObjectName("queueItem")
        container.setAccessibleName(path.name)
        column = QVBoxLayout(container)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(2)
        name = QLabel(path.name, container)
        name.setWordWrap(True)
        chips = QWidget(container)
        chips_layout = QVBoxLayout(chips)
        chips_layout.setContentsMargins(0, 0, 0, 0)
        chips_layout.setSpacing(2)
        column.addWidget(name)
        column.addWidget(chips)
        self.items_layout.addWidget(container)
        self._items[path] = (container, name, chips_layout)

    def _update_item(self, report: FileReport) -> None:
        self._ensure_item(report.path)
        name = self._items[report.path][1]
        size = report.final_size if report.final_size is not None else report.original_size
        name.setText(_("{name} · {size}").format(name=report.path.name, size=_format_size(size)))

    def _update_total(self) -> None:
        if not self._reports:
            self.total_label.clear()
            return
        original = sum(report.original_size for report in self._reports.values())
        estimated = sum(
            report.final_size if report.final_size is not None else report.original_size
            for report in self._reports.values()
        )
        self.total_label.setText(
            _("Total: {original} → {estimated} estimated").format(
                original=_format_size(original), estimated=_format_size(estimated)
            )
        )


def _format_size(size: int) -> str:
    if size >= 1_000_000_000:
        return f"{size / 1_000_000_000:.1f} GB"
    return f"{size / 1_000_000:.0f} MB"
