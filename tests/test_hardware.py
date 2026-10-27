# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from reduvid.core import hardware
from reduvid.core.ffmpeg import FFmpegInfo


def ffmpeg_info(
    tmp_path: Path,
    candidates: tuple[str, ...],
    *,
    version: str = "9.0",
) -> FFmpegInfo:
    return FFmpegInfo(
        tmp_path / "ffmpeg",
        tmp_path / "ffprobe",
        version,
        frozenset(),
        frozenset(),
        candidates,
    )


class RecordingRun:
    def __init__(
        self,
        successes: set[str] | None = None,
        errors: dict[str, str] | None = None,
    ) -> None:
        self.successes = successes or set()
        self.errors = errors or {}
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(self, args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        self.calls.append((args, kwargs))
        encoder = args[args.index("-c:v") + 1]
        error = self.errors.get(encoder)
        if error == "timeout":
            raise subprocess.TimeoutExpired(args, float(kwargs["timeout"]))
        if error == "oserror":
            raise OSError("cannot start")
        return subprocess.CompletedProcess(args, 0 if encoder in self.successes else 1)


def test_keeps_only_working_encoders_and_uses_the_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = RecordingRun({"h264_qsv"})
    monkeypatch.setattr(hardware.subprocess, "run", run)
    cache = tmp_path / "cache"
    info = ffmpeg_info(tmp_path, ("h264_nvenc", "hevc_nvenc", "h264_qsv"))

    first = hardware.probe_hardware_encoders(info, cache_dir=cache)
    second = hardware.probe_hardware_encoders(info, cache_dir=cache)

    assert first == ("h264_qsv",)
    assert second == first
    assert len(run.calls) == 3
    assert cache.is_dir()
    assert (cache / "hardware.json").is_file()

    changed_version = ffmpeg_info(
        tmp_path, ("h264_nvenc", "hevc_nvenc", "h264_qsv"), version="10.0"
    )
    newer_run = RecordingRun({"h264_qsv"})
    monkeypatch.setattr(hardware.subprocess, "run", newer_run)

    assert hardware.probe_hardware_encoders(changed_version, cache_dir=cache) == ("h264_qsv",)
    assert len(newer_run.calls) == 3


def test_cache_directory_stores_hardware_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = RecordingRun({"h264_qsv"})
    monkeypatch.setattr(hardware.subprocess, "run", run)
    cache_dir = tmp_path / "cache"
    info = ffmpeg_info(tmp_path, ("h264_qsv",))

    first = hardware.probe_hardware_encoders(info, cache_dir=cache_dir)
    second = hardware.probe_hardware_encoders(info, cache_dir=cache_dir)

    assert first == second == ("h264_qsv",)
    assert len(run.calls) == 1
    assert cache_dir.is_dir()
    assert (cache_dir / "hardware.json").is_file()


def test_timeout_and_oserror_discard_only_their_encoder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = RecordingRun(
        {"h264_qsv"},
        {"h264_nvenc": "timeout", "hevc_nvenc": "oserror"},
    )
    monkeypatch.setattr(hardware.subprocess, "run", run)
    info = ffmpeg_info(tmp_path, ("h264_nvenc", "hevc_nvenc", "h264_qsv"))

    cache = tmp_path / "cache"
    result = hardware.probe_hardware_encoders(info, cache_dir=cache)

    assert result == ("h264_qsv",)
    assert len(run.calls) == 3
    assert (cache / "hardware.json").is_file()


def test_empty_candidates_do_not_run_or_write_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = RecordingRun()
    monkeypatch.setattr(hardware.subprocess, "run", run)
    cache = tmp_path / "cache"

    result = hardware.probe_hardware_encoders(ffmpeg_info(tmp_path, ()), cache_dir=cache)

    assert result == ()
    assert run.calls == []
    assert not cache.exists()


def test_vaapi_gets_device_and_upload_filter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = RecordingRun({"h264_vaapi", "hevc_vaapi"})
    monkeypatch.setattr(hardware.subprocess, "run", run)

    cache = tmp_path / "cache"
    result = hardware.probe_hardware_encoders(
        ffmpeg_info(tmp_path, ("h264_vaapi", "hevc_vaapi")),
        cache_dir=cache,
    )

    assert result == ("h264_vaapi", "hevc_vaapi")
    assert (cache / "hardware.json").is_file()
    vaapi_args, _kwargs = run.calls[0]
    assert vaapi_args[vaapi_args.index("-vaapi_device") + 1] == "/dev/dri/renderD128"
    assert vaapi_args.index("-vaapi_device") < vaapi_args.index("-f")
    assert vaapi_args.index("-vf") < vaapi_args.index("-c:v")
    assert vaapi_args[vaapi_args.index("-vf") + 1] == "format=nv12,hwupload"


def test_non_vaapi_command_has_no_device_or_filter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = RecordingRun({"h264_qsv"})
    monkeypatch.setattr(hardware.subprocess, "run", run)

    cache = tmp_path / "cache"
    hardware.probe_hardware_encoders(
        ffmpeg_info(tmp_path, ("h264_qsv",)),
        cache_dir=cache,
    )

    args, _kwargs = run.calls[0]
    assert "-vaapi_device" not in args
    assert "-vf" not in args
    assert (cache / "hardware.json").is_file()


def test_invalid_cache_is_ignored_and_rewritten(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cache_file = cache_dir / "hardware.json"
    cache_file.write_text("not json", encoding="utf-8")
    run = RecordingRun({"h264_qsv"})
    monkeypatch.setattr(hardware.subprocess, "run", run)

    result = hardware.probe_hardware_encoders(
        ffmpeg_info(tmp_path, ("h264_qsv",)), cache_dir=cache_dir
    )

    assert result == ("h264_qsv",)
    assert len(run.calls) == 1
    assert "h264_qsv" in cache_file.read_text(encoding="utf-8")
