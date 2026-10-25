# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Wizard state shared by the assistant steps (no widgets)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from PySide6.QtCore import QObject, Signal

from reduvid.core.config import Config, Container
from reduvid.core.plan import PlanOptions
from reduvid.core.probe import MediaInfo
from reduvid.core.queue import VIDEO_EXTENSIONS

DESTINATIONS = ("jellyfin", "modern", "archive")
QUALITIES = ("high", "balanced", "max_savings")
CONTAINERS = ("mkv", "mp4")


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
        self._container: Container = config.container
        self._output_dir: Path | None = config.output_dir
        self._replace_original = False
        self._reduce_4k = True
        self._audio_selected: frozenset[str] | None = None
        self._subtitle_selected: frozenset[str] | None = None
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

    @property
    def container(self) -> str:
        return self._container

    @property
    def output_dir(self) -> Path | None:
        return self._output_dir

    @property
    def replace_original(self) -> bool:
        return self._replace_original

    @property
    def reduce_4k(self) -> bool:
        return self._reduce_4k

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

    def set_container(self, container: str) -> None:
        if container not in CONTAINERS:
            raise ValueError(f"Unknown container: {container}")
        if container != self._container:
            self._container = cast(Container, container)
            self.changed.emit()

    def set_output_dir(self, output_dir: Path | None) -> None:
        resolved = output_dir.expanduser() if output_dir is not None else None
        if resolved != self._output_dir:
            self._output_dir = resolved
            self.changed.emit()

    def set_replace_original(self, replace: bool) -> None:
        if replace != self._replace_original:
            self._replace_original = replace
            self.changed.emit()

    def set_reduce_4k(self, reduce: bool) -> None:
        if reduce != self._reduce_4k:
            self._reduce_4k = reduce
            self.changed.emit()

    def available_audio_languages(self) -> tuple[str, ...]:
        return _languages(self._videos, "audio")

    def available_subtitle_languages(self) -> tuple[str, ...]:
        return _languages(self._videos, "subtitle")

    def selected_audio_languages(self) -> frozenset[str]:
        available = frozenset(self.available_audio_languages())
        if self._audio_selected is None:
            return available
        return frozenset(code for code in self._audio_selected if code in available)

    def selected_subtitle_languages(self) -> frozenset[str]:
        available = frozenset(self.available_subtitle_languages())
        if self._subtitle_selected is None:
            return available
        return frozenset(code for code in self._subtitle_selected if code in available)

    def set_audio_languages(self, codes: Iterable[str]) -> None:
        self._set_languages("_audio_selected", codes, "audio")

    def set_subtitle_languages(self, codes: Iterable[str]) -> None:
        self._set_languages("_subtitle_selected", codes, "subtitle")

    def has_4k(self) -> bool:
        return any(
            entry.media is not None
            and any(
                stream.width > 1920 or stream.height > 1080 for stream in entry.media.video_streams
            )
            for entry in self._videos
        )

    def options(self) -> PlanOptions:
        audio_available = frozenset(self.available_audio_languages())
        subtitle_available = frozenset(self.available_subtitle_languages())
        audio_selected = self.selected_audio_languages()
        subtitle_selected = self.selected_subtitle_languages()
        audio = None if audio_selected == audio_available else frozenset(audio_selected)
        subtitles = (
            None if subtitle_selected == subtitle_available else frozenset(subtitle_selected)
        )
        max_height = 2160 if self._keep_4k() else None
        return PlanOptions(
            destination=self._destination,
            quality=self._quality,
            container=self._container,
            max_height=max_height,
            audio_languages=audio,
            subtitle_languages=subtitles,
        )

    def _keep_4k(self) -> bool:
        return not self._reduce_4k and self._destination == "jellyfin" and self.has_4k()

    def _set_languages(self, attribute: str, codes: Iterable[str], kind: str) -> None:
        normalized = frozenset(code.strip().lower() for code in codes if code.strip())
        available = frozenset(_languages(self._videos, kind))
        current = getattr(self, attribute)
        new_value: frozenset[str] | None
        new_value = None if normalized == available else normalized
        if new_value != current:
            setattr(self, attribute, new_value)
            self.changed.emit()

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


def _languages(videos: list[VideoEntry], kind: str) -> tuple[str, ...]:
    # Imported lazily to avoid a cycle: wizard_logic also reads VideoEntry.
    from reduvid.gui.wizard_logic import collect_languages

    return collect_languages(videos, "audio" if kind == "audio" else "subtitle")
