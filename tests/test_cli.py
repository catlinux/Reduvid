# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

import argparse
from pathlib import Path
from types import SimpleNamespace

import pytest

from reduvid import cli
from reduvid.core import pipeline
from reduvid.core.config import Config
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.plan import PlanOptions
from reduvid.core.probe import AudioStream, MediaInfo, VideoStream
from reduvid.core.runner import EncodeResult
from reduvid.core.verify import VerificationResult


@pytest.fixture(autouse=True)
def english_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the CLI in English regardless of the machine's locale."""
    monkeypatch.setattr(cli, "load_config", lambda: (Config(language="en"), ()))


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
    monkeypatch.setattr(cli, "_configured_ffmpeg_path", lambda _config: None)
    monkeypatch.setattr(cli, "detect_ffmpeg", lambda _path=None: ffmpeg_info())


def test_probe_reports_missing_ffmpeg(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    source = Path(__file__).resolve()
    monkeypatch.setattr(cli, "_configured_ffmpeg_path", lambda _config: None)
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

    monkeypatch.setattr(pipeline, "EncodeHandle", fail_if_called)
    monkeypatch.setattr("reduvid.core.runner.subprocess.Popen", fail_if_called)

    result = cli.main(
        [
            "convert",
            str(source),
            "--dry-run",
            "--max-height",
            "480",
            "--target",
            "jellyfin",
            "--quality",
            "high",
            "--container",
            "mp4",
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "Would convert" in captured.out
    assert "Plan: jellyfin, high, mp4" in captured.out
    assert "Video stream 0" in captured.out
    assert "scale to 480p" in captured.out
    assert "scaled down to 1080p" in captured.out


def test_convert_runs_pipeline_and_reports_success(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    source = Path(__file__).resolve()
    output = source.with_name("_reduvid_cli_output_not_created.mkv")
    temporary = source.with_name("_reduvid_cli_temp_not_created.mkv")
    mock_ffmpeg(monkeypatch)
    monkeypatch.setattr(cli, "probe_media", lambda _ffprobe, path: media_info(path, size=20))
    trash_calls: list[str] = []
    monkeypatch.setattr(pipeline.send2trash, "send2trash", trash_calls.append)
    monkeypatch.setattr(pipeline, "build_output_path", lambda *_args: output)
    monkeypatch.setattr(pipeline, "build_temp_path", lambda _path: temporary)
    monkeypatch.setattr(pipeline, "finalize_output", lambda _temp, _output: None)
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

    monkeypatch.setattr(pipeline, "EncodeHandle", FakeEncodeHandle)
    monkeypatch.setattr(
        pipeline,
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
    monkeypatch.setattr(pipeline.send2trash, "send2trash", trash_calls.append)
    monkeypatch.setattr(pipeline, "build_output_path", lambda *_args: output)
    monkeypatch.setattr(pipeline, "build_temp_path", lambda _path: temporary)

    class FakeEncodeHandle:
        def __init__(self, _command, _duration, _temp_path, **_kwargs) -> None:
            pass

        def run(self) -> EncodeResult:
            return EncodeResult(0, False, None)

    monkeypatch.setattr(pipeline, "EncodeHandle", FakeEncodeHandle)
    monkeypatch.setattr(
        pipeline,
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


def test_keep_language_options_reach_the_plan(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    source = Path(__file__).resolve()
    mock_ffmpeg(monkeypatch)
    monkeypatch.setattr(cli, "probe_media", lambda _ffprobe, path: media_info(path))
    captured: list[PlanOptions] = []
    original = cli.build_plan

    def spy(media: MediaInfo, ffmpeg: FFmpegInfo, options: PlanOptions | None = None):
        assert options is not None
        captured.append(options)
        return original(media, ffmpeg, options)

    monkeypatch.setattr(cli, "build_plan", spy)

    result = cli.main(
        [
            "convert",
            str(source),
            "--dry-run",
            "--keep-audio",
            " SPA,und ",
            "--keep-subs",
            "eng",
        ]
    )

    assert result == 0
    assert captured[0].audio_languages == frozenset({"spa", "und"})
    assert captured[0].subtitle_languages == frozenset({"eng"})


def test_language_list_rejects_empty_values() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="language"):
        cli._language_set(" , ")


def test_help_uses_the_reduvid_cli_program_name(capsys) -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(["--help"])

    assert raised.value.code == 0
    assert "usage: reduvid-cli" in capsys.readouterr().out


def test_audio_tracks_and_flags_reach_the_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    source = Path(__file__).resolve()
    mock_ffmpeg(monkeypatch)
    monkeypatch.setattr(cli, "probe_media", lambda _ffprobe, path: media_info(path))
    captured: list[PlanOptions] = []
    original = cli.build_plan

    def spy(media: MediaInfo, ffmpeg: FFmpegInfo, options: PlanOptions | None = None):
        assert options is not None
        captured.append(options)
        return original(media, ffmpeg, options)

    monkeypatch.setattr(cli, "build_plan", spy)

    result = cli.main(
        [
            "convert",
            str(source),
            "--dry-run",
            "--audio-tracks",
            " 1, 3 ",
            "--one-audio-per-language",
            "--reduce-audio",
        ]
    )

    assert result == 0
    assert captured[0].audio_tracks == frozenset({1, 3})
    assert captured[0].one_audio_per_language is True
    assert captured[0].reduce_audio is True


def test_audio_tracks_valid_parses_set() -> None:
    assert cli._track_set("0, 2, 5") == frozenset({0, 2, 5})
    assert cli._track_set("1") == frozenset({1})


@pytest.mark.parametrize("invalid", ["", "  ", "1,", ",1", "-1", "abc", "1.5", "1,-2"])
def test_audio_tracks_invalid_raises_argument_type_error(invalid: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="non-negative"):
        cli._track_set(invalid)


def test_convert_fails_on_invalid_audio_tracks(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    source = Path(__file__).resolve()
    mock_ffmpeg(monkeypatch)
    with pytest.raises(SystemExit) as raised:
        cli.main(["convert", str(source), "--audio-tracks", "invalid"])
    assert raised.value.code == 2
    captured = capsys.readouterr()
    assert "non-negative" in captured.err


def test_probe_audio_estimated_size(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    source = Path(__file__).resolve()
    mock_ffmpeg(monkeypatch)
    media = MediaInfo(
        source,
        "matroska",
        100.0,
        50_000_000,
        [VideoStream(0, "hevc", 1920, 1080, 24.0)],
        [
            AudioStream(1, "eac3", 6, "eng", True, bitrate=640_000),
            AudioStream(2, "flac", 2, "spa", False, bitrate=None),
        ],
        [],
        [],
    )
    monkeypatch.setattr(cli, "probe_media", lambda _ffprobe, _path: media)

    result = cli.main(["probe", str(source)])

    captured = capsys.readouterr()
    assert result == 0
    # 640_000 * 100 / 8 = 8_000_000 bytes -> 8 MB
    assert "Audio 1: eac3, 6 channels, eng, ~8 MB estimated" in captured.out
    assert "Audio 2: flac, 2 channels, spa, —" in captured.out


def test_convert_dry_run_shows_audio_estimated_size(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    source = Path(__file__).resolve()
    mock_ffmpeg(monkeypatch)
    media = MediaInfo(
        source,
        "matroska",
        100.0,
        50_000_000,
        [VideoStream(0, "hevc", 1920, 1080, 24.0)],
        [
            AudioStream(1, "eac3", 6, "eng", True, bitrate=640_000),
            AudioStream(2, "aac", 2, "spa", False, bitrate=None),
        ],
        [],
        [],
    )
    monkeypatch.setattr(cli, "probe_media", lambda _ffprobe, _path: media)

    # Dry-run without --reduce-audio: Stream 1 (eac3 6ch) is copied,
    # Stream 2 (aac 2ch, no bitrate) is copied
    result = cli.main(["convert", str(source), "--dry-run"])
    captured = capsys.readouterr()
    assert result == 0
    # 640_000 * 100 / 8 = 8_000_000 bytes -> 8 MB
    assert "Audio stream 1: copy, ~8 MB estimated" in captured.out
    # Stream 2 has no bitrate -> "—"
    assert "Audio stream 2: copy, —" in captured.out

    # Dry-run with --reduce-audio: Stream 1 encoded to 256k, Stream 2 encoded to 128k
    result = cli.main(["convert", str(source), "--dry-run", "--reduce-audio"])
    captured = capsys.readouterr()
    assert result == 0
    # 256_000 * 100 / 8 = 3_200_000 -> 3 MB
    assert "Audio stream 1: encode as aac at 256k, ~3 MB estimated" in captured.out
    # 128_000 * 100 / 8 = 1_600_000 -> 2 MB
    assert "Audio stream 2: encode as aac at 128k, ~2 MB estimated" in captured.out
