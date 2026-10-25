# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Worker thread tests with fake processors (no FFmpeg, no visible windows)."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QEventLoop, QObject, QThread, QTimer, Slot

from reduvid.core.probe import MediaInfo
from reduvid.core.queue import ProcessingResult
from reduvid.core.runner import ProgressEvent
from reduvid.gui.workers import ProbeWorker, QueueWorker, start_worker_thread


def media(path: Path) -> MediaInfo:
    return MediaInfo(path, "matroska", 10.0, 100, [], [], [], [])


def fake_probe(_ffprobe: Path, path: Path) -> MediaInfo:
    return media(path)


class LoopQuitter(QObject):
    def __init__(self, loop: QEventLoop) -> None:
        super().__init__()
        self._loop = loop

    @Slot()
    def quit_now(self) -> None:
        self._loop.quit()

    @Slot(object)
    def quit_with_arg(self, _arg: object) -> None:
        self._loop.quit()


def run_worker(worker: ProbeWorker | QueueWorker) -> QThread:
    loop = QEventLoop()
    quitter = LoopQuitter(loop)
    if isinstance(worker, QueueWorker):
        worker.finished.connect(quitter.quit_with_arg)
    else:
        worker.finished.connect(quitter.quit_now)
    guard = QTimer()
    guard.setSingleShot(True)
    guard.timeout.connect(loop.quit)
    guard.start(5000)
    thread = start_worker_thread(worker)
    loop.exec()
    thread.quit()
    assert thread.wait(5000)
    return thread


class RecordingProcessor:
    def __init__(self) -> None:
        self.thread: QThread | None = None
        self.paused = False
        self.resumed = False
        self.cancelled = False

    def __call__(self, item: MediaInfo, on_progress) -> ProcessingResult:
        self.thread = QThread.currentThread()
        on_progress(ProgressEvent(5.0, 2.0, 2.0, "continue", total_size=50))
        return ProcessingResult(40)

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.resumed = True

    def cancel(self) -> None:
        self.cancelled = True


class BlockingProcessor:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.paused = False
        self.resumed = False
        self.cancelled = False

    def __call__(self, _item: MediaInfo, _on_progress) -> ProcessingResult:
        self.started.set()
        self.release.wait(timeout=5)
        return ProcessingResult(40)

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.resumed = True

    def cancel(self) -> None:
        self.cancelled = True
        self.release.set()


def test_probe_worker_reports_success_and_failure(tmp_path: Path, qapp) -> None:
    good = tmp_path / "good.mkv"
    bad = tmp_path / "bad.mkv"
    good.touch()
    bad.touch()

    def probe(_ffprobe: Path, path: Path) -> MediaInfo:
        if path == bad:
            raise RuntimeError("broken input")
        return media(path)

    worker = ProbeWorker([good, bad], Path("ffprobe"), probe=probe)
    probed: list[tuple[Path, MediaInfo]] = []
    failed: list[tuple[Path, str]] = []
    worker.probed.connect(lambda path, info: probed.append((path, info)))
    worker.failed.connect(lambda path, reason: failed.append((path, reason)))

    run_worker(worker)

    assert [path for path, _info in probed] == [good]
    assert failed == [(bad, "broken input")]


def test_queue_worker_emits_engine_events(tmp_path: Path, qapp) -> None:
    processor = RecordingProcessor()
    worker = QueueWorker(processor, Path("ffprobe"), probe=fake_probe)
    worker.add_files([tmp_path / "one.mkv", tmp_path / "two.mkv"])
    started: list[tuple[Path, int, int]] = []
    completed: list[Path] = []
    reports: list[object] = []
    worker.file_started.connect(lambda path, index, total: started.append((path, index, total)))
    worker.file_complete.connect(lambda report: completed.append(report.path))
    worker.finished.connect(lambda report: reports.append(report))

    run_worker(worker)

    assert [entry[1:] for entry in started] == [(1, 2), (2, 2)]
    assert completed == [tmp_path / "one.mkv", tmp_path / "two.mkv"]
    assert reports


class ThreadRecorder(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.threads: list[QThread] = []

    @Slot(object)
    def record(self, _event: object) -> None:
        self.threads.append(QThread.currentThread())


def test_queue_callbacks_run_off_the_gui_thread_and_signals_on_it(tmp_path: Path, qapp) -> None:
    processor = RecordingProcessor()
    worker = QueueWorker(processor, Path("ffprobe"), probe=fake_probe)
    worker.add_files([tmp_path / "one.mkv"])
    main_thread = QThread.currentThread()
    recorder = ThreadRecorder()
    worker.progress.connect(recorder.record)

    run_worker(worker)

    assert processor.thread is not None
    assert processor.thread is not main_thread
    assert recorder.threads
    assert all(thread is main_thread for thread in recorder.threads)


def test_queue_worker_pause_resume_and_cancel(tmp_path: Path, qapp) -> None:
    processor = BlockingProcessor()
    worker = QueueWorker(processor, Path("ffprobe"), probe=fake_probe)
    worker.add_files([tmp_path / "one.mkv"])
    loop = QEventLoop()
    worker.finished.connect(lambda *_args: loop.quit())
    QTimer.singleShot(5000, loop.quit)
    thread = start_worker_thread(worker)
    try:
        assert processor.started.wait(timeout=2)
        worker.pause()
        assert processor.paused
        assert worker.paused
        worker.resume()
        assert processor.resumed
        assert not worker.paused
        worker.cancel()
        assert processor.cancelled
        assert worker.cancelled
        loop.exec()
    finally:
        thread.quit()
        thread.wait(5000)
    assert not thread.isRunning()


def test_worker_thread_quits_cleanly(tmp_path: Path, qapp) -> None:
    worker = QueueWorker(RecordingProcessor(), Path("ffprobe"), probe=fake_probe)
    worker.add_files([tmp_path / "one.mkv"])

    thread = run_worker(worker)

    assert not thread.isRunning()
    QCoreApplication.processEvents()
