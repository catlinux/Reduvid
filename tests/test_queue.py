# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from pathlib import Path

from reduvid.core.plan import Warning
from reduvid.core.probe import MediaInfo
from reduvid.core.queue import ConversionQueue, ProcessingResult
from reduvid.core.runner import ProgressEvent


def media(path: Path, duration: float, size: int = 100) -> MediaInfo:
    return MediaInfo(path, "mkv", duration, size, [], [], [], [])


def test_queue_processes_in_order_and_uses_duration_weighted_progress(tmp_path: Path) -> None:
    paths = [tmp_path / "short.mkv", tmp_path / "long.mkv"]
    for path in paths:
        path.touch()
    processed: list[Path] = []
    progress = []

    def processor(item: MediaInfo, callback: object) -> ProcessingResult:
        processed.append(item.path)
        if item.path == paths[0]:
            callback(ProgressEvent(10.0, 1.0, 0.0, "end"))  # type: ignore[operator]
        return ProcessingResult(50, (Warning("example"),))

    queue = ConversionQueue(
        processor,
        probe=lambda _ffprobe, path: media(path, 10 if path == paths[0] else 90),
        on_progress=progress.append,
    )
    queue.add_files(paths)

    report = queue.run()

    assert processed == paths
    assert progress[0].fraction_completed == 0.1
    assert report.succeeded == 2


def test_failure_does_not_stop_queue(tmp_path: Path) -> None:
    paths = [tmp_path / "bad.mkv", tmp_path / "good.mkv"]
    for path in paths:
        path.touch()
    processed: list[Path] = []

    def processor(item: MediaInfo, _callback: object) -> ProcessingResult:
        processed.append(item.path)
        if item.path == paths[0]:
            raise RuntimeError("encode failed")
        return ProcessingResult(40)

    queue = ConversionQueue(processor, probe=lambda _ffprobe, path: media(path, 1))
    queue.add_files(paths)

    report = queue.run()

    assert processed == paths
    assert report.failed == 1
    assert report.files[0].reason == "encode failed"


def test_cancel_skips_remaining_files(tmp_path: Path) -> None:
    paths = [tmp_path / f"{number}.mkv" for number in range(3)]
    for path in paths:
        path.touch()
    processed: list[Path] = []
    queue: ConversionQueue

    def processor(item: MediaInfo, _callback: object) -> ProcessingResult:
        processed.append(item.path)
        return ProcessingResult(50)

    def started(_path: Path, index: int, _total: int) -> None:
        if index == 1:
            queue.cancel()

    queue = ConversionQueue(
        processor, probe=lambda _ffprobe, path: media(path, 1), on_file_start=started
    )
    queue.add_files(paths)

    report = queue.run()

    assert processed == paths[:1]
    assert report.succeeded == 1
    assert report.skipped == 2


def test_add_folder_filters_extensions_and_recursion(tmp_path: Path) -> None:
    top = tmp_path / "video.MP4"
    ignored = tmp_path / "notes.txt"
    nested = tmp_path / "nested"
    nested.mkdir()
    nested_video = nested / "clip.webm"
    nested_other = nested / "readme.md"
    for path in (top, ignored, nested_video, nested_other):
        path.touch()

    flat = ConversionQueue(lambda _media, _progress: ProcessingResult(1))
    flat.add_folder(tmp_path)
    recursive = ConversionQueue(lambda _media, _progress: ProcessingResult(1))
    recursive.add_folder(tmp_path, recursive=True)

    assert flat.files == (top,)
    assert recursive.files == (top, nested_video)
