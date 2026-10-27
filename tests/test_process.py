# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path
from subprocess import CompletedProcess
from types import SimpleNamespace

import pytest

from reduvid.core import ffmpeg, hardware, probe, process, runner, thumbnail
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.probe import MediaInfo

WINDOWS_CREATIONFLAGS = 0x08000000


@pytest.fixture
def windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", WINDOWS_CREATIONFLAGS, raising=False)


def test_hidden_window_kwargs_on_windows(windows: None) -> None:
    assert process.hidden_window_kwargs() == {"creationflags": WINDOWS_CREATIONFLAGS}


def test_hidden_window_kwargs_on_other_platforms(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process, "sys", SimpleNamespace(platform="linux"))

    assert process.hidden_window_kwargs() == {}


def test_ffmpeg_uses_hidden_window_kwargs(monkeypatch: pytest.MonkeyPatch, windows: None) -> None:
    calls: list[dict[str, object]] = []

    def run(args: list[str], **kwargs: object) -> CompletedProcess[str]:
        calls.append(kwargs)
        return CompletedProcess(args, 0, stdout="ffmpeg version 9.0\n", stderr="")

    monkeypatch.setattr(ffmpeg.subprocess, "run", run)
    monkeypatch.setattr(ffmpeg, "_find_executable", lambda name, configured: Path("C:/mock") / name)

    assert ffmpeg.detect_ffmpeg() is not None
    assert len(calls) == 4
    assert all(call["creationflags"] == WINDOWS_CREATIONFLAGS for call in calls)


def test_runner_uses_hidden_window_kwargs(
    monkeypatch: pytest.MonkeyPatch, windows: None, tmp_path: Path
) -> None:
    class FakeProcess:
        stdout = io.StringIO()
        stderr = io.StringIO()
        pid = 1234

    calls: list[dict[str, object]] = []

    def popen(args: list[str], **kwargs: object) -> FakeProcess:
        calls.append(kwargs)
        return FakeProcess()

    monkeypatch.setattr(runner.subprocess, "Popen", popen)
    monkeypatch.setattr(runner.EncodeHandle, "_lower_priority", lambda self: None)

    runner.EncodeHandle([], None, tmp_path / "output.mkv")

    assert calls[0]["creationflags"] == WINDOWS_CREATIONFLAGS


def test_probe_uses_hidden_window_kwargs(monkeypatch: pytest.MonkeyPatch, windows: None) -> None:
    output = (Path(__file__).parent / "data" / "simple.json").read_text(encoding="utf-8")
    calls: list[dict[str, object]] = []

    def run(args: list[str], **kwargs: object) -> CompletedProcess[str]:
        calls.append(kwargs)
        return CompletedProcess(args, 0, stdout=output, stderr="")

    monkeypatch.setattr(probe.subprocess, "run", run)

    probe.probe_media(Path("C:/mock/ffprobe"), Path("C:/movie.mkv"))

    assert calls[0]["creationflags"] == WINDOWS_CREATIONFLAGS


def test_thumbnail_uses_hidden_window_kwargs(
    monkeypatch: pytest.MonkeyPatch, windows: None, tmp_path: Path
) -> None:
    source = tmp_path / "video.mkv"
    source.write_bytes(b"video")
    media = MediaInfo(source, "matroska", 60.0, source.stat().st_size, [], [], [], [])
    calls: list[dict[str, object]] = []

    def run(args: list[str], **kwargs: object) -> CompletedProcess[bytes]:
        calls.append(kwargs)
        return CompletedProcess(args, 0)

    monkeypatch.setattr(thumbnail.subprocess, "run", run)

    assert (
        thumbnail.extract_thumbnail(tmp_path / "ffmpeg", media, cache_dir=tmp_path / "cache")
        is None
    )
    assert calls[0]["creationflags"] == WINDOWS_CREATIONFLAGS


def test_hardware_uses_hidden_window_kwargs(
    monkeypatch: pytest.MonkeyPatch, windows: None, tmp_path: Path
) -> None:
    info = FFmpegInfo(
        tmp_path / "ffmpeg",
        tmp_path / "ffprobe",
        "9.0",
        frozenset(),
        frozenset(),
        ("h264_qsv",),
    )
    calls: list[dict[str, object]] = []

    def run(args: list[str], **kwargs: object) -> CompletedProcess[bytes]:
        calls.append(kwargs)
        return CompletedProcess(args, 0)

    monkeypatch.setattr(hardware.subprocess, "run", run)

    hardware.probe_hardware_encoders(info, cache_dir=tmp_path / "cache")

    assert calls[0]["creationflags"] == WINDOWS_CREATIONFLAGS


def test_power_throttling_is_a_no_op_outside_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process, "sys", SimpleNamespace(platform="linux"))

    assert process.disable_power_throttling(1234) is False


@pytest.mark.skipif(sys.platform != "win32", reason="real Windows API call")
def test_power_throttling_can_be_disabled_for_a_real_process() -> None:
    assert process.disable_power_throttling(os.getpid()) is True


def test_runner_disables_power_throttling_on_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    monkeypatch.setattr(runner, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(runner, "disable_power_throttling", calls.append)
    monkeypatch.setattr(
        runner.psutil, "Process", lambda pid: SimpleNamespace(nice=lambda value: None)
    )
    monkeypatch.setattr(runner.psutil, "BELOW_NORMAL_PRIORITY_CLASS", 0x4000, raising=False)
    handle = object.__new__(runner.EncodeHandle)
    handle._process = SimpleNamespace(pid=4321)  # type: ignore[assignment]

    handle._lower_priority()

    assert calls == [4321]
