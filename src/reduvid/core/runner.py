# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Run and control an FFmpeg encode process."""

from __future__ import annotations

import subprocess
import sys
import threading
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import psutil  # type: ignore[import-untyped]

from reduvid.core.process import hidden_window_kwargs

EncodeErrorCode = Literal[
    "no_space", "corrupt_input", "missing_codec", "permission_denied", "unknown"
]


@dataclass(frozen=True)
class ProgressEvent:
    """Progress values parsed from one FFmpeg ``-progress`` block."""

    tiempo_procesado_segundos: float
    velocidad: float
    tiempo_restante_segundos: float | None
    estado: Literal["continue", "end"]
    total_size: int | None = None
    bitrate: str | None = None


@dataclass(frozen=True)
class EncodeResult:
    """Final status of an FFmpeg process."""

    returncode: int
    cancelled: bool
    last_progress: ProgressEvent | None


class EncodeError(RuntimeError):
    """FFmpeg failed with a user-facing, translatable error code."""

    def __init__(self, code: EncodeErrorCode, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"FFmpeg failed ({code}): {detail}")


class EncodeHandle:
    """A started encode with blocking ``run`` and concurrent control methods.

    ``command`` contains arguments from ``build_command``; ``ffmpeg_path`` supplies
    the executable. Progress callbacks run on the stdout reader thread and should
    return promptly.
    """

    _TERMINATE_TIMEOUT_SECONDS = 5
    _READER_JOIN_TIMEOUT_SECONDS = 5

    def __init__(
        self,
        command: list[str],
        output_duration_seconds: float | None,
        temp_output_path: Path,
        on_progress: Callable[[ProgressEvent], None] | None = None,
        threads: int | None = None,
        ffmpeg_path: str | Path = "ffmpeg",
    ) -> None:
        if threads is not None and threads < 1:
            raise ValueError("threads must be positive")

        self.temp_output_path = temp_output_path
        self.output_duration_seconds = output_duration_seconds
        self.on_progress = on_progress
        self.arguments = self._build_arguments(command, ffmpeg_path, threads)
        self._control_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._cancelled = False
        self._paused = False
        self._run_called = False
        self._callback_error: BaseException | None = None
        self._last_progress: ProgressEvent | None = None
        self._stderr = ""

        try:
            self._process = subprocess.Popen(  # noqa: S603
                self.arguments,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                **hidden_window_kwargs(),
            )
        except OSError as error:
            self._remove_temp_output()
            raise EncodeError("unknown", str(error)) from error

        self._lower_priority()
        self._stdout_thread = threading.Thread(target=self._read_progress, daemon=True)
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()

    @staticmethod
    def _build_arguments(
        command: list[str], ffmpeg_path: str | Path, threads: int | None
    ) -> list[str]:
        arguments = [
            str(ffmpeg_path),
            "-nostdin",
            "-hide_banner",
            "-progress",
            "pipe:1",
            "-nostats",
            *command,
        ]
        if threads is not None and "-threads" not in command:
            insert_at = len(arguments)
            if command:
                insert_at -= 1
            arguments[insert_at:insert_at] = ["-threads", str(threads)]
        return arguments

    def _lower_priority(self) -> None:
        try:
            process = psutil.Process(self._process.pid)
            if sys.platform == "win32":
                process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
            elif sys.platform.startswith("linux"):
                process.nice(10)
        except (OSError, psutil.Error):
            pass

    def _read_progress(self) -> None:
        if self._process.stdout is None:
            return

        block: dict[str, str] = {}
        for line in self._process.stdout:
            key, separator, value = line.strip().partition("=")
            if not separator:
                continue
            block[key] = value
            if key != "progress" or value not in ("continue", "end"):
                continue

            event = self._parse_progress(block)
            with self._state_lock:
                self._last_progress = event
            if self.on_progress is not None:
                try:
                    self.on_progress(event)
                except BaseException as error:
                    with self._state_lock:
                        if self._callback_error is None:
                            self._callback_error = error
            block = {}

    def _parse_progress(self, block: dict[str, str]) -> ProgressEvent:
        try:
            processed = int(block.get("out_time_us", "0")) / 1_000_000
        except ValueError:
            processed = 0.0
        # While +faststart moves the index FFmpeg reports N/A or an earlier time; never go back.
        with self._state_lock:
            if self._last_progress is not None:
                processed = max(processed, self._last_progress.tiempo_procesado_segundos)

        raw_speed = block.get("speed", "N/A").removesuffix("x")
        try:
            speed = float(raw_speed) if raw_speed != "N/A" else 0.0
        except ValueError:
            speed = 0.0

        remaining = None
        if self.output_duration_seconds is not None and speed > 0:
            remaining = (self.output_duration_seconds - processed) / speed

        try:
            total_size = int(block["total_size"])
        except (KeyError, ValueError):
            total_size = None

        return ProgressEvent(
            tiempo_procesado_segundos=processed,
            velocidad=speed,
            tiempo_restante_segundos=remaining,
            estado=cast(Literal["continue", "end"], block["progress"]),
            total_size=total_size,
            bitrate=block.get("bitrate"),
        )

    def _read_stderr(self) -> None:
        if self._process.stderr is None:
            return
        parts: list[str] = []
        while chunk := self._process.stderr.read(4096):
            parts.append(chunk)
        self._stderr = "".join(parts)[-65536:]

    def _remove_temp_output(self) -> None:
        self.temp_output_path.unlink(missing_ok=True)

    def pause(self) -> None:
        """Suspend the FFmpeg process while it is running."""
        with self._control_lock:
            if self._cancelled or self._process.poll() is not None or self._paused:
                return
            psutil.Process(self._process.pid).suspend()
            self._paused = True

    def resume(self) -> None:
        """Resume a process previously suspended with ``pause``."""
        with self._control_lock:
            if self._cancelled or self._process.poll() is not None or not self._paused:
                return
            psutil.Process(self._process.pid).resume()
            self._paused = False

    def cancel(self) -> None:
        """Stop FFmpeg, escalating from terminate to kill after five seconds."""
        with self._control_lock:
            if self._cancelled:
                return
            self._cancelled = True
            if self._process.poll() is None:
                with suppress(OSError):
                    self._process.terminate()

        try:
            self._process.wait(timeout=self._TERMINATE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            # The five-second grace period keeps cancellation responsive to the UI.
            with suppress(OSError):
                self._process.kill()
            with suppress(subprocess.TimeoutExpired):
                self._process.wait(timeout=self._TERMINATE_TIMEOUT_SECONDS)
        finally:
            self._remove_temp_output()

    def run(self) -> EncodeResult:
        """Wait for completion and return the result or raise ``EncodeError``."""
        with self._state_lock:
            if self._run_called:
                raise RuntimeError("EncodeHandle.run() can only be called once")
            self._run_called = True

        successful = False
        try:
            returncode = self._process.wait()
            self._stdout_thread.join(self._READER_JOIN_TIMEOUT_SECONDS)
            self._stderr_thread.join(self._READER_JOIN_TIMEOUT_SECONDS)
            if self._stdout_thread.is_alive() or self._stderr_thread.is_alive():
                raise RuntimeError("FFmpeg output streams did not close")

            with self._state_lock:
                callback_error = self._callback_error
                cancelled = self._cancelled
                last_progress = self._last_progress

            if callback_error is not None:
                raise callback_error
            if cancelled:
                successful = True
                return EncodeResult(returncode, True, last_progress)
            if returncode != 0:
                detail = self._stderr.strip() or f"FFmpeg exited with status {returncode}"
                raise EncodeError(_classify_error(detail), detail)

            successful = True
            return EncodeResult(returncode, False, last_progress)
        finally:
            if not successful:
                self._remove_temp_output()


def _classify_error(detail: str) -> EncodeErrorCode:
    """Classify common FFmpeg failures heuristically from stderr text."""
    lowered = detail.casefold()
    if "no space left on device" in lowered:
        return "no_space"
    if "permission denied" in lowered:
        return "permission_denied"
    if any(
        pattern in lowered
        for pattern in (
            "invalid data found when processing input",
            "moov atom not found",
            "could not find codec parameters",
        )
    ):
        return "corrupt_input"
    if "unknown encoder" in lowered or "encoder not found" in lowered:
        return "missing_codec"
    return "unknown"
