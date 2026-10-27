# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

from reduvid.core import pipeline
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.pipeline import FileProcessor
from reduvid.core.plan import PlanOptions
from reduvid.core.probe import MediaInfo, VideoStream
from reduvid.core.runner import EncodeError, EncodeResult
from reduvid.core.verify import VerificationResult

_ROOT = Path(Path.cwd().anchor)


def ffmpeg_info(*hwaccels: str) -> FFmpegInfo:
    return FFmpegInfo(
        _ROOT / "ffmpeg",
        _ROOT / "ffprobe",
        "test",
        frozenset({"libx264", "libx265"}),
        frozenset(),
        (),
        hwaccels=hwaccels,
    )


def media_info(path: Path) -> MediaInfo:
    return MediaInfo(
        path,
        "matroska",
        10.0,
        1000,
        [VideoStream(0, "hevc", 1280, 720, 24.0)],
        [],
        [],
        [],
    )


def patch_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    output = tmp_path / "output" / "clip_reduvid.mkv"
    temporary = tmp_path / "output" / ".clip.reduvid-tmp.mkv"
    monkeypatch.setattr(pipeline, "build_output_path", lambda *_args: output)
    monkeypatch.setattr(pipeline, "build_temp_path", lambda _path: temporary)
    return output


class FakeHandle:
    instances: ClassVar[list[FakeHandle]] = []
    fail_first: ClassVar[bool] = False
    always_fail: ClassVar[bool] = False
    cancel_processor: ClassVar[FileProcessor | None] = None

    def __init__(
        self,
        command: list[str],
        _duration: float,
        temp_path: Path,
        **_kwargs: object,
    ) -> None:
        self.command = command
        self.temp_path = temp_path
        self.cancelled = False
        type(self).instances.append(self)

    def run(self) -> EncodeResult:
        attempt = type(self).instances.index(self)
        processor = type(self).cancel_processor
        if processor is not None and attempt == 0:
            processor.cancel()
        if type(self).always_fail or (type(self).fail_first and attempt == 0):
            raise EncodeError("unknown", "hardware decode failed")
        self.temp_path.write_bytes(b"data")
        return EncodeResult(0, False, None)

    def cancel(self) -> None:
        self.cancelled = True

    def pause(self) -> None:
        pass

    def resume(self) -> None:
        pass


def use_fake_handle(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fail_first: bool = False,
    always_fail: bool = False,
    cancel_processor: FileProcessor | None = None,
) -> None:
    FakeHandle.instances = []
    FakeHandle.fail_first = fail_first
    FakeHandle.always_fail = always_fail
    FakeHandle.cancel_processor = cancel_processor
    monkeypatch.setattr(pipeline, "EncodeHandle", FakeHandle)


def allow_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pipeline, "verify_output", lambda *_args: VerificationResult(True, "ok", 10.0, 4)
    )


def finalize(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pipeline,
        "finalize_output",
        lambda _temporary, destination: destination.write_bytes(b"data"),
    )


def make_processor(
    tmp_path: Path, *, hwaccels: tuple[str, ...], hw_decode: bool = True
) -> FileProcessor:
    return FileProcessor(
        ffmpeg_info(*hwaccels),
        PlanOptions(),
        output_dir=tmp_path / "output",
        threads=2,
        hw_decode=hw_decode,
    )


def test_retries_once_without_hardware_decode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output = patch_paths(monkeypatch, tmp_path)
    use_fake_handle(monkeypatch, fail_first=True)
    allow_verification(monkeypatch)
    finalize(monkeypatch)
    processor = make_processor(tmp_path, hwaccels=("cuda",))

    result = processor(media_info(tmp_path / "clip.mkv"), lambda _event: None)

    assert len(FakeHandle.instances) == 2
    first_input = FakeHandle.instances[0].command.index("-i")
    assert FakeHandle.instances[0].command[first_input - 2 : first_input] == [
        "-hwaccel",
        "auto",
    ]
    assert "-hwaccel" not in FakeHandle.instances[1].command
    assert result.final_size == 4
    assert processor.last_output_path == output


def test_hardware_decode_is_skipped_without_hwaccels(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    patch_paths(monkeypatch, tmp_path)
    use_fake_handle(monkeypatch)
    allow_verification(monkeypatch)
    finalize(monkeypatch)
    processor = make_processor(tmp_path, hwaccels=())

    processor(media_info(tmp_path / "clip.mkv"), lambda _event: None)

    assert len(FakeHandle.instances) == 1
    assert "-hwaccel" not in FakeHandle.instances[0].command


def test_hardware_decode_can_be_disabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    patch_paths(monkeypatch, tmp_path)
    use_fake_handle(monkeypatch)
    allow_verification(monkeypatch)
    finalize(monkeypatch)
    processor = make_processor(tmp_path, hwaccels=("cuda",), hw_decode=False)

    processor(media_info(tmp_path / "clip.mkv"), lambda _event: None)

    assert len(FakeHandle.instances) == 1
    assert "-hwaccel" not in FakeHandle.instances[0].command


def test_cancellation_during_first_attempt_does_not_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    patch_paths(monkeypatch, tmp_path)
    processor = make_processor(tmp_path, hwaccels=("cuda",))
    use_fake_handle(monkeypatch, always_fail=True, cancel_processor=processor)

    with pytest.raises(EncodeError):
        processor(media_info(tmp_path / "clip.mkv"), lambda _event: None)

    assert len(FakeHandle.instances) == 1


def test_retry_failure_is_propagated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    patch_paths(monkeypatch, tmp_path)
    use_fake_handle(monkeypatch, always_fail=True)
    processor = make_processor(tmp_path, hwaccels=("cuda",))

    with pytest.raises(EncodeError):
        processor(media_info(tmp_path / "clip.mkv"), lambda _event: None)

    assert len(FakeHandle.instances) == 2
    assert "-hwaccel" in FakeHandle.instances[0].command
    assert "-hwaccel" not in FakeHandle.instances[1].command
