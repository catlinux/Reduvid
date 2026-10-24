# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from pathlib import Path
from types import SimpleNamespace

import pytest

from reduvid import cli
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.probe import MediaInfo, VideoStream
from reduvid.core.runner import EncodeResult
from reduvid.core.verify import VerificationResult


def ffmpeg_info() -> FFmpegInfo:
    return FFmpegInfo(
        Path("ffmpeg"), Path("ffprobe"), "test", frozenset({"libx264"}), frozenset(), ()
    )


def media_info(path: Path, *, size: int = 20) -> MediaInfo:
    return MediaInfo(
        path,
        "matroska",
        125.5,
        size,
        [VideoStream(0, "hevc", 1280, 720, 24.0)],
        [],
        [],
        [],
    )


def mock_ffmpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "_configured_ffmpeg_path", lambda: None)
    monkeypatch.setattr(cli, "detect_ffmpeg", lambda _path=None: ffmpeg_info())


def test_probe_reports_missing_ffmpeg(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    source = Path(__file__).resolve()
    monkeypatch.setattr(cli, "_configured_ffmpeg_path", lambda: None)
    monkeypatch.setattr(cli, "detect_ffmpeg", lambda _path=None: None)

    result = cli.main(["probe", str(source)])

    captured = capsys.readouterr()
    assert result == 1
    assert "FFmpeg and ffprobe were not found" in captured.err


def test_probe_prints_media_summary(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    source = Path(__file__).resolve()
    mock_ffmpeg(monkeypatch)
    monkeypatch.setattr(cli, "probe_media", lambda _ffprobe, path: media_info(path))

    result = cli.main(["probe", str(source)])

    captured = capsys.readouterr()
    assert result == 0
    assert "1280x720" in captured.out
    assert "hevc" in captured.out
    assert "Duration: 2:05" in captured.out


def test_probe_continues_after_a_file_error(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    source = Path(__file__).resolve()
    mock_ffmpeg(monkeypatch)
    attempts = 0

    def probe(_ffprobe: Path, path: Path) -> MediaInfo:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise cli.ProbeError("invalid media")
        return media_info(path)

    monkeypatch.setattr(cli, "probe_media", probe)

    result = cli.main(["probe", str(source), str(source)])

    captured = capsys.readouterr()
    assert result == 2
    assert "invalid media" in captured.err
    assert "test_cli.py" in captured.out


def test_convert_dry_run_does_not_start_encoder(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    source = Path(__file__).resolve()
    mock_ffmpeg(monkeypatch)
    monkeypatch.setattr(cli, "probe_media", lambda _ffprobe, path: media_info(path))

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("dry-run started an encoder")

    monkeypatch.setattr(cli, "EncodeHandle", fail_if_called)
    monkeypatch.setattr("reduvid.core.runner.subprocess.Popen", fail_if_called)

    result = cli.main(
        [
            "convert",
            str(source),
            "--dry-run",
            "--max-height",
            "720",
            "--target",
            "modern",
            "--quality",
            "high",
            "--container",
            "mp4",
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "Would convert" in captured.out
    assert "Plan: modern, high, mp4" in captured.out
    assert "Video stream 0" in captured.out
    assert "--max-height is not supported yet" in captured.out


def test_convert_runs_pipeline_and_reports_success(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    source = Path(__file__).resolve()
    output = source.with_name("_reduvid_cli_output_not_created.mkv")
    temporary = source.with_name("_reduvid_cli_temp_not_created.mkv")
    mock_ffmpeg(monkeypatch)
    monkeypatch.setattr(cli, "probe_media", lambda _ffprobe, path: media_info(path, size=20))
    trash_calls: list[str] = []
    monkeypatch.setattr(cli.send2trash, "send2trash", trash_calls.append)
    monkeypatch.setattr(cli, "build_output_path", lambda *_args: output)
    monkeypatch.setattr(cli, "build_temp_path", lambda _path: temporary)
    monkeypatch.setattr(cli, "finalize_output", lambda _temp, _output: None)
    original_stat = Path.stat

    def fake_stat(path: Path, *args, **kwargs):
        if path == output:
            return SimpleNamespace(st_size=7)
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", fake_stat)

    class FakeEncodeHandle:
        def __init__(self, _command, _duration, _temp_path, **_kwargs) -> None:
            pass

        def run(self) -> EncodeResult:
            return EncodeResult(0, False, None)

    monkeypatch.setattr(cli, "EncodeHandle", FakeEncodeHandle)
    monkeypatch.setattr(
        cli,
        "verify_output",
        lambda *_args: VerificationResult(True, "ok", 125.5, 7),
    )

    result = cli.main(["convert", str(source), "--replace-original"])

    captured = capsys.readouterr()
    assert result == 0
    assert "1 succeeded, 0 failed, 0 skipped" in captured.out
    assert "Total savings" in captured.out
    assert trash_calls == [str(source.resolve())]
    assert source.exists()
    assert str(output) in captured.out


def test_replace_original_keeps_source_if_verification_fails(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    source = Path(__file__).resolve()
    output = source.with_name("_reduvid_cli_failed_output_not_created.mkv")
    temporary = source.with_name("_reduvid_cli_failed_temp_not_created.mkv")
    mock_ffmpeg(monkeypatch)
    monkeypatch.setattr(cli, "probe_media", lambda _ffprobe, path: media_info(path, size=20))
    trash_calls: list[str] = []
    monkeypatch.setattr(cli.send2trash, "send2trash", trash_calls.append)
    monkeypatch.setattr(cli, "build_output_path", lambda *_args: output)
    monkeypatch.setattr(cli, "build_temp_path", lambda _path: temporary)

    class FakeEncodeHandle:
        def __init__(self, _command, _duration, _temp_path, **_kwargs) -> None:
            pass

        def run(self) -> EncodeResult:
            return EncodeResult(0, False, None)

    monkeypatch.setattr(cli, "EncodeHandle", FakeEncodeHandle)
    monkeypatch.setattr(
        cli,
        "verify_output",
        lambda *_args: VerificationResult(False, "duration_mismatch"),
    )

    result = cli.main(["convert", str(source), "--replace-original"])

    captured = capsys.readouterr()
    assert result == 2
    assert "Output verification failed" in captured.err
    assert trash_calls == []
    assert source.exists()
    assert not temporary.exists()


def test_missing_input_fails_before_ffmpeg_detection(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    missing = Path(__file__).with_name("_missing_cli_input_never_created.mkv")

    def fail_if_called(_path=None):
        raise AssertionError("FFmpeg detection should not run for a missing input")

    monkeypatch.setattr(cli, "detect_ffmpeg", fail_if_called)

    result = cli.main(["convert", str(missing)])

    captured = capsys.readouterr()
    assert result == 2
    assert "Input does not exist" in captured.err
