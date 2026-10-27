# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Worker thread tests with fake processors (no FFmpeg, no visible windows)."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QEventLoop, QObject, QThread, QTimer, Slot

from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.pipeline import PipelineError
from reduvid.core.plan import PlanOptions
from reduvid.core.probe import AudioStream, MediaInfo, VideoStream
from reduvid.core.queue import ProcessingResult
from reduvid.core.runner import ProgressEvent
from reduvid.core.sample import SampleEstimate, TotalEstimate
from reduvid.gui.workers import (
    LevelsWorker,
    ProbeWorker,
    QueueWorker,
    SampleWorker,
    start_worker_thread,
)


def media(path: Path) -> MediaInfo:
    return MediaInfo(path, "matroska", 10.0, 100, [], [], [], [])


def sample_media(path: Path) -> MediaInfo:
    return MediaInfo(
        path,
        "matroska",
        10.0,
        100_000,
        [VideoStream(0, "h264", 1920, 1080, 24)],
        [AudioStream(1, "aac", 2, "eng", True, bitrate=8000)],
        [],
        [],
    )


def ffmpeg_info() -> FFmpegInfo:
    return FFmpegInfo(Path("ffmpeg"), Path("ffprobe"), "test", frozenset(), frozenset(), ())


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


def run_worker(worker: ProbeWorker | QueueWorker | SampleWorker | LevelsWorker) -> QThread:
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


class FakeSampleRunner:
    def __init__(
        self,
        _ffmpeg,
        _media,
        _plan,
        _input,
        *,
        on_progress=None,
        threads=None,
        hw_decode=False,
    ):
        self.on_progress = on_progress
        self.threads = threads
        self.hw_decode = hw_decode
        self.cancelled = False

    def run(self) -> SampleEstimate:
        if self.on_progress is not None:
            self.on_progress(0.5)
        return SampleEstimate(500, 10.0, 5.0)

    def cancel(self) -> None:
        self.cancelled = True


def test_sample_worker_reports_progress_and_the_estimate(tmp_path: Path, qapp) -> None:
    path = (tmp_path / "movie.mkv").resolve()
    worker = SampleWorker(
        ffmpeg_info(),
        sample_media(path),
        PlanOptions(),
        path,
        runner_factory=FakeSampleRunner,
    )
    progress: list[float] = []
    estimates: list[object] = []
    worker.progress.connect(progress.append)
    worker.done.connect(estimates.append)

    run_worker(worker)

    assert progress == [0.5]
    assert len(estimates) == 1
    assert estimates[0].video_bytes == 500
    assert estimates[0].audio_bytes == 10_000
    assert estimates[0].total_bytes == 10_500
    assert estimates[0].encode_seconds == 5.0


class CancelledSampleRunner:
    def __init__(
        self,
        _ffmpeg,
        _media,
        _plan,
        _input,
        *,
        on_progress=None,
        threads=None,
        hw_decode=False,
    ):
        self.hw_decode = hw_decode
        self.started = threading.Event()
        self.release = threading.Event()
        self.cancelled = False

    def run(self) -> SampleEstimate:
        self.started.set()
        self.release.wait(timeout=5)
        if self.cancelled:
            raise PipelineError("cancelled", "Sampling was cancelled.")
        return SampleEstimate(500, 10.0, 5.0)

    def cancel(self) -> None:
        self.cancelled = True
        self.release.set()


def test_sample_worker_cancel_stops_the_runner(tmp_path: Path, qapp) -> None:
    path = (tmp_path / "movie.mkv").resolve()
    runners: list[CancelledSampleRunner] = []

    class Runner(CancelledSampleRunner):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            runners.append(self)

    worker = SampleWorker(
        ffmpeg_info(),
        sample_media(path),
        PlanOptions(),
        path,
        runner_factory=Runner,
    )
    failures: list[tuple[str, str]] = []
    worker.failed.connect(lambda code, detail: failures.append((code, detail)))
    loop = QEventLoop()
    worker.finished.connect(loop.quit)
    QTimer.singleShot(5000, loop.quit)
    thread = start_worker_thread(worker)
    try:
        deadline = time.monotonic() + 2
        while not runners and time.monotonic() < deadline:
            QCoreApplication.processEvents()
            time.sleep(0.01)
        assert runners
        assert runners[0].started.wait(timeout=2)
        worker.cancel()
        loop.exec()
    finally:
        thread.quit()
        thread.wait(5000)

    assert failures == [("cancelled", "Sampling was cancelled.")]
    assert not thread.isRunning()


class FakeLevelsRunner:
    def __init__(
        self,
        _ffmpeg,
        _media,
        _input,
        _options,
        _info,
        *,
        qualities=("high", "balanced", "max_savings"),
        on_progress=None,
        threads=None,
        hw_decode=False,
    ):
        self.qualities = qualities
        self.on_progress = on_progress
        self.threads = threads
        self.hw_decode = hw_decode
        self.cancelled = False

    def run(self) -> dict[str, TotalEstimate]:
        if self.on_progress is not None:
            self.on_progress(0.5)
        return {
            quality: TotalEstimate(500, 10_000, 0, 10_500, 1.0, 5.0) for quality in self.qualities
        }

    def cancel(self) -> None:
        self.cancelled = True


def test_levels_worker_reports_progress_and_every_estimate(tmp_path: Path, qapp) -> None:
    path = (tmp_path / "movie.mkv").resolve()
    worker = LevelsWorker(
        ffmpeg_info(),
        sample_media(path),
        PlanOptions(),
        path,
        runner_factory=FakeLevelsRunner,
    )
    progress: list[float] = []
    estimates: list[object] = []
    worker.progress.connect(progress.append)
    worker.done.connect(estimates.append)

    run_worker(worker)

    assert progress == [0.5]
    assert len(estimates) == 1
    assert set(estimates[0]) == {"high", "balanced", "max_savings"}
    assert estimates[0]["balanced"].total_bytes == 10_500


class FailingLevelsRunner(FakeLevelsRunner):
    def run(self) -> dict[str, TotalEstimate]:
        raise PipelineError("verification_failed", "The sample could not be measured.")


def test_levels_worker_reports_pipeline_errors(tmp_path: Path, qapp) -> None:
    path = (tmp_path / "movie.mkv").resolve()
    worker = LevelsWorker(
        ffmpeg_info(),
        sample_media(path),
        PlanOptions(),
        path,
        runner_factory=FailingLevelsRunner,
    )
    failures: list[tuple[str, str]] = []
    worker.failed.connect(lambda code, detail: failures.append((code, detail)))

    run_worker(worker)

    assert failures == [("verification_failed", "The sample could not be measured.")]


class CancelledLevelsRunner(FakeLevelsRunner):
    def run(self) -> dict[str, TotalEstimate]:
        if self.cancelled:
            raise PipelineError("cancelled", "Sampling was cancelled.")
        return super().run()


def test_levels_worker_cancel_before_start_stops_the_runner(tmp_path: Path, qapp) -> None:
    path = (tmp_path / "movie.mkv").resolve()
    runners: list[CancelledLevelsRunner] = []

    class Runner(CancelledLevelsRunner):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            runners.append(self)

    worker = LevelsWorker(
        ffmpeg_info(),
        sample_media(path),
        PlanOptions(),
        path,
        runner_factory=Runner,
    )
    failures: list[tuple[str, str]] = []
    worker.failed.connect(lambda code, detail: failures.append((code, detail)))
    worker.cancel()

    run_worker(worker)

    assert runners
    assert runners[0].cancelled
    assert failures == [("cancelled", "Sampling was cancelled.")]


class _InstantRunner:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def run(self) -> dict[str, TotalEstimate]:
        return {}

    def cancel(self) -> None:
        pass


def test_waiting_on_a_finished_worker_thread_from_its_slot_is_safe(tmp_path: Path, qapp) -> None:
    # Owners quit and wait on the thread from the worker's finished slot. A queued
    # deleteLater of the same QThread used to hang or crash that call.
    path = (tmp_path / "movie.mkv").resolve()
    remaining = 200
    kept: list[QThread | None] = [None]

    class Owner(QObject):
        @Slot()
        def finished(self) -> None:
            nonlocal remaining
            thread = kept[0]
            if thread is not None:
                thread.quit()
                thread.wait(5000)
            kept[0] = None
            remaining -= 1
            if remaining:
                QTimer.singleShot(0, begin)

    owner = Owner()

    def begin() -> None:
        worker = LevelsWorker(
            ffmpeg_info(), sample_media(path), PlanOptions(), path, runner_factory=_InstantRunner
        )
        worker.finished.connect(owner.finished)
        kept[0] = start_worker_thread(worker)

    begin()
    deadline = time.monotonic() + 30
    while remaining and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.001)

    assert remaining == 0
