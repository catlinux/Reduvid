# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from __future__ import annotations

import io
import subprocess
from pathlib import Path

import pytest

from reduvid.core import runner


class FakeProcess:
    def __init__(
        self,
        stdout: str = "",
        stderr: str = "",
        returncode: int | None = 0,
        *,
        stays_alive_on_terminate: bool = False,
    ) -> None:
        self.stdout = io.StringIO(stdout)
        self.stderr = io.StringIO(stderr)
        self.returncode = returncode
        self.stays_alive_on_terminate = stays_alive_on_terminate
        self.pid = 1234
        self.terminate_calls = 0
        self.kill_calls = 0
        self.wait_calls: list[float | None] = []

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls.append(timeout)
        if self.returncode is None:
            if timeout is not None:
                raise subprocess.TimeoutExpired("ffmpeg", timeout)
            self.returncode = 0
        return self.returncode

    def terminate(self) -> None:
        self.terminate_calls += 1
        if not self.stays_alive_on_terminate:
            self.returncode = -15

    def kill(self) -> None:
        self.kill_calls += 1
        self.returncode = -9


class FakePsutilProcess:
    def __init__(self) -> None:
        self.nice_calls: list[int] = []
        self.suspend_calls = 0
        self.resume_calls = 0

    def nice(self, value: int) -> None:
        self.nice_calls.append(value)

    def suspend(self) -> None:
        self.suspend_calls += 1

    def resume(self) -> None:
        self.resume_calls += 1


def _install_process(
    monkeypatch: pytest.MonkeyPatch,
    process: FakeProcess,
) -> list[list[str]]:
    invocations: list[list[str]] = []

    def popen(args: list[str], **_kwargs: object) -> FakeProcess:
        invocations.append(args)
        return process

    monkeypatch.setattr(runner.subprocess, "Popen", popen)
    return invocations


def _install_psutil(monkeypatch: pytest.MonkeyPatch) -> FakePsutilProcess:
    process = FakePsutilProcess()
    monkeypatch.setattr(runner.psutil, "Process", lambda _pid: process)
    return process


def test_progress_blocks_are_parsed_and_end_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    process = FakeProcess(
        "out_time_us=2000000\nspeed=2.0x\ntotal_size=10\nbitrate=4kbits/s\n"
        "progress=continue\n"
        "out_time_us=4000000\nspeed=1.5x\nprogress=end\n"
    )
    _install_process(monkeypatch, process)
    _install_psutil(monkeypatch)
    events: list[runner.ProgressEvent] = []

    handle = runner.EncodeHandle(
        ["-i", "input.mkv", "output.mkv"],
        10.0,
        tmp_path / "temporary.mkv",
        events.append,
    )
    result = handle.run()

    assert result.returncode == 0
    assert len(events) == 2
    assert events[0].tiempo_procesado_segundos == 2.0
    assert events[0].velocidad == 2.0
    assert events[0].tiempo_restante_segundos == 4.0
    assert events[0].total_size == 10
    assert events[0].bitrate == "4kbits/s"
    assert events[-1].estado == "end"
    assert events[-1].tiempo_procesado_segundos == 4.0
    assert events[-1].tiempo_restante_segundos == 4.0


def test_successful_encode_builds_ffmpeg_arguments(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(runner.sys, "platform", "linux")
    process = FakeProcess()
    invocations = _install_process(monkeypatch, process)
    ps_process = _install_psutil(monkeypatch)
    output = tmp_path / "encoded.mkv"
    output.write_text("partial", encoding="utf-8")

    result = runner.EncodeHandle(
        ["-nostdin", "-hide_banner", "-i", "input.mkv", str(output)],
        None,
        output,
        threads=3,
        ffmpeg_path=Path("/mock/ffmpeg"),
    ).run()

    assert result == runner.EncodeResult(0, False, None)
    assert invocations[0][:6] == [
        str(Path("/mock/ffmpeg")),
        "-nostdin",
        "-hide_banner",
        "-progress",
        "pipe:1",
        "-nostats",
    ]
    assert invocations[0][-3:] == ["-threads", "3", str(output)]
    assert ps_process.nice_calls == [10]
    assert output.exists()


@pytest.mark.parametrize(
    ("stderr", "code"),
    [
        ("No space left on device", "no_space"),
        ("Permission denied", "permission_denied"),
    ],
)
def test_ffmpeg_errors_are_classified_and_remove_temporary_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    stderr: str,
    code: runner.EncodeErrorCode,
) -> None:
    process = FakeProcess(stderr=stderr, returncode=1)
    _install_process(monkeypatch, process)
    _install_psutil(monkeypatch)
    output = tmp_path / "partial.mkv"
    output.write_text("partial", encoding="utf-8")
    handle = runner.EncodeHandle([], None, output)

    with pytest.raises(runner.EncodeError) as error:
        handle.run()

    assert error.value.code == code
    assert not output.exists()


def test_cancel_terminates_then_kills_and_removes_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    process = FakeProcess(returncode=None, stays_alive_on_terminate=True)
    _install_process(monkeypatch, process)
    _install_psutil(monkeypatch)
    output = tmp_path / "partial.mkv"
    output.write_text("partial", encoding="utf-8")
    handle = runner.EncodeHandle([], None, output)

    handle.cancel()
    result = handle.run()

    assert process.terminate_calls == 1
    assert process.kill_calls == 1
    assert process.wait_calls == [5, 5, None]
    assert result == runner.EncodeResult(-9, True, None)
    assert not output.exists()


def test_pause_and_resume_use_psutil_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    process = FakeProcess(returncode=None)
    _install_process(monkeypatch, process)
    ps_process = _install_psutil(monkeypatch)
    handle = runner.EncodeHandle([], None, tmp_path / "output.mkv")

    handle.pause()
    handle.resume()

    assert ps_process.suspend_calls == 1
    assert ps_process.resume_calls == 1
