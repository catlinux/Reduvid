# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from pathlib import Path
from subprocess import CompletedProcess

import pytest

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
    monkeypatch.setattr(ffmpeg, "_registry_path", lambda: "")
    monkeypatch.setenv("PATH", "")

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


def test_falls_back_to_registry_path_on_windows(monkeypatch, tmp_path: Path) -> None:
    binary = tmp_path / "ffmpeg.exe"
    probe = tmp_path / "ffprobe.exe"
    binary.write_text("")
    probe.write_text("")
    monkeypatch.setattr(ffmpeg, "sys", type("S", (), {"platform": "win32"}))
    monkeypatch.setattr(ffmpeg, "_registry_path", lambda: f"C:/nowhere;{tmp_path}")
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda name, path=None: None)
    monkeypatch.setenv("PATH", "")
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


def test_describe_search_reports_what_was_found_and_launch_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = tmp_path / "ffmpeg"
    fake.write_text("")
    monkeypatch.setattr(
        ffmpeg, "_find_executable", lambda name, _path: fake if name == "ffmpeg" else None
    )

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError(6, "The handle is invalid")

    monkeypatch.setattr(ffmpeg.subprocess, "run", refuse)

    text = ffmpeg.describe_search(None)

    assert f"ffmpeg: {fake}" in text
    assert "ffprobe: not found" in text
    assert "launching ffmpeg failed" in text
    assert "handle is invalid" in text


def test_describe_search_says_when_nothing_was_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ffmpeg, "_find_executable", lambda _name, _path: None)

    text = ffmpeg.describe_search(None)

    assert "ffmpeg: not found" in text
    assert "launching" not in text


def test_scan_for_exe_finds_the_executable_without_pathext(tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "ffmpeg.exe").write_text("")

    found = ffmpeg._scan_for_exe("ffmpeg", f'{other};"{tools}";', ";")

    assert found == tools / "ffmpeg.exe"
    assert ffmpeg._scan_for_exe("ffprobe", f"{other};{tools}", ";") is None


def _untrusted_link(monkeypatch: pytest.MonkeyPatch, link: Path, target_text: str) -> None:
    """Make *link* behave like winget's link under Windows' redirection trust (WinError 448)."""
    real_is_file = Path.is_file

    def is_file(self: Path) -> bool:
        if self == link:
            raise OSError(448, "untrusted mount point")
        return real_is_file(self)

    monkeypatch.setattr(Path, "is_file", is_file)
    monkeypatch.setattr(Path, "readlink", lambda self: Path(target_text))


def test_existing_file_uses_the_target_of_a_link_it_cannot_follow(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "real" / "ffmpeg.exe"
    target.parent.mkdir()
    target.write_text("")
    link = tmp_path / "Links" / "ffmpeg.exe"
    _untrusted_link(monkeypatch, link, "\\\\?\\" + str(target))

    assert ffmpeg._existing_file(link) == target


def test_existing_file_gives_up_quietly_when_the_link_cannot_be_read(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    link = tmp_path / "ffmpeg.exe"
    _untrusted_link(monkeypatch, link, str(tmp_path / "missing.exe"))

    assert ffmpeg._existing_file(link) is None

    def unreadable(_self: Path) -> Path:
        raise OSError(448, "untrusted mount point")

    monkeypatch.setattr(Path, "readlink", unreadable)
    assert ffmpeg._existing_file(link) is None


def test_scan_for_exe_follows_an_untrusted_link_to_its_target(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "real" / "ffmpeg.exe"
    target.parent.mkdir()
    target.write_text("")
    links = tmp_path / "Links"
    _untrusted_link(monkeypatch, links / "ffmpeg.exe", str(target))

    assert ffmpeg._scan_for_exe("ffmpeg", str(links), ";") == target
