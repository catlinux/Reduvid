# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Wizard state shared by the assistant steps (no widgets)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from reduvid.core.config import Config
from reduvid.core.plan import PlanOptions
from reduvid.core.probe import MediaInfo
from reduvid.core.queue import VIDEO_EXTENSIONS

DESTINATIONS = ("jellyfin", "modern", "archive")
QUALITIES = ("high", "balanced", "max_savings")


@dataclass
class VideoEntry:
    """One path added to the wizard, with its probe result or error."""

    path: Path
    media: MediaInfo | None = None
    error: str | None = None

    @property
    def ready(self) -> bool:
        return self.media is not None


class WizardState(QObject):
    """Videos, destination and quality selected in the assistant."""

    changed = Signal()

    def __init__(self, config: Config, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._destination: str = config.destination
        self._quality: str = config.quality
        self._videos: list[VideoEntry] = []

    @property
    def videos(self) -> tuple[VideoEntry, ...]:
        return tuple(self._videos)

    @property
    def destination(self) -> str:
        return self._destination

    @property
    def quality(self) -> str:
        return self._quality

    @property
    def ready(self) -> bool:
        """Whether at least one video has been probed successfully."""
        return any(entry.ready for entry in self._videos)

    def set_destination(self, destination: str) -> None:
        if destination not in DESTINATIONS:
            raise ValueError(f"Unknown destination: {destination}")
        if destination != self._destination:
            self._destination = destination
            self.changed.emit()

    def set_quality(self, quality: str) -> None:
        if quality not in QUALITIES:
            raise ValueError(f"Unknown quality: {quality}")
        if quality != self._quality:
            self._quality = quality
            self.changed.emit()

    def options(self) -> PlanOptions:
        return PlanOptions(destination=self._destination, quality=self._quality)

    def add_paths(self, paths: Iterable[Path], *, recursive: bool = False) -> list[Path]:
        """Add video files, expanding folders; return the new absolute paths."""
        existing = {entry.path for entry in self._videos}
        added: list[Path] = []
        for raw_path in paths:
            try:
                path = raw_path.expanduser().resolve()
            except OSError:
                continue
            candidates: list[Path]
            if path.is_dir():
                walker = path.rglob("*") if recursive else path.iterdir()
                candidates = sorted(
                    (
                        item
                        for item in walker
                        if item.is_file() and item.suffix.casefold() in VIDEO_EXTENSIONS
                    ),
                    key=lambda item: str(item).casefold(),
                )
            elif path.is_file() and path.suffix.casefold() in VIDEO_EXTENSIONS:
                candidates = [path]
            else:
                continue
            for candidate in candidates:
                try:
                    resolved = candidate.resolve()
                except OSError:
                    continue
                if resolved in existing:
                    continue
                self._videos.append(VideoEntry(resolved))
                existing.add(resolved)
                added.append(resolved)
        if added:
            self.changed.emit()
        return added

    def remove_paths(self, paths: Iterable[Path]) -> None:
        wanted = {path.expanduser().resolve() for path in paths}
        remaining = [entry for entry in self._videos if entry.path not in wanted]
        if len(remaining) != len(self._videos):
            self._videos = remaining
            self.changed.emit()

    def set_media(self, path: Path, media: MediaInfo) -> None:
        entry = self._entry(path)
        if entry is not None:
            entry.media = media
            entry.error = None
            self.changed.emit()

    def set_error(self, path: Path, reason: str) -> None:
        entry = self._entry(path)
        if entry is not None:
            entry.media = None
            entry.error = reason
            self.changed.emit()

    def _entry(self, path: Path) -> VideoEntry | None:
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            return None
        return next((entry for entry in self._videos if entry.path == resolved), None)
