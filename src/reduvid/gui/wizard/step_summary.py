# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Step 6: per-video compatibility summary and conversion start."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from reduvid.core.estimate import estimate_from_sample
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.report import QueueReport
from reduvid.gui.error_view import ErrorView
from reduvid.gui.widgets.primary_button import PrimaryButton
from reduvid.gui.wizard_logic import (
    VideoSummary,
    format_duration,
    format_size,
    summarize,
)
from reduvid.gui.wizard_state import WizardState
from reduvid.i18n import _
from reduvid.messages import warning_text


def _level_text(level: str) -> str:
    if level == "direct":
        return _("Direct play")
    if level == "partial":
        return _("Jellyfin will transcode")
    return _("Needs attention")


class BlockingPrompt:
    """Ask once per video whether to skip it or convert it anyway."""

    def __init__(self, parent: QWidget | None = None) -> None:
        self._parent = parent

    def ask(self, summary: VideoSummary) -> bool:
        box = QMessageBox(self._parent)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(_("HDR video"))
        if summary.blocking:
            box.setText(warning_text(summary.blocking[0]))
        else:
            box.setText(_("This video needs your attention."))
        box.setInformativeText(_("Convert it anyway? Colours will look washed out."))
        skip_button = box.addButton(_("Skip this video"), QMessageBox.ButtonRole.RejectRole)
        box.addButton(
            _("Convert anyway (colours will look washed out)"),
            QMessageBox.ButtonRole.DestructiveRole,
        )
        box.exec()
        clicked = box.clickedButton()
        return clicked is not None and clicked is not skip_button


class StepSummary(QWidget):
    """Show the plan and traffic light for every video, then start the queue."""

    start_requested = Signal()

    def __init__(
        self,
        state: WizardState,
        ffmpeg_info: FFmpegInfo,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._ffmpeg_info = ffmpeg_info
        self.blocking_prompt = BlockingPrompt(self)
        self.summaries: list[VideoSummary] = []
        self.status_labels: dict[Path, QLabel] = {}
        self.skipped: set[Path] = set()
        self.error_views: list[ErrorView] = []
        self._decisions: dict[Path, bool] = {}
        self._running = False
        self._build_ui()
        self.refresh(prompt_blocking=False)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        heading = QLabel(_("Summary"), self)
        heading.setProperty("role", "heading")
        heading.setWordWrap(True)
        lead = QLabel(_("Review what Reduvid will do with each video before starting."), self)
        lead.setProperty("role", "muted")
        lead.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(lead)

        self.items_container = QWidget(self)
        self.items_container.setObjectName("summaryItems")
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(8)
        layout.addWidget(self.items_container)
        layout.addStretch(1)

        self.start_button = PrimaryButton(_("&Start"), self)
        self.start_button.setObjectName("startButton")
        self.start_button.setAccessibleName(_("Start conversion"))
        self.start_button.clicked.connect(self._start)
        layout.addWidget(self.start_button)

        self.report_label = QLabel(self)
        self.report_label.setObjectName("finalReport")
        self.report_label.setWordWrap(True)
        layout.addWidget(self.report_label)
        self.report_errors = QWidget(self)
        self.report_errors_layout = QVBoxLayout(self.report_errors)
        self.report_errors_layout.setContentsMargins(0, 0, 0, 0)
        self.report_errors_layout.setSpacing(6)
        layout.addWidget(self.report_errors)

    def refresh(self, *, prompt_blocking: bool = True) -> None:
        options = self._state.options()
        self.summaries = [
            summary
            for entry in self._state.videos
            if (summary := summarize(entry, self._ffmpeg_info, options)) is not None
        ]
        blocking_paths = {summary.path for summary in self.summaries if summary.blocking}
        for path in list(self._decisions):
            if path not in blocking_paths:
                del self._decisions[path]
                self.skipped.discard(path)
        if prompt_blocking:
            self._ask_unresolved()
        self._build_rows()
        self._update_start_button()

    def resolve_blocking(self) -> None:
        """Ask about every unresolved blocking video before starting."""
        if self._ask_unresolved():
            self._build_rows()
            self._update_start_button()

    def _ask_unresolved(self) -> bool:
        changed = False
        for summary in self.summaries:
            if summary.blocking and summary.path not in self._decisions:
                keep = self.blocking_prompt.ask(summary)
                self._decisions[summary.path] = keep
                if keep:
                    self.skipped.discard(summary.path)
                else:
                    self.skipped.add(summary.path)
                changed = True
        return changed

    def remaining_paths(self) -> list[Path]:
        return [summary.path for summary in self.summaries if summary.path not in self.skipped]

    def set_running(self, running: bool) -> None:
        self._running = running
        self.start_button.setText(_("Converting…") if running else _("&Start"))
        self._update_start_button()

    def show_report(self, report: QueueReport) -> None:
        self.set_running(False)
        self.report_label.setText(
            _(
                "Total savings: {megabytes:.2f} MB ({percent:.1f}%). "
                "{succeeded} succeeded, {failed} failed, {skipped} skipped."
            ).format(
                megabytes=report.savings_bytes / 1_000_000,
                percent=report.savings_percent,
                succeeded=report.succeeded,
                failed=report.failed,
                skipped=len(self.skipped),
            )
        )
        while self.report_errors_layout.count():
            entry = self.report_errors_layout.takeAt(0)
            if entry is None:
                continue
            widget = entry.widget()
            if widget is not None:
                widget.deleteLater()
        self.error_views.clear()
        for file_report in report.files:
            if file_report.status != "failed":
                continue
            label = QLabel(str(file_report.path), self.report_errors)
            label.setWordWrap(True)
            error_view = ErrorView(self.report_errors)
            error_view.set_error(file_report.error_code or "unknown", file_report.reason)
            self.report_errors_layout.addWidget(label)
            self.report_errors_layout.addWidget(error_view)
            self.error_views.append(error_view)

    def _build_rows(self) -> None:
        while self.items_layout.count():
            entry = self.items_layout.takeAt(0)
            if entry is None:
                continue
            widget = entry.widget()
            if widget is not None:
                widget.deleteLater()
        self.status_labels.clear()
        for summary in self.summaries:
            self.items_layout.addWidget(self._build_row(summary))

    def _build_row(self, summary: VideoSummary) -> QWidget:
        row = QWidget(self.items_container)
        row.setObjectName("summaryCard")
        row.setProperty("level", summary.status.level)
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.style().unpolish(row)
        row.style().polish(row)
        column = QVBoxLayout(row)
        column.setContentsMargins(12, 10, 12, 10)
        column.setSpacing(2)

        header = QHBoxLayout()
        name = QLabel(summary.path.name, row)
        name.setWordWrap(True)
        status = QLabel(_level_text(summary.status.level), row)
        status.setObjectName("compatLight")
        status.setProperty("level", summary.status.level)
        status.setAccessibleName(_level_text(summary.status.level))
        status.style().unpolish(status)
        status.style().polish(status)
        header.addWidget(name, 1)
        header.addWidget(status)
        column.addLayout(header)

        meta = QLabel(
            f"{format_size(summary.media.size)} · {format_duration(summary.media.duration)}",
            row,
        )
        meta.setProperty("role", "muted")
        column.addWidget(meta)

        sample = self._state.sample_result
        if sample is not None:
            estimate = estimate_from_sample(
                original_sample_bytes=0,
                encoded_sample_bytes=sample.encoded_sample_bytes,
                sample_duration_seconds=sample.sample_duration_seconds,
                total_duration_seconds=summary.media.duration,
                elapsed_encode_seconds=sample.encode_seconds,
            )
            estimate_label = QLabel(
                _("Estimated: {size} · {time}").format(
                    size=format_size(estimate.estimated_total_bytes),
                    time=format_duration(estimate.estimated_total_seconds),
                ),
                row,
            )
            estimate_label.setObjectName("estimateInfo")
            estimate_label.setProperty("role", "muted")
            estimate_label.setWordWrap(True)
            column.addWidget(estimate_label)

        for warning in summary.warnings:
            label = QLabel(warning_text(warning), row)
            label.setObjectName("compatWarning")
            label.setWordWrap(True)
            column.addWidget(label)
        if summary.path in self.skipped:
            skipped = QLabel(_("Skipped"), row)
            skipped.setObjectName("skippedMark")
            column.addWidget(skipped)
        self.status_labels[summary.path] = status
        return row

    def _update_start_button(self) -> None:
        self.start_button.setEnabled(bool(self.remaining_paths()) and not self._running)

    def _start(self) -> None:
        if self.start_button.isEnabled():
            self.start_requested.emit()
