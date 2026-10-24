# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from __future__ import annotations

import threading
from pathlib import Path
from typing import ClassVar

import pytest

from reduvid.core import pipeline
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.pipeline import FileProcessor, PipelineError
from reduvid.core.plan import PlanOptions
from reduvid.core.probe import MediaInfo, VideoStream
from reduvid.core.runner import EncodeResult
from reduvid.core.verify import VerificationResult


def ffmpeg_info() -> FFmpegInfo:
    return FFmpegInfo(
        Path("ffmpeg"),
        Path("ffprobe"),
        "test",
        frozenset({"libx264", "libx265"}),
        frozenset(),
        (),
    )


def media_info(path: Path, *, size: int = 1000) -> MediaInfo:
    return MediaInfo(
        path,
        "matroska",
        10.0,
        size,
        [VideoStream(0, "hevc", 1280, 720, 24.0)],
        [],
        [],
        [],
    )


def make_processor(tmp_path: Path) -> FileProcessor:
    return FileProcessor(ffmpeg_info(), PlanOptions(), output_dir=tmp_path / "output", threads=2)


def patch_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path]:
    output = tmp_path / "output" / "clip_reduvid.mkv"
    temporary = tmp_path / "output" / ".clip.reduvid-tmp.mkv"
    monkeypatch.setattr(pipeline, "build_output_path", lambda *_args: output)
    monkeypatch.setattr(pipeline, "build_temp_path", lambda _path: temporary)
    return output, temporary


class FakeHandle:
    instances: ClassVar[list[FakeHandle]] = []
    auto_finish: ClassVar[bool] = False
    created = threading.Event()

    def __init__(self, _command, _duration, temp_path: Path, **kwargs: object) -> None:
        self.temp_path = temp_path
        self.cancelled = False
        self.paused = False
        self.resumed = False
        self.release = threading.Event()
        self.started = threading.Event()
        if type(self).auto_finish:
            self.release.set()
        self.instances.append(self)
        self.created.set()

    def run(self) -> EncodeResult:
        self.started.set()
        self.release.wait(timeout=5)
        return EncodeResult(0, self.cancelled, None)

    def cancel(self) -> None:
        self.cancelled = True
        self.release.set()

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.resumed = True


def use_fake_handle(monkeypatch: pytest.MonkeyPatch, *, auto_finish: bool) -> None:
    FakeHandle.instances = []
    FakeHandle.auto_finish = auto_finish
    FakeHandle.created = threading.Event()
    monkeypatch.setattr(pipeline, "EncodeHandle", FakeHandle)


def allow_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pipeline, "verify_output", lambda *_args: VerificationResult(True, "ok", 10.0, 4)
    )


def test_success_returns_size_and_records_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output, _temporary = patch_paths(monkeypatch, tmp_path)
    use_fake_handle(monkeypatch, auto_finish=True)
    allow_verification(monkeypatch)

    def finalize(_temporary: Path, destination: Path) -> None:
        destination.write_bytes(b"data")

    monkeypatch.setattr(pipeline, "finalize_output", finalize)
    processor = make_processor(tmp_path)

    result = processor(media_info(tmp_path / "clip.mkv"), lambda _event: None)

    assert result.final_size == 4
    assert processor.last_output_path == output


def test_cancel_reaches_the_running_handle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    patch_paths(monkeypatch, tmp_path)
    use_fake_handle(monkeypatch, auto_finish=False)
    processor = make_processor(tmp_path)
    errors: list[BaseException] = []

    def run() -> None:
        try:
            processor(media_info(tmp_path / "clip.mkv"), lambda _event: None)
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(target=run)
    thread.start()
    assert FakeHandle.created.wait(timeout=5)
    assert FakeHandle.instances[0].started.wait(timeout=5)
    processor.pause()
    processor.resume()
    processor.cancel()
    thread.join(timeout=5)

    assert not thread.is_alive()
    handle = FakeHandle.instances[0]
    assert handle.cancelled
    assert handle.paused
    assert handle.resumed
    assert len(errors) == 1
    error = errors[0]
    assert isinstance(error, PipelineError)
    assert error.code == "cancelled"


def test_cancel_before_start_prevents_encoding(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    patch_paths(monkeypatch, tmp_path)
    use_fake_handle(monkeypatch, auto_finish=True)
    processor = make_processor(tmp_path)
    processor.cancel()

    with pytest.raises(PipelineError) as raised:
        processor(media_info(tmp_path / "clip.mkv"), lambda _event: None)

    assert raised.value.code == "cancelled"
    assert FakeHandle.instances == []


def test_cancel_between_files_prevents_the_next_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    patch_paths(monkeypatch, tmp_path)
    use_fake_handle(monkeypatch, auto_finish=True)
    allow_verification(monkeypatch)
    monkeypatch.setattr(
        pipeline,
        "finalize_output",
        lambda _temporary, destination: destination.write_bytes(b"data"),
    )
    processor = make_processor(tmp_path)

    processor(media_info(tmp_path / "first.mkv"), lambda _event: None)
    processor.cancel()

    with pytest.raises(PipelineError) as raised:
        processor(media_info(tmp_path / "second.mkv"), lambda _event: None)

    assert raised.value.code == "cancelled"
    assert len(FakeHandle.instances) == 1


def test_verification_failure_reports_reason_and_removes_temp(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _output, temporary = patch_paths(monkeypatch, tmp_path)
    use_fake_handle(monkeypatch, auto_finish=True)
    monkeypatch.setattr(
        pipeline,
        "verify_output",
        lambda *_args: VerificationResult(False, "duration_mismatch"),
    )
    processor = make_processor(tmp_path)

    with pytest.raises(PipelineError) as raised:
        processor(media_info(tmp_path / "clip.mkv"), lambda _event: None)

    assert raised.value.code == "verification_failed"
    assert raised.value.detail == "duration_mismatch"
    assert "Output verification failed: duration_mismatch." in str(raised.value)
    assert not temporary.exists()
