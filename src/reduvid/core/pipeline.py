# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Per-file processing shared by the CLI and the graphical interface."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import send2trash  # type: ignore[import-untyped]

from reduvid.core.command import build_command
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.naming import build_output_path, build_temp_path, finalize_output
from reduvid.core.plan import PlanOptions, build_plan
from reduvid.core.probe import MediaInfo
from reduvid.core.queue import ProcessingResult
from reduvid.core.runner import EncodeError, EncodeHandle, EncodeResult, ProgressEvent
from reduvid.core.verify import verify_output

PipelineErrorCode = Literal["cancelled", "verification_failed"]


class PipelineError(RuntimeError):
    """A processing failure with a user-facing, translatable error code."""

    def __init__(self, code: PipelineErrorCode, detail: str) -> None:
        self.code = code
        self.detail = detail
        if code == "verification_failed":
            message = f"Output verification failed: {detail}."
        else:
            message = detail
        super().__init__(message)


class FileProcessor:
    """Convert one media file, exposing pause, resume and cancel controls."""

    def __init__(
        self,
        ffmpeg_info: FFmpegInfo,
        options: PlanOptions,
        *,
        output_dir: Path | None = None,
        threads: int | None = None,
        replace_original: bool = False,
        hw_decode: bool = True,
    ) -> None:
        self.ffmpeg_info = ffmpeg_info
        self.options = options
        self.output_dir = output_dir
        self.threads = threads
        self.replace_original = replace_original
        self.hw_decode = hw_decode
        self._lock = threading.Lock()
        self._handle: EncodeHandle | None = None
        self._cancelled = False
        self._last_output_path: Path | None = None

    @property
    def last_output_path(self) -> Path | None:
        """Output of the most recent successful file, for caller-side reporting."""
        return self._last_output_path

    def __call__(
        self, media: MediaInfo, on_progress: Callable[[ProgressEvent], None]
    ) -> ProcessingResult:
        if self._cancelled:
            raise PipelineError("cancelled", "Encoding was cancelled.")

        plan = build_plan(media, self.ffmpeg_info, self.options)
        destination_dir = self.output_dir or media.path.parent
        destination_dir.mkdir(parents=True, exist_ok=True)
        output_path = build_output_path(media.path, destination_dir, plan.container)
        temp_path = build_temp_path(output_path)
        use_hw_decode = self.hw_decode and bool(self.ffmpeg_info.hwaccels)
        try:
            try:
                result = self._run_handle(
                    build_command(media, plan, media.path, temp_path, hw_decode=use_hw_decode),
                    media.duration,
                    temp_path,
                    on_progress,
                )
            except EncodeError:
                if not use_hw_decode or self._is_cancelled():
                    raise
                temp_path.unlink(missing_ok=True)
                result = self._run_handle(
                    build_command(media, plan, media.path, temp_path, hw_decode=False),
                    media.duration,
                    temp_path,
                    on_progress,
                )
            if result.cancelled:
                raise PipelineError("cancelled", "Encoding was cancelled.")
            verification = verify_output(
                self.ffmpeg_info.ffprobe_path,
                media.path,
                media.duration,
                media.size,
                temp_path,
            )
            if not verification.passed:
                raise PipelineError("verification_failed", verification.reason)
            finalize_output(temp_path, output_path)
            if self.replace_original:
                send2trash.send2trash(str(media.path))
            self._last_output_path = output_path
            return ProcessingResult(output_path.stat().st_size, plan.warnings)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
        finally:
            with self._lock:
                self._handle = None

    def _run_handle(
        self,
        command: list[str],
        duration: float,
        temp_path: Path,
        on_progress: Callable[[ProgressEvent], None],
    ) -> EncodeResult:
        handle = EncodeHandle(
            command,
            duration,
            temp_path,
            on_progress=on_progress,
            threads=self.threads,
            ffmpeg_path=self.ffmpeg_info.ffmpeg_path,
        )
        with self._lock:
            cancelled_early = self._cancelled
            self._handle = handle
        if cancelled_early:
            handle.cancel()
        return handle.run()

    def _is_cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    def pause(self) -> None:
        """Suspend the running encode, if any."""
        handle = self._current_handle()
        if handle is not None:
            handle.pause()

    def resume(self) -> None:
        """Resume a paused encode, if any."""
        handle = self._current_handle()
        if handle is not None:
            handle.resume()

    def cancel(self) -> None:
        """Cancel the running encode, or prevent the next file from starting."""
        with self._lock:
            self._cancelled = True
            handle = self._handle
        if handle is not None:
            handle.cancel()

    def _current_handle(self) -> EncodeHandle | None:
        with self._lock:
            return self._handle
