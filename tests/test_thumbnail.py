# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from reduvid.core import thumbnail
from reduvid.core.probe import MediaInfo, probe_media


def media(path: Path, *, duration: float = 60.0, size: int | None = None) -> MediaInfo:
    actual_size = size if size is not None else path.stat().st_size
    return MediaInfo(path, "matroska", duration, actual_size, [], [], [], [])


class RecordingRun:
    def __init__(
        self, *, returncode: int = 0, error: str | None = None, create: bool = True
    ) -> None:
        self.returncode = returncode
        self.error = error
        self.create = create
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(self, args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        self.calls.append((args, kwargs))
        if self.error == "timeout":
            raise subprocess.TimeoutExpired(args, float(kwargs["timeout"]))
        if self.error == "oserror":
            raise OSError("ffmpeg failed")
        if self.create:
            Path(args[-1]).write_bytes(b"\xff\xd8fake-jpeg")
        return subprocess.CompletedProcess(args, self.returncode)


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path = tmp_path / "video.mkv"
    path.write_bytes(b"video")
    return path


@pytest.fixture
def cache(tmp_path: Path) -> Path:
    return tmp_path / "cache"


def test_first_call_creates_a_cached_jpeg_and_second_call_does_not_run_ffmpeg(
    monkeypatch: pytest.MonkeyPatch, source: Path, cache: Path
) -> None:
    run = RecordingRun()
    monkeypatch.setattr(thumbnail.subprocess, "run", run)
    ffmpeg_path = cache.parent / "ffmpeg"

    first = thumbnail.extract_thumbnail(ffmpeg_path, media(source), cache_dir=cache)
    second = thumbnail.extract_thumbnail(ffmpeg_path, media(source), cache_dir=cache)

    assert first is not None
    assert second == first
    assert first.parent == cache
    assert first.suffix == ".jpg"
    assert first.read_bytes().startswith(b"\xff\xd8")
    assert len(run.calls) == 1
    args, kwargs = run.calls[0]
    assert args[0] == str(ffmpeg_path)
    assert args[args.index("-ss") + 1] == "6.000"
    assert args.index("-ss") < args.index("-i")
    assert args[args.index("-vf") + 1] == "scale=320:-2"
    assert args[args.index("-frames:v") + 1] == "1"
    assert args[args.index("-q:v") + 1] == "4"
    assert args[-1].endswith(".tmp.jpg")
    assert Path(args[-1]).parent == cache
    assert kwargs["timeout"] == 20.0
    assert kwargs["check"] is False
    assert not Path(args[-1]).exists()


def test_size_and_mtime_changes_produce_different_thumbnails(
    monkeypatch: pytest.MonkeyPatch, source: Path, cache: Path
) -> None:
    run = RecordingRun()
    monkeypatch.setattr(thumbnail.subprocess, "run", run)
    ffmpeg_path = cache.parent / "ffmpeg"

    first = thumbnail.extract_thumbnail(ffmpeg_path, media(source), cache_dir=cache)
    source.write_bytes(b"a different video")
    second = thumbnail.extract_thumbnail(ffmpeg_path, media(source), cache_dir=cache)
    stat = source.stat()
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    third = thumbnail.extract_thumbnail(ffmpeg_path, media(source), cache_dir=cache)

    assert first is not None and second is not None and third is not None
    assert len({first, second, third}) == 3
    assert len(run.calls) == 3


@pytest.mark.parametrize("error", ["returncode", "timeout", "oserror"])
def test_ffmpeg_failures_return_none_and_remove_the_temporary(
    monkeypatch: pytest.MonkeyPatch, source: Path, cache: Path, error: str
) -> None:
    run = RecordingRun(
        returncode=1 if error == "returncode" else 0,
        error=None if error == "returncode" else error,
    )
    monkeypatch.setattr(thumbnail.subprocess, "run", run)

    result = thumbnail.extract_thumbnail(cache.parent / "ffmpeg", media(source), cache_dir=cache)

    assert result is None
    assert list(cache.iterdir()) == []


def test_empty_output_is_rejected(
    monkeypatch: pytest.MonkeyPatch, source: Path, cache: Path
) -> None:
    run = RecordingRun(create=False)
    monkeypatch.setattr(thumbnail.subprocess, "run", run)

    result = thumbnail.extract_thumbnail(cache.parent / "ffmpeg", media(source), cache_dir=cache)

    assert result is None
    assert list(cache.iterdir()) == []


def test_missing_source_returns_none_without_running_ffmpeg(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = RecordingRun()
    monkeypatch.setattr(thumbnail.subprocess, "run", run)
    cache = tmp_path / "cache"

    result = thumbnail.extract_thumbnail(
        tmp_path / "ffmpeg", media(tmp_path / "missing.mkv", size=0), cache_dir=cache
    )

    assert result is None
    assert run.calls == []
    assert not cache.exists()


@pytest.mark.parametrize("duration", [float("nan"), float("inf"), 0.0, -5.0])
def test_invalid_duration_uses_zero_as_the_seek(
    monkeypatch: pytest.MonkeyPatch, source: Path, cache: Path, duration: float
) -> None:
    run = RecordingRun()
    monkeypatch.setattr(thumbnail.subprocess, "run", run)

    result = thumbnail.extract_thumbnail(
        cache.parent / "ffmpeg",
        media(source, duration=duration),
        cache_dir=cache,
    )

    assert result is not None
    args, _kwargs = run.calls[0]
    assert args[args.index("-ss") + 1] == "0.000"


def test_default_cache_directory_uses_platformdirs(
    monkeypatch: pytest.MonkeyPatch, source: Path, tmp_path: Path
) -> None:
    run = RecordingRun()
    monkeypatch.setattr(thumbnail.subprocess, "run", run)
    user_cache = tmp_path / "user-cache"
    monkeypatch.setattr(thumbnail.platformdirs, "user_cache_dir", lambda _app: str(user_cache))

    result = thumbnail.extract_thumbnail(tmp_path / "ffmpeg", media(source))

    assert result is not None
    assert result.parent == user_cache / "thumbnails"


def test_clear_thumbnail_cache_removes_only_jpegs(cache: Path) -> None:
    cache.mkdir()
    first = cache / "one.jpg"
    first.write_bytes(b"jpg")
    temporary = cache / "two.tmp.jpg"
    temporary.write_bytes(b"jpg")
    other = cache / "notes.txt"
    other.write_text("keep", encoding="utf-8")

    thumbnail.clear_thumbnail_cache(cache)

    assert not first.exists()
    assert not temporary.exists()
    assert other.exists()


@pytest.mark.ffmpeg
def test_real_ffmpeg_produces_a_valid_jpeg(ffmpeg_info, cache: Path, tmp_path: Path) -> None:
    video_path = tmp_path / "real-input.mkv"
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
            "testsrc2=duration=2:size=160x120:rate=10",
            "-c:v",
            "ffv1",
            "-an",
            str(video_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    info = probe_media(ffmpeg_info.ffprobe_path, video_path)

    result = thumbnail.extract_thumbnail(ffmpeg_info.ffmpeg_path, info, cache_dir=cache)

    assert result is not None
    assert result.read_bytes()[:2] == b"\xff\xd8"
