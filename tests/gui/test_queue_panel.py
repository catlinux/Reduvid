# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Queue panel and error view tests with a fake worker."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, Signal

from reduvid.core.plan import Warning
from reduvid.core.queue import QueueProgressEvent
from reduvid.core.report import build_file_report, build_queue_report
from reduvid.core.runner import ProgressEvent
from reduvid.gui.error_view import ErrorView
from reduvid.gui.queue_panel import QueuePanel


class FakeWorker(QObject):
    file_started = Signal(object, int, int)
    progress = Signal(object)
    file_complete = Signal(object)
    file_failed = Signal(object)
    warnings = Signal(object, object)
    finished = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.paused = False
        self.resumed = False
        self.cancelled = False

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.resumed = True

    def cancel(self) -> None:
        self.cancelled = True


def progress_event(
    path: Path,
    *,
    fraction: float = 0.38,
    remaining: float | None = 240.0,
    size: int = 123_000_000,
) -> QueueProgressEvent:
    return QueueProgressEvent(
        path,
        1,
        2,
        fraction,
        ProgressEvent(30.0, 1.5, remaining, "continue", total_size=size),
    )


def test_progress_reaches_the_panel(qapp) -> None:
    panel = QueuePanel()
    worker = FakeWorker()
    panel.connect_worker(worker)  # type: ignore[arg-type]
    path = Path("pelicula.mkv")

    worker.file_started.emit(path, 1, 2)
    worker.progress.emit(progress_event(path))

    assert panel.state == "converting"
    assert panel.current_name.text() == "pelicula.mkv"
    assert panel.progress_bar.value() == 38
    assert "38" in panel.percent_label.text()
    assert "4 min" in panel.eta_label.text()
    assert "123 MB" in panel.size_label.text()


def test_pause_and_resume_update_the_panel(qapp) -> None:
    panel = QueuePanel()
    worker = FakeWorker()
    panel.connect_worker(worker)  # type: ignore[arg-type]
    worker.file_started.emit(Path("a.mkv"), 1, 1)

    panel.pause_button.click()
    assert worker.paused
    assert panel.state == "paused"
    assert panel.pause_button.text() == "&Resume"
    assert "Paused" in panel.status_label.text()

    panel.pause_button.click()
    assert worker.resumed
    assert panel.state == "converting"
    assert panel.pause_button.text() == "&Pause"
    assert panel.status_label.text() == ""


def test_cancel_finishes_with_the_cancelled_message(qapp) -> None:
    panel = QueuePanel()
    worker = FakeWorker()
    panel.connect_worker(worker)  # type: ignore[arg-type]
    worker.file_started.emit(Path("a.mkv"), 1, 1)

    panel.cancel_button.click()
    assert worker.cancelled
    assert panel.state == "cancelling"
    assert "Cancelling" in panel.status_label.text()

    worker.finished.emit(build_queue_report([]))

    assert panel.state == "finished"
    assert "Cancelled" in panel.status_label.text()
    assert not panel.cancel_button.isEnabled()


def test_warnings_and_total_are_shown_per_video(qapp) -> None:
    panel = QueuePanel()
    worker = FakeWorker()
    panel.connect_worker(worker)  # type: ignore[arg-type]
    path = Path("a.mkv")
    report = build_file_report(path, "success", 400_000_000, 160_000_000)

    worker.file_started.emit(path, 1, 1)
    worker.warnings.emit(path, (Warning("audio_recoded", {"stream_index": 1, "codec": "aac"}),))
    worker.file_complete.emit(report)

    assert panel.warning_texts
    assert "Audio track 1" in panel.warning_texts[0]
    assert "Total:" in panel.total_label.text()
    assert "estimated" in panel.total_label.text()


def test_finished_reports_savings(qapp) -> None:
    panel = QueuePanel()
    worker = FakeWorker()
    panel.connect_worker(worker)  # type: ignore[arg-type]
    path = Path("a.mkv")
    report = build_file_report(path, "success", 1000, 600)
    worker.file_started.emit(path, 1, 1)
    worker.file_complete.emit(report)

    worker.finished.emit(build_queue_report([report]))

    assert "Ready and verified" in panel.status_label.text()
    assert "40%" in panel.status_label.text()
    assert "Total:" in panel.total_label.text()


def test_failed_report_uses_the_translated_error(qapp) -> None:
    from reduvid.messages import error_text

    panel = QueuePanel()
    worker = FakeWorker()
    panel.connect_worker(worker)  # type: ignore[arg-type]
    path = Path("a.mkv")
    report = build_file_report(
        path, "failed", 1000, reason="ffmpeg exploded", error_code="no_space"
    )

    worker.file_started.emit(path, 1, 1)
    worker.file_failed.emit(report)

    assert panel.status_label.text() == error_text("no_space")


def test_error_view_shows_translation_and_technical_details(qapp) -> None:
    from reduvid.messages import error_text

    view = ErrorView()
    view.set_error("verification_failed", "duration mismatch")

    assert view.message_label.text() == error_text("verification_failed")
    assert view.details.isHidden()

    view.details_button.setChecked(True)

    assert not view.details.isHidden()
    assert view.details.toPlainText() == "duration mismatch"
    assert "Hide" in view.details_button.text()
    assert view.details.isReadOnly()


def test_error_view_hides_details_without_reason(qapp) -> None:
    view = ErrorView()
    view.set_error("unknown", None)

    assert view.details.isHidden()
    assert view.details_button.isHidden()
