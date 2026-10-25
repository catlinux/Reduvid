# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Quality-step sample: worker wiring, result panel and invalidation."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from types import SimpleNamespace

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QImage

from reduvid.core.config import Config
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.plan import PlanOptions, build_plan
from reduvid.core.probe import AudioStream, MediaInfo, VideoStream
from reduvid.core.runner import EncodeResult
from reduvid.gui import workers as workers_module
from reduvid.gui.wizard import step_quality
from reduvid.gui.wizard.step_quality import StepQuality
from reduvid.gui.wizard_state import WizardState
from reduvid.gui.workers import SampleResult, SampleWorker


def ffmpeg_info() -> FFmpegInfo:
    return FFmpegInfo(
        Path("ffmpeg"), Path("ffprobe"), "test", frozenset({"libx264"}), frozenset(), ()
    )


def media(path: Path) -> MediaInfo:
    return MediaInfo(
        path,
        "matroska",
        60.0,
        100_000_000,
        [VideoStream(0, "h264", 1920, 1080, 24)],
        [AudioStream(1, "aac", 2, "eng", True)],
        [],
        [],
    )


def state_with_video(tmp_path: Path) -> WizardState:
    path = tmp_path / "vídeo ñ.mkv"
    path.touch()
    state = WizardState(Config())
    state.add_paths([path])
    state.set_media(path, media(path))
    return state


def image_file(path: Path) -> Path:
    image = QImage(32, 18, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.red)
    image.save(str(path))
    return path


class FakeWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        pass


class FakeThread:
    pass


def page_with_fake_worker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[StepQuality, FakeWorker, list[FakeWorker]]:
    state = state_with_video(tmp_path)
    page = StepQuality(state, ffmpeg_info())
    worker = FakeWorker()
    started: list[FakeWorker] = []
    page.create_sample_worker = lambda *_args: worker  # type: ignore[method-assign]
    monkeypatch.setattr(
        step_quality,
        "start_worker_thread",
        lambda target: (started.append(target), FakeThread())[1],
    )
    return page, worker, started


def sample_result(tmp_path: Path) -> SampleResult:
    before = image_file(tmp_path / "before.png")
    after = image_file(tmp_path / "after.png")
    return SampleResult(
        encoded_sample_bytes=10_000_000,
        sample_duration_seconds=30.0,
        total_duration_seconds=60.0,
        original_total_bytes=100_000_000,
        encode_seconds=5.0,
        original_frame_path=before,
        encoded_frame_path=after,
    )


def test_sample_button_is_disabled_without_videos(qapp) -> None:
    page = StepQuality(WizardState(Config()), ffmpeg_info())

    assert not page.sample_button.isEnabled()
    assert page.sample_result.isHidden()


def test_sample_runs_and_shows_comparison(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, qapp
) -> None:
    page, worker, started = page_with_fake_worker(monkeypatch, tmp_path)
    assert page.sample_button.isEnabled()

    page.sample_button.click()

    assert started == [worker]
    assert not page.sample_button.isEnabled()
    assert page._sample_running
    assert "Encoding" in page.sample_status.text()

    worker.finished.emit(sample_result(tmp_path))
    qapp.processEvents()

    assert page.sample_button.isEnabled()
    assert not page.sample_result.isHidden()
    assert page.before_frame.pixmap() is not None
    assert not page.before_frame.pixmap().isNull()
    assert page.after_frame.pixmap() is not None
    assert not page.after_frame.pixmap().isNull()
    assert "20 MB" in page.estimate_label.text()
    assert "80%" in page.savings_label.text()
    assert page.sample_status.text() == "Sample ready."
    assert page._state.sample_result is not None


def test_changing_quality_invalidates_the_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, qapp
) -> None:
    page, worker, _started = page_with_fake_worker(monkeypatch, tmp_path)
    page.sample_button.click()
    worker.finished.emit(sample_result(tmp_path))
    qapp.processEvents()
    assert not page.sample_result.isHidden()

    page.cards["high"].click()

    assert page.sample_result.isHidden()
    assert page.estimate_label.text() == ""
    assert page._state.sample_result is None
    assert "Quality changed" in page.sample_status.text()


def test_changing_quality_while_running_discards_the_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, qapp
) -> None:
    page, worker, _started = page_with_fake_worker(monkeypatch, tmp_path)
    page.sample_button.click()
    page.cards["high"].click()

    worker.finished.emit(sample_result(tmp_path))
    qapp.processEvents()

    assert page.sample_result.isHidden()
    assert page._state.sample_result is None
    assert "Quality changed" in page.sample_status.text()
    assert page.sample_button.isEnabled()


def test_sample_worker_builds_a_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, qapp
) -> None:
    source = tmp_path / "source.mkv"
    source.touch()
    info = media(source)
    plan = build_plan(info, ffmpeg_info(), PlanOptions())

    class FakeHandle:
        def __init__(self, _command, _duration, path: Path, **_kwargs) -> None:
            self.path = path

        def run(self) -> EncodeResult:
            self.path.write_bytes(b"encoded sample")
            return EncodeResult(0, False, None)

    def fake_run(command, **_kwargs):
        Path(command[-1]).write_bytes(b"png")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(workers_module, "EncodeHandle", FakeHandle)
    monkeypatch.setattr(workers_module.subprocess, "run", fake_run)
    worker = SampleWorker(info, plan, ffmpeg_info(), source, 10.0, 30.0, tmp_path / "cache")
    finished: list[object] = []
    failed: list[str] = []
    worker.finished.connect(finished.append)
    worker.failed.connect(failed.append)

    worker.run()

    assert failed == []
    result = finished[0]
    assert isinstance(result, SampleResult)
    assert result.encoded_sample_bytes == len(b"encoded sample")
    assert result.original_frame_path.is_file()
    assert result.encoded_frame_path.is_file()
    assert result.total_duration_seconds == info.duration


def test_sample_failure_is_reported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, qapp) -> None:
    page, worker, _started = page_with_fake_worker(monkeypatch, tmp_path)
    page.sample_button.click()

    worker.failed.emit("ffmpeg exploded")
    worker.finished.emit(None)
    qapp.processEvents()

    assert "ffmpeg exploded" in page.sample_status.text()
    assert page.sample_button.isEnabled()
    assert page.sample_result.isHidden()
