# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Background workers that run engine work outside the GUI thread."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from reduvid.core.probe import MediaInfo, probe_media
from reduvid.core.queue import ConversionQueue, ProcessorProtocol, QueueProgressEvent


class ProbeWorker(QObject):
    """Probe a list of paths and report each result as a signal."""

    probed = Signal(object, object)
    failed = Signal(object, str)
    finished = Signal()

    def __init__(
        self,
        paths: Sequence[Path],
        ffprobe_path: Path,
        *,
        probe: Callable[[Path, Path], MediaInfo] = probe_media,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._paths = list(paths)
        self._ffprobe_path = ffprobe_path
        self._probe = probe

    @Slot()
    def run(self) -> None:
        for path in self._paths:
            try:
                media = self._probe(self._ffprobe_path, path)
            except Exception as error:
                self.failed.emit(path, str(error))
            else:
                self.probed.emit(path, media)
        self.finished.emit()


class QueueWorker(QObject):
    """Run a conversion queue in a worker thread, emitting only signals."""

    file_started = Signal(object, int, int)
    progress = Signal(object)
    file_complete = Signal(object)
    file_failed = Signal(object)
    warnings = Signal(object, object)
    finished = Signal(object)

    def __init__(
        self,
        processor: ProcessorProtocol,
        ffprobe_path: Path,
        *,
        probe: Callable[[Path, Path], MediaInfo] = probe_media,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._queue = ConversionQueue(
            processor,
            ffprobe_path=ffprobe_path,
            on_progress=self._emit_progress,
            on_file_start=self.file_started.emit,
            on_file_complete=self.file_complete.emit,
            on_file_failed=self.file_failed.emit,
            on_warnings=self.warnings.emit,
            probe=probe,
        )
        self._paused = False
        self._cancelled = False

    @property
    def queue(self) -> ConversionQueue:
        return self._queue

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def add_files(self, paths: Iterable[Path]) -> None:
        self._queue.add_files(paths)

    def add_folder(self, folder: Path, *, recursive: bool = False) -> None:
        self._queue.add_folder(folder, recursive=recursive)

    def pause(self) -> None:
        self._paused = True
        self._queue.pause()

    def resume(self) -> None:
        self._paused = False
        self._queue.resume()

    def cancel(self) -> None:
        self._cancelled = True
        self._queue.cancel()

    @Slot()
    def run(self) -> None:
        report = self._queue.run()
        self.finished.emit(report)

    def _emit_progress(self, event: QueueProgressEvent) -> None:
        self.progress.emit(event)


def start_worker_thread(worker: ProbeWorker | QueueWorker) -> QThread:
    """Move *worker* to a new thread, start it and return the thread.

    ``finished`` quits the thread; both objects are scheduled for deletion once
    the thread stops.
    """
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread
