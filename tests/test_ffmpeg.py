# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from pathlib import Path
from subprocess import CompletedProcess

from reduvid.core import ffmpeg


def _run_mock(
    monkeypatch,
    encoder_output: str,
    filter_output: str,
    hwaccel_output: str = "Hardware acceleration methods:\ncuda\nd3d11va\n\n",
) -> None:
    outputs = {
        "-version": "ffmpeg version 7.0.2 Copyright (c) FFmpeg developers\n",
        "-encoders": encoder_output,
        "-filters": filter_output,
        "-hide_banner": hwaccel_output,
    }

    def run(args, **kwargs):
        return CompletedProcess(args, 0, stdout=outputs[args[1]], stderr="")

    monkeypatch.setattr(ffmpeg.subprocess, "run", run)


def test_detects_selected_capabilities(monkeypatch) -> None:
    binary = Path("/mock/bin/ffmpeg")
    probe = Path("/mock/bin/ffprobe")
    monkeypatch.setattr(Path, "is_file", lambda self: self in (binary, probe))
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda name, path=None: None)
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
    assert info.hwaccels == ("cuda", "d3d11va")


def test_detects_filters_with_two_flag_columns_and_skips_legend(monkeypatch) -> None:
    binary = Path("/mock/bin/ffmpeg")
    probe = Path("/mock/bin/ffprobe")
    monkeypatch.setattr(Path, "is_file", lambda self: self in (binary, probe))
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda name, path=None: None)
    _run_mock(
        monkeypatch,
        "Encoders:\n V..... = Video\n ------\n V....D libx264 H.264\n",
        "Filters:\n  T.. = Timeline support\n  ------\n"
        " .S tonemap           V->V       Conversion to/from different dynamic ranges.\n"
        " .S zscale            V->V       Apply resizing, colorspace and bit depth conversion.\n",
    )

    info = ffmpeg.detect_ffmpeg(binary)

    assert info is not None
    assert info.has_zscale and info.has_tonemap
    assert "=" not in info.filters and "=" not in info.encoders


def test_hwaccels_are_empty_when_the_probe_fails(monkeypatch) -> None:
    binary = Path("/mock/bin/ffmpeg")
    probe = Path("/mock/bin/ffprobe")
    monkeypatch.setattr(Path, "is_file", lambda self: self in (binary, probe))
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda name, path=None: None)
    outputs = {
        "-version": "ffmpeg version 7.0.2 Copyright (c) FFmpeg developers\n",
        "-encoders": "Encoders:\n",
        "-filters": "Filters:\n",
    }

    def run(args, **kwargs):
        if args[1] == "-hide_banner":
            return CompletedProcess(args, 1, stdout="", stderr="failed")
        return CompletedProcess(args, 0, stdout=outputs[args[1]], stderr="")

    monkeypatch.setattr(ffmpeg.subprocess, "run", run)

    info = ffmpeg.detect_ffmpeg(binary)

    assert info is not None
    assert info.hwaccels == ()


def test_missing_capabilities_are_false(monkeypatch) -> None:
    binary = Path("/mock/bin/ffmpeg")
    probe = Path("/mock/bin/ffprobe")
    monkeypatch.setattr(Path, "is_file", lambda self: self in (binary, probe))
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda name, path=None: None)
    _run_mock(monkeypatch, "Encoders:\n V..... mpeg4 MPEG-4\n", "Filters:\n ... scale V->V\n")

    info = ffmpeg.detect_ffmpeg(binary)

    assert info is not None
    assert not info.has_libx264 and not info.has_libx265
    assert not info.has_zscale and not info.has_tonemap


def test_missing_ffmpeg_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda name, path=None: None)

    assert ffmpeg.detect_ffmpeg(Path("missing-ffmpeg")) is None


def test_invalid_configured_path_falls_back_to_path(monkeypatch) -> None:
    binary = Path("/mock/bin/ffmpeg")
    probe = Path("/mock/bin/ffprobe")
    monkeypatch.setattr(Path, "is_file", lambda self: self in (binary, probe))
    monkeypatch.setattr(
        ffmpeg.shutil,
        "which",
        lambda name, path=None: str(binary if name == "ffmpeg" else probe),
    )
    _run_mock(monkeypatch, "Encoders:\n", "Filters:\n")

    info = ffmpeg.detect_ffmpeg(Path("/invalid/ffmpeg"))

    assert info is not None
    assert info.ffmpeg_path == binary
    assert info.ffprobe_path == probe


def test_falls_back_to_registry_path_on_windows(monkeypatch) -> None:
    binary = Path("/mock/bin/ffmpeg")
    probe = Path("/mock/bin/ffprobe")
    monkeypatch.setattr(Path, "is_file", lambda self: self in (binary, probe))
    monkeypatch.setattr(ffmpeg, "sys", type("S", (), {"platform": "win32"}))
    monkeypatch.setattr(ffmpeg, "_registry_path", lambda: "C:\\registry\\bin")

    def which(name: str, path: str | None = None) -> str | None:
        if path is None:
            return None
        assert path == "C:\\registry\\bin"
        return str(binary if name == "ffmpeg" else probe)

    monkeypatch.setattr(ffmpeg.shutil, "which", which)
    _run_mock(monkeypatch, "Encoders:\n", "Filters:\n")

    info = ffmpeg.detect_ffmpeg()

    assert info is not None
    assert info.ffmpeg_path == binary
    assert info.ffprobe_path == probe


def test_registry_fallback_is_skipped_outside_windows(monkeypatch) -> None:
    monkeypatch.setattr(ffmpeg, "sys", type("S", (), {"platform": "linux"}))
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda name, path=None: None)

    def fail_registry_path() -> str:
        raise AssertionError("_registry_path must not be called outside Windows")

    monkeypatch.setattr(ffmpeg, "_registry_path", fail_registry_path)

    assert ffmpeg.detect_ffmpeg() is None
