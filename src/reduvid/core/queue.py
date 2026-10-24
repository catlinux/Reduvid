# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Sequential conversion queue with duration-weighted progress."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from reduvid.core.plan import Warning
from reduvid.core.probe import MediaInfo, probe_media
from reduvid.core.report import FileReport, QueueReport, build_file_report, build_queue_report
from reduvid.core.runner import ProgressEvent

VIDEO_EXTENSIONS = frozenset(
    {
        ".3gp",
        ".avi",
        ".m2ts",
        ".m4v",
        ".mkv",
        ".mov",
        ".mp4",
        ".mpeg",
        ".mpg",
        ".ts",
        ".webm",
        ".wmv",
    }
)


@dataclass(frozen=True)
class ProcessingResult:
    """Result supplied by the injected per-file processing callback."""

    final_size: int
    warnings: tuple[Warning, ...] = ()


@dataclass(frozen=True)
class QueueProgressEvent:
    file_path: Path
    current_index: int
    total_files: int
    fraction_completed: float
    file_progress: ProgressEvent | None = None


class ProcessorProtocol(Protocol):
    def __call__(
        self, media: MediaInfo, on_progress: Callable[[ProgressEvent], None]
    ) -> ProcessingResult: ...


class ConversionQueue:
    """Process probed files one at a time through a caller-supplied pipeline."""

    def __init__(
        self,
        processor: ProcessorProtocol,
        *,
        ffprobe_path: Path = Path("ffprobe"),
        on_progress: Callable[[QueueProgressEvent], None] | None = None,
        on_file_start: Callable[[Path, int, int], None] | None = None,
        on_file_complete: Callable[[FileReport], None] | None = None,
        on_file_failed: Callable[[FileReport], None] | None = None,
        on_warnings: Callable[[Path, tuple[Warning, ...]], None] | None = None,
        on_finished: Callable[[QueueReport], None] | None = None,
        probe: Callable[[Path, Path], MediaInfo] = probe_media,
    ) -> None:
        self.processor = processor
        self.ffprobe_path = ffprobe_path
        self.on_progress = on_progress
        self.on_file_start = on_file_start
        self.on_file_complete = on_file_complete
        self.on_file_failed = on_file_failed
        self.on_warnings = on_warnings
        self.on_finished = on_finished
        self.probe = probe
        self._paths: list[Path] = []
        self._cancelled = threading.Event()
        self._active = False
        self._lock = threading.Lock()

    @property
    def files(self) -> tuple[Path, ...]:
        return tuple(self._paths)

    def add_files(self, paths: Iterable[Path]) -> None:
        for path in paths:
            if not path.is_absolute():
                raise ValueError("input paths must be absolute")
            self._paths.append(path)

    def add_folder(
        self, folder: Path, *, recursive: bool = False, extensions: Iterable[str] = VIDEO_EXTENSIONS
    ) -> None:
        if not folder.is_absolute():
            raise ValueError("folder path must be absolute")
        if not folder.is_dir():
            raise NotADirectoryError(folder)
        accepted = {
            extension.casefold() if extension.startswith(".") else f".{extension.casefold()}"
            for extension in extensions
        }
        candidates = folder.rglob("*") if recursive else folder.iterdir()
        self.add_files(
            sorted(
                (
                    item
                    for item in candidates
                    if item.is_file() and item.suffix.casefold() in accepted
                ),
                key=lambda item: (len(item.relative_to(folder).parts), item),
            )
        )

    def run(self) -> QueueReport:
        with self._lock:
            if self._active:
                raise RuntimeError("queue is already running")
            self._active = True
        self._cancelled.clear()
        reports_by_index: dict[int, FileReport] = {}
        media_items: list[MediaInfo | None] = []
        for index, path in enumerate(self._paths, start=1):
            try:
                media_items.append(self.probe(self.ffprobe_path, path))
            except Exception as error:
                media_items.append(None)
                reports_by_index[index] = build_file_report(
                    path,
                    "failed",
                    _file_size(path),
                    reason=str(error),
                    error_code="probe_failed",
                )
        valid = [media for media in media_items if media is not None]
        total_duration = sum(max(0.0, media.duration) for media in valid)
        completed_duration = 0.0
        try:
            for index, media in enumerate(media_items, start=1):
                path = self._paths[index - 1]
                if self._cancelled.is_set():
                    reports_by_index[index] = build_file_report(
                        path,
                        "skipped",
                        media.size if media else _file_size(path),
                        reason="cancelled",
                    )
                    continue
                if media is None:
                    report = reports_by_index[index]
                    if self.on_file_failed is not None:
                        self.on_file_failed(report)
                    continue
                if self.on_file_start is not None:
                    self.on_file_start(path, index, len(self._paths))
                duration = max(0.0, media.duration)

                def progress_callback(
                    event: ProgressEvent,
                    *,
                    current: MediaInfo = media,
                    completed: float = completed_duration,
                    current_index: int = index,
                ) -> None:
                    fraction = _global_fraction(
                        completed,
                        event.tiempo_procesado_segundos,
                        current.duration,
                        total_duration,
                    )
                    if self.on_progress is not None:
                        self.on_progress(
                            QueueProgressEvent(
                                current.path, current_index, len(self._paths), fraction, event
                            )
                        )

                try:
                    result = self.processor(media, progress_callback)
                    report = build_file_report(
                        path, "success", media.size, result.final_size, result.warnings
                    )
                    reports_by_index[index] = report
                    completed_duration += duration
                    if self.on_warnings is not None and result.warnings:
                        self.on_warnings(path, result.warnings)
                    if self.on_file_complete is not None:
                        self.on_file_complete(report)
                    if self.on_progress is not None:
                        self.on_progress(
                            QueueProgressEvent(
                                path,
                                index,
                                len(self._paths),
                                _global_fraction(completed_duration, 0.0, 0.0, total_duration),
                            )
                        )
                except Exception as error:
                    report = build_file_report(
                        path, "failed", media.size, reason=str(error), error_code=_error_code(error)
                    )
                    reports_by_index[index] = report
                    completed_duration += duration
                    if self.on_file_failed is not None:
                        self.on_file_failed(report)
        finally:
            with self._lock:
                self._active = False
        final_report = build_queue_report(
            [reports_by_index[index] for index in sorted(reports_by_index)]
        )
        if self.on_finished is not None:
            self.on_finished(final_report)
        return final_report

    def cancel(self) -> None:
        self._cancelled.set()
        control = getattr(self.processor, "cancel", None)
        if callable(control):
            control()

    def pause(self) -> None:
        """Pause is provided by processing implementations that expose queue controls."""
        control = getattr(self.processor, "pause", None)
        if callable(control):
            control()

    def resume(self) -> None:
        control = getattr(self.processor, "resume", None)
        if callable(control):
            control()


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _error_code(error: BaseException) -> str:
    code = getattr(error, "code", None)
    return code if isinstance(code, str) else "unknown"


def _global_fraction(completed: float, processed: float, duration: float, total: float) -> float:
    if total <= 0:
        return 1.0 if completed > 0 or processed > 0 else 0.0
    return min(1.0, max(0.0, (completed + min(max(processed, 0.0), max(duration, 0.0))) / total))
