# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Step 6: per-video compatibility summary and conversion start."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.plan import PlanOptions
from reduvid.core.probe import MediaInfo, format_size
from reduvid.core.report import QueueReport
from reduvid.core.sample import TotalEstimate
from reduvid.gui.error_view import ErrorView
from reduvid.gui.wizard_logic import (
    VideoSummary,
    format_duration,
    summarize,
)
from reduvid.gui.wizard_state import WizardState
from reduvid.gui.workers import SampleWorker, start_worker_thread
from reduvid.i18n import _
from reduvid.messages import error_text, warning_text

EstimateKey = tuple[PlanOptions, int]


def _estimate_text(total: TotalEstimate, media: MediaInfo) -> str:
    """Describe an estimate as such, without implying a measured final size."""
    time = format_duration(total.encode_seconds)
    if total.total_bytes is None:
        return _(
            "Estimated size: cannot be calculated without the audio size; "
            "video only: ~{size} · Approx. time: {time}"
        ).format(size=format_size(total.video_bytes), time=time)
    size = format_size(total.total_bytes)
    original = format_size(media.size)
    if media.size > 0 and total.total_bytes > media.size:
        return _(
            "Estimated size: ~{size} (bigger than the original {original}) · Approx. time: {time}"
        ).format(size=size, original=original, time=time)
    ratio = total.ratio_vs_original
    if ratio is None:
        return _("Estimated size: ~{size} · Approx. time: {time}").format(size=size, time=time)
    return _(
        "Estimated size: ~{size} (from {original}: −{percent:.0f} %) · Approx. time: {time}"  # noqa: RUF001
    ).format(size=size, original=original, percent=(1 - ratio) * 100, time=time)


def _level_text(level: str) -> str:
    if level == "direct":
        return _("Plays directly in Cinecat")
    if level == "partial":
        return _("Cinecat will convert it while playing")
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
        *,
        scrollable: bool = True,
    ) -> None:
        super().__init__(parent)
        # Advanced already scrolls the whole page; a second scroll would squeeze the rows.
        self._scrollable = scrollable
        self._state = state
        self._ffmpeg_info = ffmpeg_info
        self.blocking_prompt = BlockingPrompt(self)
        self.summaries: list[VideoSummary] = []
        self.status_labels: dict[Path, QLabel] = {}
        self.skipped: set[Path] = set()
        self.error_views: list[ErrorView] = []
        self.estimate_buttons: dict[Path, QPushButton] = {}
        self.estimate_progress_bars: dict[Path, QProgressBar] = {}
        self.estimate_cancel_buttons: dict[Path, QPushButton] = {}
        self.estimate_results: dict[Path, QLabel] = {}
        self._decisions: dict[Path, bool] = {}
        self._running = False
        self._results: dict[Path, tuple[EstimateKey, TotalEstimate]] = {}
        self._estimate_errors: dict[Path, str] = {}
        self._estimating_path: Path | None = None
        self._estimating_key: EstimateKey | None = None
        self._estimate_worker: SampleWorker | None = None
        self._estimate_thread: QThread | None = None
        self._estimate_progress = 0.0
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
        if self._scrollable:
            scroll = QScrollArea(self)
            scroll.setObjectName("summaryScroll")
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setAccessibleName(_("Summary"))
            scroll.setWidget(self.items_container)
            layout.addWidget(scroll, 1)
        else:
            layout.addWidget(self.items_container, 1)

        self.start_button = QPushButton(_("&Start"), self)
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
        keys = {summary.path: (options, summary.media.size) for summary in self.summaries}
        if (
            self._estimating_path is not None
            and keys.get(self._estimating_path) != self._estimating_key
        ):
            self.cancel_estimate()
        for path in list(self._results):
            if keys.get(path) != self._results[path][0]:
                del self._results[path]
        for path in list(self._estimate_errors):
            if path not in keys:
                del self._estimate_errors[path]
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

    @property
    def estimating_path(self) -> Path | None:
        """The video being estimated right now, if any."""
        return self._estimating_path

    def remaining_paths(self) -> list[Path]:
        return [summary.path for summary in self.summaries if summary.path not in self.skipped]

    def set_running(self, running: bool) -> None:
        self._running = running
        self.start_button.setText(_("Converting…") if running else _("&Start"))
        self._apply_estimate_widgets()
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
        self.estimate_buttons.clear()
        self.estimate_progress_bars.clear()
        self.estimate_cancel_buttons.clear()
        self.estimate_results.clear()
        for summary in self.summaries:
            self.items_layout.addWidget(self._build_row(summary))
        self.items_layout.addStretch(1)
        self._apply_estimate_widgets()

    def _build_row(self, summary: VideoSummary) -> QWidget:
        row = QWidget(self.items_container)
        row.setObjectName("summaryRow")
        column = QVBoxLayout(row)
        column.setContentsMargins(0, 0, 0, 0)
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

        self._build_estimate_row(summary, column, row)

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

    def _build_estimate_row(self, summary: VideoSummary, column: QVBoxLayout, row: QWidget) -> None:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        button = QPushButton(_("Estimate the final size (1-minute test)"), row)
        button.setObjectName("estimateButton")
        button.setAccessibleName(_("Estimate the final size from a 1-minute test of this video"))
        button.clicked.connect(lambda _checked=False, path=summary.path: self._start_estimate(path))
        self.estimate_buttons[summary.path] = button
        layout.addWidget(button)

        bar = QProgressBar(row)
        bar.setObjectName("estimateProgress")
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setMinimumWidth(120)
        bar.setAccessibleName(_("Estimate progress"))
        bar.hide()
        self.estimate_progress_bars[summary.path] = bar
        layout.addWidget(bar, 1)

        cancel = QPushButton(_("Cancel"), row)
        cancel.setObjectName("estimateCancel")
        cancel.setAccessibleName(_("Cancel the estimate"))
        cancel.clicked.connect(
            lambda _checked=False, path=summary.path: self._cancel_estimate_clicked(path)
        )
        cancel.hide()
        self.estimate_cancel_buttons[summary.path] = cancel
        layout.addWidget(cancel)
        layout.addStretch(1)

        result = QLabel(row)
        result.setObjectName("estimateResult")
        result.setWordWrap(True)
        result.setAccessibleName(_("Estimated size and time"))
        result.setToolTip(
            _(
                "A 1-minute test of this video, scaled to the whole file. "
                "The real size and time may differ."
            )
        )
        result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        result.hide()
        self.estimate_results[summary.path] = result
        column.addLayout(layout)
        column.addWidget(result)

    def _summary_for(self, path: Path) -> VideoSummary | None:
        return next((summary for summary in self.summaries if summary.path == path), None)

    def _start_estimate(self, path: Path) -> None:
        summary = self._summary_for(path)
        if summary is None or self._estimating_path is not None or self._running:
            return
        options = self._state.options()
        worker = SampleWorker(
            self._ffmpeg_info,
            summary.media,
            options,
            summary.path,
            threads=self._state.threads,
            hw_decode=self._state.hw_decode,
        )
        worker.progress.connect(self._on_estimate_progress)
        worker.done.connect(self._on_estimate_done)
        worker.failed.connect(self._on_estimate_failed)
        worker.finished.connect(self._on_estimate_finished)
        self._estimate_errors.pop(path, None)
        self._estimating_path = path
        self._estimating_key = (options, summary.media.size)
        self._estimate_worker = worker
        self._estimate_progress = 0.0
        self._apply_estimate_widgets()
        self._update_start_button()
        self._estimate_thread = start_worker_thread(worker)

    def _cancel_estimate_clicked(self, path: Path) -> None:
        if path == self._estimating_path:
            self.cancel_estimate()

    def cancel_estimate(self, *, wait: bool = True) -> None:
        """Stop a running estimate and return the rows to their initial state."""
        worker = self._estimate_worker
        thread = self._estimate_thread
        self._estimate_worker = None
        self._estimating_path = None
        self._estimating_key = None
        self._estimate_progress = 0.0
        if worker is not None:
            worker.cancel()
        if thread is not None:
            thread.quit()
            if wait:
                thread.wait(5000)
        if wait:
            self._estimate_thread = None
        self._apply_estimate_widgets()
        self._update_start_button()

    @Slot(float)
    def _on_estimate_progress(self, value: float) -> None:
        self._estimate_progress = min(max(value, 0.0), 1.0)
        path = self._estimating_path
        bar = self.estimate_progress_bars.get(path) if path is not None else None
        if bar is not None:
            bar.setValue(int(self._estimate_progress * 100))

    @Slot(object)
    def _on_estimate_done(self, estimate: object) -> None:
        path = self._estimating_path
        if path is None or self._estimating_key is None or not isinstance(estimate, TotalEstimate):
            return
        self._results[path] = (self._estimating_key, estimate)
        self._estimate_errors.pop(path, None)
        self._apply_estimate_widgets()

    @Slot(str, str)
    def _on_estimate_failed(self, code: str, _detail: str) -> None:
        path = self._estimating_path
        if path is None or code == "cancelled":
            return
        self._estimate_errors[path] = _("Could not estimate the size: {message}").format(
            message=error_text(code)
        )
        self._apply_estimate_widgets()

    @Slot()
    def _on_estimate_finished(self) -> None:
        thread = self._estimate_thread
        self._estimate_worker = None
        self._estimating_path = None
        self._estimating_key = None
        self._estimate_progress = 0.0
        if thread is not None:
            thread.quit()
            thread.wait(5000)
        self._estimate_thread = None
        self._apply_estimate_widgets()
        self._update_start_button()

    def _result_text(self, path: Path) -> str:
        error = self._estimate_errors.get(path)
        if error is not None:
            return error
        entry = self._results.get(path)
        summary = self._summary_for(path)
        if entry is None or summary is None:
            return ""
        return _estimate_text(entry[1], summary.media)

    def _apply_estimate_widgets(self) -> None:
        for path, button in self.estimate_buttons.items():
            estimating = path == self._estimating_path
            button.setEnabled(self._estimating_path is None and not self._running)
            bar = self.estimate_progress_bars[path]
            bar.setVisible(estimating)
            bar.setValue(int(self._estimate_progress * 100) if estimating else 0)
            self.estimate_cancel_buttons[path].setVisible(estimating)
            result = self.estimate_results[path]
            text = self._result_text(path)
            result.setText(text)
            result.setVisible(bool(text))

    def _update_start_button(self) -> None:
        self.start_button.setEnabled(
            bool(self.remaining_paths()) and not self._running and self._estimating_path is None
        )

    def _start(self) -> None:
        if self.start_button.isEnabled():
            self.cancel_estimate()
            self.start_requested.emit()
