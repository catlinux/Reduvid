# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from pathlib import Path
from subprocess import CompletedProcess

from reduvid.core import ffmpeg


def _run_mock(monkeypatch, encoder_output: str, filter_output: str) -> None:
    outputs = {
        "-version": "ffmpeg version 7.0.2 Copyright (c) FFmpeg developers\n",
        "-encoders": encoder_output,
        "-filters": filter_output,
    }

    def run(args, **kwargs):
        return CompletedProcess(args, 0, stdout=outputs[args[1]], stderr="")

    monkeypatch.setattr(ffmpeg.subprocess, "run", run)


def test_detects_selected_capabilities(monkeypatch) -> None:
    binary = Path("/mock/bin/ffmpeg")
    probe = Path("/mock/bin/ffprobe")
    monkeypatch.setattr(Path, "is_file", lambda self: self in (binary, probe))
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda name: None)
    _run_mock(
        monkeypatch,
        "Encoders:\n V..... libx264 H.264\n V..... libx265 H.265\n V..... h264_nvenc NVENC\n",
        "Filters:\n ... zscale V->V\n ... tonemap V->V\n",
    )

    info = ffmpeg.detect_ffmpeg(binary)

    assert info is not None
    assert info.version == "7.0.2"
    assert info.has_libx264 and info.has_libx265
    assert info.has_zscale and info.has_tonemap
    assert info.hardware_encoders == ("h264_nvenc",)


def test_missing_capabilities_are_false(monkeypatch) -> None:
    binary = Path("/mock/bin/ffmpeg")
    probe = Path("/mock/bin/ffprobe")
    monkeypatch.setattr(Path, "is_file", lambda self: self in (binary, probe))
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda name: None)
    _run_mock(monkeypatch, "Encoders:\n V..... mpeg4 MPEG-4\n", "Filters:\n ... scale V->V\n")

    info = ffmpeg.detect_ffmpeg(binary)

    assert info is not None
    assert not info.has_libx264 and not info.has_libx265
    assert not info.has_zscale and not info.has_tonemap


def test_missing_ffmpeg_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda name: None)

    assert ffmpeg.detect_ffmpeg(Path("missing-ffmpeg")) is None


def test_invalid_configured_path_falls_back_to_path(monkeypatch) -> None:
    binary = Path("/mock/bin/ffmpeg")
    probe = Path("/mock/bin/ffprobe")
    monkeypatch.setattr(Path, "is_file", lambda self: self in (binary, probe))
    monkeypatch.setattr(
        ffmpeg.shutil,
        "which",
        lambda name: str(binary if name == "ffmpeg" else probe),
    )
    _run_mock(monkeypatch, "Encoders:\n", "Filters:\n")

    info = ffmpeg.detect_ffmpeg(Path("/invalid/ffmpeg"))

    assert info is not None
    assert info.ffmpeg_path == binary
    assert info.ffprobe_path == probe
