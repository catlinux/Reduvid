# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Extract small JPEG thumbnails from videos and cache them on disk."""

from __future__ import annotations

import contextlib
import hashlib
import math
import os
import subprocess
import tempfile
from pathlib import Path

import platformdirs

from reduvid.core.probe import MediaInfo


def _default_cache_dir() -> Path:
    return Path(platformdirs.user_cache_dir("reduvid")) / "thumbnails"


def _cache_path(cache_dir: Path, media: MediaInfo, width: int) -> Path:
    stat = media.path.stat()
    key = "\0".join(
        (
            str(media.path.resolve()),
            str(stat.st_size),
            str(stat.st_mtime_ns),
            str(width),
        )
    )
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return cache_dir / f"{digest}.jpg"


def _seek_seconds(duration: float) -> str:
    if not math.isfinite(duration) or duration <= 0:
        return "0.000"
    return f"{max(duration * 0.1, 0.0):.3f}"


def extract_thumbnail(
    ffmpeg_path: Path,
    media: MediaInfo,
    *,
    width: int = 320,
    cache_dir: Path | None = None,
    timeout: float = 20.0,
) -> Path | None:
    """Return a cached JPEG thumbnail, creating it with FFmpeg when needed."""
    if not media.path.exists():
        return None

    target_dir = cache_dir if cache_dir is not None else _default_cache_dir()
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        final_path = _cache_path(target_dir, media, width)
        if final_path.exists() and final_path.stat().st_size > 0:
            return final_path
    except OSError:
        return None

    temp_path: Path | None = None
    try:
        descriptor, temp_name = tempfile.mkstemp(
            prefix=".thumbnail-", suffix=".tmp.jpg", dir=target_dir
        )
        temp_path = Path(temp_name)
        os.close(descriptor)
        completed = subprocess.run(  # noqa: S603
            [
                str(ffmpeg_path),
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                _seek_seconds(media.duration),
                "-i",
                str(media.path),
                "-frames:v",
                "1",
                "-vf",
                f"scale={width}:-2",
                "-q:v",
                "4",
                "-y",
                str(temp_path),
            ],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        if completed.returncode != 0:
            return None
        if not temp_path.exists() or temp_path.stat().st_size <= 0:
            return None
        temp_path.replace(final_path)
        return final_path
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        if temp_path is not None:
            with contextlib.suppress(OSError):
                temp_path.unlink(missing_ok=True)


def clear_thumbnail_cache(cache_dir: Path | None = None) -> None:
    """Delete the cached JPEG files, leaving other files untouched."""
    target_dir = cache_dir if cache_dir is not None else _default_cache_dir()
    if not target_dir.exists():
        return
    for path in target_dir.glob("*.jpg"):
        with contextlib.suppress(OSError):
            path.unlink(missing_ok=True)
