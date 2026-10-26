# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Discovery and capability inspection for FFmpeg installations."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FFmpegInfo:
    """Paths and selected capabilities reported by an FFmpeg installation."""

    ffmpeg_path: Path
    ffprobe_path: Path
    version: str
    encoders: frozenset[str]
    filters: frozenset[str]
    hardware_encoders: tuple[str, ...]

    @property
    def has_libx264(self) -> bool:
        return "libx264" in self.encoders

    @property
    def has_libx265(self) -> bool:
        return "libx265" in self.encoders

    @property
    def has_zscale(self) -> bool:
        return "zscale" in self.filters

    @property
    def has_tonemap(self) -> bool:
        return "tonemap" in self.filters


def _find_executable(name: str, configured_path: Path | None) -> Path | None:
    if configured_path is not None and configured_path.is_file():
        return configured_path
    executable = shutil.which(name)
    if executable is not None:
        return Path(executable)
    if sys.platform == "win32":
        executable = shutil.which(name, path=_registry_path())
        if executable is not None:
            return Path(executable)
    return None


def _registry_path() -> str:
    """Return the user and machine PATH values straight from the Windows registry.

    A tool installed by winget (or any installer) writes its PATH entry there
    immediately, but `os.environ["PATH"]` only reflects it in processes started
    after a fresh logon — so a just-installed FFmpeg would otherwise go
    undetected until the user signs out and back in.
    """
    import winreg

    values = []
    for hive, subkey in (
        (winreg.HKEY_CURRENT_USER, "Environment"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
    ):
        try:
            with winreg.OpenKey(hive, subkey) as key:
                value, _kind = winreg.QueryValueEx(key, "Path")
                values.append(value)
        except OSError:
            continue
    return ";".join(values)


def _listed_names(output: str) -> set[str]:
    names: set[str] = set()
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and re.fullmatch(r"[A-Z.]{3,6}", parts[0]):
            names.add(parts[1])
    return names


def _version(output: str) -> str:
    match = re.search(r"^ffmpeg version\s+(\S+)", output, re.MULTILINE)
    return match.group(1) if match is not None else "unknown"


def detect_ffmpeg(configured_path: Path | None = None) -> FFmpegInfo | None:
    """Locate FFmpeg and ffprobe, returning ``None`` if either is unavailable."""
    ffmpeg_path = _find_executable("ffmpeg", configured_path)
    if ffmpeg_path is None:
        return None

    suffix = ".exe" if ffmpeg_path.suffix.lower() == ".exe" else ""
    sibling_probe = ffmpeg_path.with_name(f"ffprobe{suffix}")
    ffprobe_path = _find_executable("ffprobe", sibling_probe)
    if ffprobe_path is None:
        return None

    version_result = subprocess.run(  # noqa: S603
        [str(ffmpeg_path), "-version"], capture_output=True, text=True, check=False
    )
    encoder_result = subprocess.run(  # noqa: S603
        [str(ffmpeg_path), "-encoders"], capture_output=True, text=True, check=False
    )
    filter_result = subprocess.run(  # noqa: S603
        [str(ffmpeg_path), "-filters"], capture_output=True, text=True, check=False
    )
    encoders = _listed_names(encoder_result.stdout)
    filters = _listed_names(filter_result.stdout)
    hardware = tuple(
        name
        for name in sorted(encoders)
        if any(marker in name.lower() for marker in ("nvenc", "_qsv", "vaapi", "_amf"))
    )
    return FFmpegInfo(
        ffmpeg_path=ffmpeg_path,
        ffprobe_path=ffprobe_path,
        version=_version(version_result.stdout),
        encoders=frozenset(encoders),
        filters=frozenset(filters),
        hardware_encoders=hardware,
    )
