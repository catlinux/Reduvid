# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Check which advertised hardware encoders actually work on this machine."""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

import platformdirs

from reduvid.core.ffmpeg import FFmpegInfo


def _default_cache_file() -> Path:
    return Path(platformdirs.user_cache_dir("reduvid")) / "hardware.json"


def _cache_file(cache_dir: Path | None) -> Path:
    if cache_dir is None:
        return _default_cache_file()
    return cache_dir / "hardware.json"


def _cache_key(info: FFmpegInfo) -> str:
    return json.dumps(
        [
            str(info.ffmpeg_path.resolve()),
            info.version,
            list(info.hardware_encoders),
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _read_cache(cache_file: Path, key: str) -> tuple[str, ...] | None:
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    value = data.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return None
    return tuple(value)


def _write_cache(cache_file: Path, key: str, encoders: tuple[str, ...]) -> None:
    data: dict[str, object] = {}
    try:
        existing = json.loads(cache_file.read_text(encoding="utf-8"))
        if isinstance(existing, dict):
            data = existing
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass

    data[key] = list(encoders)
    temporary: Path | None = None
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".hardware-", suffix=".json", dir=cache_file.parent
        )
        temporary = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        temporary.replace(cache_file)
    except (OSError, TypeError, ValueError):
        pass
    finally:
        if temporary is not None:
            with contextlib.suppress(OSError):
                temporary.unlink(missing_ok=True)


def _probe_command(ffmpeg_path: Path, encoder: str) -> list[str]:
    arguments = [
        str(ffmpeg_path),
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
    ]
    if "vaapi" in encoder.lower():
        arguments.extend(["-vaapi_device", "/dev/dri/renderD128"])
    arguments.extend(
        [
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=256x256:r=1:d=1",
            "-frames:v",
            "1",
        ]
    )
    if "vaapi" in encoder.lower():
        arguments.extend(["-vf", "format=nv12,hwupload"])
    arguments.extend(["-c:v", encoder, "-f", "null", "-"])
    return arguments


def probe_hardware_encoders(
    info: FFmpegInfo,
    *,
    timeout: float = 10.0,
    cache_dir: Path | None = None,
) -> tuple[str, ...]:
    """Return the advertised hardware encoders that can encode one frame."""
    if not info.hardware_encoders:
        return ()

    cache_file = _cache_file(cache_dir)
    try:
        key = _cache_key(info)
    except OSError:
        key = ""
    if key:
        cached = _read_cache(cache_file, key)
        if cached is not None:
            return cached

    valid: list[str] = []
    for encoder in info.hardware_encoders:
        try:
            result = subprocess.run(  # noqa: S603
                _probe_command(info.ffmpeg_path, encoder),
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            valid.append(encoder)

    if key:
        _write_cache(cache_file, key, tuple(valid))
    return tuple(valid)
