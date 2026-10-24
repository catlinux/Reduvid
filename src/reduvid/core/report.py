# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Pure aggregation of per-file conversion results."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from reduvid.core.plan import Warning

FileStatus = Literal["success", "failed", "skipped"]


@dataclass(frozen=True)
class FileReport:
    path: Path
    status: FileStatus
    original_size: int
    final_size: int | None = None
    warnings: tuple[Warning, ...] = ()
    reason: str | None = None

    @property
    def savings_bytes(self) -> int:
        return max(0, self.original_size - self.final_size) if self.final_size is not None else 0

    @property
    def savings_percent(self) -> float:
        if self.original_size <= 0:
            return 0.0
        return self.savings_bytes / self.original_size * 100


@dataclass(frozen=True)
class QueueReport:
    files: tuple[FileReport, ...]

    @property
    def original_size(self) -> int:
        return sum(item.original_size for item in self.files)

    @property
    def final_size(self) -> int:
        return sum(item.final_size or 0 for item in self.files if item.status == "success")

    @property
    def savings_bytes(self) -> int:
        return sum(item.savings_bytes for item in self.files)

    @property
    def savings_percent(self) -> float:
        return self.savings_bytes / self.original_size * 100 if self.original_size else 0.0

    @property
    def succeeded(self) -> int:
        return sum(item.status == "success" for item in self.files)

    @property
    def failed(self) -> int:
        return sum(item.status == "failed" for item in self.files)

    @property
    def skipped(self) -> int:
        return sum(item.status == "skipped" for item in self.files)


def build_file_report(
    path: Path,
    status: FileStatus,
    original_size: int,
    final_size: int | None = None,
    warnings: tuple[Warning, ...] = (),
    reason: str | None = None,
) -> FileReport:
    """Create a file report from already collected processing data."""
    if original_size < 0 or (final_size is not None and final_size < 0):
        raise ValueError("sizes must not be negative")
    if status != "success":
        final_size = None
    return FileReport(path, status, original_size, final_size, warnings, reason)


def build_queue_report(files: tuple[FileReport, ...] | list[FileReport]) -> QueueReport:
    """Aggregate file reports without performing any I/O."""
    return QueueReport(tuple(files))
