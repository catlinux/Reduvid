# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from __future__ import annotations

import io
import subprocess
import sys
import threading
from pathlib import Path
from typing import ClassVar

import pytest

from reduvid import cli
from reduvid.core.config import Config
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.pipeline import PipelineError
from reduvid.core.probe import AudioStream, MediaInfo, VideoStream
from reduvid.core.runner import EncodeError
from reduvid.core.sample import SampleEstimate


@pytest.fixture(autouse=True)
def english_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the CLI in English regardless of the machine's locale."""
    monkeypatch.setattr(cli, "load_config", lambda: (Config(language="en"), ()))


def ffmpeg_info() -> FFmpegInfo:
    return FFmpegInfo(
        Path("ffmpeg"), Path("ffprobe"), "test", frozenset({"libx264"}), frozenset(), ()
    )


def media_info(
    path: Path,
    *,
    duration: float = 600.0,
    size: int = 1_000_000_000,
    audio_bitrate: int | None = 640_000,
    audio_codec: str = "eac3",
) -> MediaInfo:
    return MediaInfo(
        path,
        "matroska",
        duration,
        size,
        [VideoStream(0, "hevc", 1920, 1080, 24.0)],
        [AudioStream(1, audio_codec, 6, "eng", True, bitrate=audio_bitrate)],
        [],
        [],
    )


def mock_ffmpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "_configured_ffmpeg_path", lambda _config: None)
    monkeypatch.setattr(cli, "detect_ffmpeg", lambda _path=None: ffmpeg_info())


class FakeSampleRunner:
    """Return a fixed sample without starting FFmpeg."""

    instances: ClassVar[list[FakeSampleRunner]] = []

    def __init__(
        self,
        _ffmpeg_path,
        _media,
        _plan,
        _input_path,
        on_progress=None,
        threads: int | None = None,
        hw_decode: bool = False,
    ) -> None:
        self.on_progress = on_progress
        self.threads = threads
        self.hw_decode = hw_decode
        self.cancelled = False
        FakeSampleRunner.instances.append(self)

    def run(self) -> SampleEstimate:
        if self.on_progress is not None:
            self.on_progress(1.0)
        return SampleEstimate(video_bytes=2_000_000, sampled_seconds=60.0, elapsed_seconds=30.0)

    def cancel(self) -> None:
        self.cancelled = True


@pytest.fixture(autouse=True)
def reset_fake_runners() -> None:
    FakeSampleRunner.instances.clear()


def test_estimate_reports_size_savings_and_time(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = Path(__file__).resolve()
    mock_ffmpeg(monkeypatch)
    monkeypatch.setattr(cli, "probe_media", lambda _ffprobe, path: media_info(path))
    monkeypatch.setattr(cli, "SampleRunner", FakeSampleRunner)

    result = cli.main(["estimate", str(source), "--threads", "3"])

    captured = capsys.readouterr()
    assert result == 0
    assert "Estimating [1/1]" in captured.out
    assert "Estimate from a 60-second sample" in captured.out
    assert "Video: ~20 MB" in captured.out
    assert "Audio: ~29 MB" in captured.out
    assert "Estimated size: ~49 MB" in captured.out
    assert "Original size: 1.0 GB" in captured.out
    assert "Savings: 95% (951 MB smaller)" in captured.out
    assert "Approximate conversion time: 5:00" in captured.out
    assert FakeSampleRunner.instances[0].threads == 3


def test_estimate_without_an_audio_bitrate_shows_video_only(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = Path(__file__).resolve()
    mock_ffmpeg(monkeypatch)
    monkeypatch.setattr(
        cli,
        "probe_media",
        lambda _ffprobe, path: media_info(path, audio_bitrate=None, audio_codec="aac"),
    )
    monkeypatch.setattr(cli, "SampleRunner", FakeSampleRunner)

    result = cli.main(["estimate", str(source)])

    captured = capsys.readouterr()
    assert result == 0
    assert "Audio: unknown" in captured.out
    assert "Estimated size: cannot be calculated" in captured.out
    assert "video only: ~20 MB" in captured.out
    assert "Savings:" not in captured.out
    assert "Approximate conversion time: 5:00" in captured.out


def test_estimate_processes_several_files(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    first = Path(__file__).resolve()
    second = Path(__file__).with_name("conftest.py")
    mock_ffmpeg(monkeypatch)
    monkeypatch.setattr(cli, "probe_media", lambda _ffprobe, path: media_info(path))
    monkeypatch.setattr(cli, "SampleRunner", FakeSampleRunner)

    result = cli.main(["estimate", str(first), str(second)])

    captured = capsys.readouterr()
    assert result == 0
    assert "Estimating [1/2]" in captured.out
    assert "Estimating [2/2]" in captured.out
    assert captured.out.count("Estimated size: ~49 MB") == 2


def test_estimate_rejects_a_folder(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    def fail_if_called(_path=None):
        raise AssertionError("FFmpeg detection should not run for a rejected folder")

    monkeypatch.setattr(cli, "detect_ffmpeg", fail_if_called)

    result = cli.main(["estimate", str(tmp_path)])

    captured = capsys.readouterr()
    assert result == 2
    assert "Input is a folder" in captured.err
    assert "files only" in captured.err


class BlockingSampleRunner:
    """Wait for cancellation, like a real sample would after Ctrl+C."""

    def __init__(self, _ffmpeg_path, _media, _plan, _input_path, **_kwargs) -> None:
        self.released = threading.Event()
        self.cancelled = False

    def run(self) -> SampleEstimate:
        self.released.wait(timeout=5)
        raise PipelineError("cancelled", "Sampling was cancelled.")

    def cancel(self) -> None:
        self.cancelled = True
        self.released.set()


def test_ctrl_c_cancels_the_sample(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = Path(__file__).resolve()
    mock_ffmpeg(monkeypatch)
    monkeypatch.setattr(cli, "probe_media", lambda _ffprobe, path: media_info(path))
    runners: list[BlockingSampleRunner] = []

    def factory(*args, **kwargs) -> BlockingSampleRunner:
        runner = BlockingSampleRunner(*args, **kwargs)
        runners.append(runner)
        return runner

    def interrupt(_done: threading.Event) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "SampleRunner", factory)
    monkeypatch.setattr(cli, "_wait_for_sample", interrupt)

    result = cli.main(["estimate", str(source)])

    captured = capsys.readouterr()
    assert result == 130
    assert "Estimate cancelled" in captured.err
    assert runners[0].cancelled


class FailingSampleRunner(FakeSampleRunner):
    def run(self) -> SampleEstimate:
        raise EncodeError("corrupt_input", "FFmpeg could not read the sample")


def test_estimate_reports_an_ffmpeg_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = Path(__file__).resolve()
    mock_ffmpeg(monkeypatch)
    monkeypatch.setattr(cli, "probe_media", lambda _ffprobe, path: media_info(path))
    monkeypatch.setattr(cli, "SampleRunner", FailingSampleRunner)

    result = cli.main(["estimate", str(source)])

    captured = capsys.readouterr()
    assert result == 2
    assert "Could not estimate" in captured.err
    assert "damaged" in captured.err


class TtyStream(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_progress_rewrites_one_line_on_a_terminal() -> None:
    stream = TtyStream()
    progress = cli._TextProgress(stream)

    progress(0.0)
    progress(0.5)
    progress(0.5)
    progress(1.0)
    progress.finish()

    text = stream.getvalue()
    assert text.count("\r") == 3
    assert "Estimating: 50%" in text
    assert text.endswith("\n")


def test_progress_writes_nothing_when_stdout_is_not_a_terminal() -> None:
    stream = io.StringIO()
    progress = cli._TextProgress(stream)

    progress(0.5)
    progress.finish()

    assert stream.getvalue() == ""


def test_importing_the_cli_does_not_load_pyside6() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, reduvid.cli; print('PySide6' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert completed.stdout.strip() == "False"


def _integration_destination(ffmpeg_info: FFmpegInfo) -> str:
    if ffmpeg_info.has_libx264:
        return "cinecat"
    if ffmpeg_info.has_libx265:
        return "modern"
    pytest.skip("FFmpeg H.264/H.265 encoder not available")


@pytest.fixture
def short_video(ffmpeg_info: FFmpegInfo, tmp_path: Path) -> Path:
    output_path = tmp_path / "short-source.mkv"
    subprocess.run(
        [
            str(ffmpeg_info.ffmpeg_path),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=duration=6:size=320x180:rate=25",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=6",
            "-c:v",
            "ffv1",
            "-level",
            "3",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return output_path.resolve()


@pytest.mark.ffmpeg
def test_estimate_on_a_short_generated_video(
    ffmpeg_info: FFmpegInfo,
    short_video: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = cli.main(
        [
            "estimate",
            str(short_video),
            "--target",
            _integration_destination(ffmpeg_info),
            "--threads",
            "2",
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "Estimate from a" in captured.out
    assert "Video: ~" in captured.out
    assert "Estimated size:" in captured.out
    assert "Approximate conversion time:" in captured.out
