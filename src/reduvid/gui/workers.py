# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Background workers that run engine work outside the GUI thread."""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.plan import EncodePlan
from reduvid.core.probe import MediaInfo, probe_media
from reduvid.core.queue import ConversionQueue, ProcessorProtocol, QueueProgressEvent
from reduvid.core.runner import EncodeHandle
from reduvid.core.sample import build_sample_command, extract_frame_command


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


@dataclass(frozen=True)
class SampleResult:
    """Outcome of encoding and extracting a short sample."""

    encoded_sample_bytes: int
    sample_duration_seconds: float
    total_duration_seconds: float
    original_total_bytes: int
    encode_seconds: float
    original_frame_path: Path
    encoded_frame_path: Path


class SampleWorker(QObject):
    """Encode a short sample and extract before/after frames in a worker thread."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        media: MediaInfo,
        plan: EncodePlan,
        ffmpeg_info: FFmpegInfo,
        input_path: Path,
        start_seconds: float,
        duration_seconds: float,
        work_dir: Path,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._media = media
        self._plan = plan
        self._ffmpeg_info = ffmpeg_info
        self._input_path = input_path
        self._start_seconds = start_seconds
        self._duration_seconds = duration_seconds
        self._work_dir = work_dir
        self._sample_path = work_dir / f"sample.{plan.container}"
        self._original_frame_path = work_dir / "before.png"
        self._encoded_frame_path = work_dir / "after.png"

    @Slot()
    def run(self) -> None:
        result: SampleResult | None = None
        try:
            result = self._process()
        except Exception as error:
            self._remove_outputs()
            self.failed.emit(str(error))
        finally:
            self.finished.emit(result)

    def _process(self) -> SampleResult:
        self._work_dir.mkdir(parents=True, exist_ok=True)
        self._remove_outputs()
        command = build_sample_command(
            self._media,
            self._plan,
            self._input_path,
            self._sample_path,
            self._start_seconds,
            self._duration_seconds,
        )
        started = time.monotonic()
        encode_result = EncodeHandle(
            command,
            self._duration_seconds,
            self._sample_path,
            ffmpeg_path=self._ffmpeg_info.ffmpeg_path,
        ).run()
        elapsed = time.monotonic() - started
        if encode_result.cancelled:
            raise RuntimeError("sample encoding was cancelled")
        encoded_bytes = self._sample_path.stat().st_size

        self._extract_frame(
            self._input_path,
            self._start_seconds + self._duration_seconds / 2,
            self._original_frame_path,
        )
        self._extract_frame(
            self._sample_path,
            self._duration_seconds / 2,
            self._encoded_frame_path,
        )
        return SampleResult(
            encoded_sample_bytes=encoded_bytes,
            sample_duration_seconds=self._duration_seconds,
            total_duration_seconds=self._media.duration,
            original_total_bytes=self._media.size,
            encode_seconds=elapsed,
            original_frame_path=self._original_frame_path,
            encoded_frame_path=self._encoded_frame_path,
        )

    def _extract_frame(self, source: Path, timestamp: float, output: Path) -> None:
        command = extract_frame_command(source, timestamp, output)
        completed = subprocess.run(  # noqa: S603
            [str(self._ffmpeg_info.ffmpeg_path), *command],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip()[-500:]
            raise RuntimeError(detail or "could not extract a sample frame")

    def _remove_outputs(self) -> None:
        for path in (
            self._sample_path,
            self._original_frame_path,
            self._encoded_frame_path,
        ):
            path.unlink(missing_ok=True)


def start_worker_thread(worker: ProbeWorker | QueueWorker | SampleWorker) -> QThread:
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
