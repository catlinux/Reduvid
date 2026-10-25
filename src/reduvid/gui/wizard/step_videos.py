# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Step 1: choose the videos to convert."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from reduvid.core.probe import MediaInfo, probe_media
from reduvid.core.queue import VIDEO_EXTENSIONS
from reduvid.gui.wizard_state import WizardState
from reduvid.gui.workers import ProbeWorker, start_worker_thread
from reduvid.i18n import _
from reduvid.messages import error_text


class StepVideos(QWidget):
    """Add files or folders, probe them in the background and list the results."""

    def __init__(
        self,
        state: WizardState,
        ffprobe_path: Path,
        *,
        probe: Callable[[Path, Path], MediaInfo] = probe_media,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._ffprobe_path = ffprobe_path
        self._probe = probe
        self._threads: list[QThread] = []
        self._workers: list[ProbeWorker] = []
        self.setAcceptDrops(True)
        self._build_ui()
        state.changed.connect(self._refresh)
        self._refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        heading = QLabel(_("Videos"), self)
        heading.setProperty("role", "heading")
        heading.setWordWrap(True)
        lead = QLabel(
            _("Add the videos you want to shrink. You can also drop files or folders here."),
            self,
        )
        lead.setProperty("role", "muted")
        lead.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(lead)

        buttons = QHBoxLayout()
        self.add_files_button = QPushButton(_("Add videos…"), self)
        self.add_files_button.setMinimumWidth(0)
        self.add_files_button.setObjectName("addVideosButton")
        self.add_files_button.setAccessibleName(_("Add videos…"))
        self.add_files_button.clicked.connect(self._choose_files)
        self.add_folder_button = QPushButton(_("Add folder…"), self)
        self.add_folder_button.setMinimumWidth(0)
        self.add_folder_button.setObjectName("addFolderButton")
        self.add_folder_button.setAccessibleName(_("Add folder…"))
        self.add_folder_button.clicked.connect(self._choose_folder)
        self.include_subfolders = QCheckBox(_("Include subfolders"), self)
        self.include_subfolders.setObjectName("includeSubfolders")
        self.include_subfolders.setAccessibleName(_("Include subfolders"))
        buttons.addWidget(self.add_files_button)
        buttons.addWidget(self.add_folder_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addWidget(self.include_subfolders)

        self.video_list = QListWidget(self)
        self.video_list.setObjectName("videoList")
        self.video_list.setAccessibleName(_("Added videos"))
        self.video_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.video_list, 1)

        self.empty_label = QLabel(_("No videos added yet."), self)
        self.empty_label.setProperty("role", "muted")
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        footer = QHBoxLayout()
        self.remove_button = QPushButton(_("Remove selected"), self)
        self.remove_button.setMinimumWidth(0)
        self.remove_button.setObjectName("removeVideosButton")
        self.remove_button.setAccessibleName(_("Remove selected"))
        self.remove_button.clicked.connect(self.remove_selected)
        footer.addWidget(self.remove_button)
        footer.addStretch(1)
        layout.addLayout(footer)
        QWidget.setTabOrder(self.add_files_button, self.add_folder_button)
        QWidget.setTabOrder(self.add_folder_button, self.include_subfolders)
        QWidget.setTabOrder(self.include_subfolders, self.video_list)
        QWidget.setTabOrder(self.video_list, self.remove_button)

    @property
    def threads(self) -> tuple[QThread, ...]:
        return tuple(self._threads)

    def add_paths(self, paths: Iterable[Path], *, recursive: bool | None = None) -> None:
        include = self.include_subfolders.isChecked() if recursive is None else recursive
        added = self._state.add_paths(paths, recursive=include)
        if added:
            self._start_probe(added)

    def remove_selected(self) -> None:
        paths = [
            Path(str(item.data(Qt.ItemDataRole.UserRole)))
            for item in self.video_list.selectedItems()
        ]
        if paths:
            self._state.remove_paths(paths)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.add_paths(paths)
            event.acceptProposedAction()

    def _choose_files(self) -> None:
        patterns = " ".join(f"*{extension}" for extension in sorted(VIDEO_EXTENSIONS))
        filters = f"{_('Video files')} ({patterns});;{_('All files (*)')}"
        filenames, _selected = QFileDialog.getOpenFileNames(self, _("Choose videos"), "", filters)
        if filenames:
            self.add_paths([Path(filename) for filename in filenames])

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, _("Choose a folder"))
        if folder:
            self.add_paths([Path(folder)])

    def _start_probe(self, paths: list[Path]) -> None:
        worker = ProbeWorker(paths, self._ffprobe_path, probe=self._probe)
        worker.probed.connect(self._state.set_media)
        worker.failed.connect(self._state.set_error)
        worker.finished.connect(self._on_probe_finished)
        self._workers.append(worker)
        thread = start_worker_thread(worker)
        self._threads.append(thread)
        thread.finished.connect(self._on_probe_thread_finished)

    def _on_probe_finished(self) -> None:
        sender = self.sender()
        if isinstance(sender, ProbeWorker) and sender in self._workers:
            self._workers.remove(sender)

    def _on_probe_thread_finished(self) -> None:
        sender = self.sender()
        if isinstance(sender, QThread) and sender in self._threads:
            self._threads.remove(sender)

    def _refresh(self) -> None:
        self.video_list.clear()
        for entry in self._state.videos:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, str(entry.path))
            if entry.media is not None:
                details = _format_duration(entry.media.duration)
                item.setText(
                    _("{name} · {duration} · {state}").format(
                        name=entry.path.name, duration=details, state=_("Ready")
                    )
                )
            elif entry.error is not None:
                item.setText(
                    _("{name} · {state}").format(
                        name=entry.path.name, state=error_text("probe_failed")
                    )
                )
                item.setToolTip(entry.error)
            else:
                item.setText(
                    _("{name} · {state}").format(name=entry.path.name, state=_("Analysing…"))
                )
            self.video_list.addItem(item)
        self.empty_label.setVisible(not self._state.videos)
        self.remove_button.setEnabled(bool(self._state.videos))


def _format_duration(duration: float) -> str:
    seconds = int(duration) if duration > 0 else 0
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02}:{seconds:02}"
    return f"{minutes}:{seconds:02}"
