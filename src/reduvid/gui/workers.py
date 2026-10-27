# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Background workers that run engine work outside the GUI thread."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.pipeline import PipelineError
from reduvid.core.plan import PlanOptions, build_plan
from reduvid.core.probe import MediaInfo, probe_media
from reduvid.core.queue import ConversionQueue, ProcessorProtocol, QueueProgressEvent
from reduvid.core.runner import EncodeError
from reduvid.core.sample import (
    SampleLevelsRunner,
    SampleRunner,
    TotalEstimate,
    audio_bytes_for_plan,
    estimate_total,
)
from reduvid.i18n import _


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


class SampleWorker(QObject):
    """Estimate one video's final size from a short sample, emitting only signals."""

    progress = Signal(float)
    done = Signal(object)
    failed = Signal(str, str)
    finished = Signal()

    def __init__(
        self,
        ffmpeg_info: FFmpegInfo,
        media: MediaInfo,
        options: PlanOptions,
        input_path: Path,
        *,
        threads: int | None = None,
        hw_decode: bool = False,
        runner_factory: Callable[..., SampleRunner] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._ffmpeg_info = ffmpeg_info
        self._media = media
        self._options = options
        self._input_path = input_path
        self._threads = threads
        self._hw_decode = hw_decode
        self._runner_factory = runner_factory
        self._lock = threading.Lock()
        self._runner: SampleRunner | None = None
        self._cancelled = False

    @Slot()
    def run(self) -> None:
        try:
            plan = build_plan(self._media, self._ffmpeg_info, self._options)
            if not plan.videos:
                self.failed.emit("unknown", _("This video has no video streams to estimate."))
                return
            factory = self._runner_factory or SampleRunner
            runner = factory(
                self._ffmpeg_info.ffmpeg_path,
                self._media,
                plan,
                self._input_path,
                on_progress=self.progress.emit,
                threads=self._threads,
                hw_decode=self._hw_decode,
            )
            with self._lock:
                cancelled_early = self._cancelled
                self._runner = runner
            if cancelled_early:
                runner.cancel()
            sample = runner.run()
            audio_bytes = audio_bytes_for_plan(self._media, plan)[1]
            total = estimate_total(sample, self._media, audio_bytes)
        except (EncodeError, PipelineError) as error:
            self.failed.emit(error.code, error.detail)
        except ValueError as error:
            self.failed.emit("unknown", str(error))
        else:
            self.done.emit(total)
        finally:
            with self._lock:
                self._runner = None
            self.finished.emit()

    def cancel(self) -> None:
        """Stop the running sample and prevent the rest from starting."""
        with self._lock:
            self._cancelled = True
            runner = self._runner
        if runner is not None:
            runner.cancel()


class LevelsWorker(QObject):
    """Estimate several quality levels in series, emitting only signals."""

    progress = Signal(float)
    done = Signal(object)
    failed = Signal(str, str)
    finished = Signal()

    def __init__(
        self,
        ffmpeg_info: FFmpegInfo,
        media: MediaInfo,
        options: PlanOptions,
        input_path: Path,
        *,
        qualities: tuple[str, ...] = ("high", "balanced", "max_savings"),
        threads: int | None = None,
        hw_decode: bool = False,
        runner_factory: Callable[..., SampleLevelsRunner] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._ffmpeg_info = ffmpeg_info
        self._media = media
        self._options = options
        self._input_path = input_path
        self._qualities = qualities
        self._threads = threads
        self._hw_decode = hw_decode
        self._runner_factory = runner_factory
        self._lock = threading.Lock()
        self._runner: SampleLevelsRunner | None = None
        self._cancelled = False

    @Slot()
    def run(self) -> None:
        try:
            factory = self._runner_factory or SampleLevelsRunner
            runner = factory(
                self._ffmpeg_info.ffmpeg_path,
                self._media,
                self._input_path,
                self._options,
                self._ffmpeg_info,
                qualities=self._qualities,
                on_progress=self.progress.emit,
                threads=self._threads,
                hw_decode=self._hw_decode,
            )
            with self._lock:
                cancelled_early = self._cancelled
                self._runner = runner
            if cancelled_early:
                runner.cancel()
            estimates: dict[str, TotalEstimate] = runner.run()
        except (EncodeError, PipelineError) as error:
            self.failed.emit(error.code, error.detail)
        except ValueError as error:
            self.failed.emit("unknown", str(error))
        else:
            self.done.emit(estimates)
        finally:
            with self._lock:
                self._runner = None
            self.finished.emit()

    def cancel(self) -> None:
        """Stop the running level and prevent the next one from starting."""
        with self._lock:
            self._cancelled = True
            runner = self._runner
        if runner is not None:
            runner.cancel()


class _ThreadReaper(QObject):
    """Release a finished worker thread from the GUI thread.

    The thread is never scheduled with ``deleteLater``: Python owns the ``QThread``, so
    a second, queued deletion would race with the steps that still wait on it and
    crash. It is dropped here only once Qt reports that it has really finished.
    """

    @Slot()
    def reap(self) -> None:
        thread = self.sender()
        if isinstance(thread, QThread):
            thread.wait()
            _RUNNING.pop(thread, None)


_RUNNING: dict[QThread, QObject] = {}
_reaper: _ThreadReaper | None = None


def start_worker_thread(
    worker: ProbeWorker | QueueWorker | SampleWorker | LevelsWorker,
) -> QThread:
    """Move *worker* to a new thread, start it and return the thread.

    ``finished`` quits the thread. This module keeps the thread and the worker alive
    until the thread has finished, so callers may drop their own references or wait
    on the thread at any moment without it being destroyed underneath them.
    """
    global _reaper
    if _reaper is None:
        _reaper = _ThreadReaper()
    thread = QThread()
    _RUNNING[thread] = worker
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    thread.finished.connect(_reaper.reap)
    thread.start()
    return thread
