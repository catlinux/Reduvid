# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Main window skeleton: top bar, step list, content and queue panels."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QCloseEvent, QResizeEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from reduvid.core.config import Config
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.pipeline import FileProcessor
from reduvid.core.plan import PlanOptions
from reduvid.core.report import QueueReport
from reduvid.gui.preferences import PreferencesDialog
from reduvid.gui.queue_panel import QueuePanel
from reduvid.gui.theme.manager import ThemeManager
from reduvid.gui.workers import QueueWorker, start_worker_thread
from reduvid.i18n import _

STEP_LIST_WIDTH = 180
QUEUE_PANEL_WIDTH = 300
COMPACT_WIDTH = 900


def _step_titles() -> tuple[str, ...]:
    return (
        _("Videos"),
        _("Where to watch"),
        _("Quality"),
        _("What to keep"),
        _("Destination"),
        _("Summary"),
    )


class MainWindow(QMainWindow):
    """Application shell with the three-column layout of the mockups."""

    def __init__(
        self,
        config: Config,
        ffmpeg_info: FFmpegInfo,
        theme_manager: ThemeManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("mainWindow")
        self.setWindowTitle(_("Reduvid"))
        self._config = config
        self._ffmpeg_info = ffmpeg_info
        self._theme_manager = theme_manager
        self._ui_mode = config.ui_mode
        self._compact = False

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.wizard_button = self._build_mode_button(_("Wizard"), "wizardButton", 0)
        self.advanced_button = self._build_mode_button(_("Advanced"), "advancedButton", 1)
        self.preferences_button = QPushButton(_("Preferences"), self)
        self.preferences_button.setObjectName("preferencesButton")
        self.preferences_button.setAccessibleName(_("Preferences"))
        self.preferences_button.clicked.connect(self.open_preferences)

        self.step_list = self._build_step_list()
        self.content = self._build_content()
        self.queue_panel = QueuePanel(self)
        self.queue_panel.setMinimumWidth(QUEUE_PANEL_WIDTH)
        self.queue_worker: QueueWorker | None = None
        self.queue_thread: QThread | None = None
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.setObjectName("bodySplitter")
        self.splitter.setAccessibleName(_("Main panels"))
        self.splitter.addWidget(self.step_list)
        self.splitter.addWidget(self.content)
        self.splitter.addWidget(self.queue_panel)
        self.splitter.setSizes([STEP_LIST_WIDTH, 640, QUEUE_PANEL_WIDTH])

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_top_bar())
        layout.addWidget(self.splitter, 1)
        self.setCentralWidget(central)
        self.resize(1100, 720)
        self.set_ui_mode(config.ui_mode)

    @property
    def ui_mode(self) -> str:
        return self._ui_mode

    def set_ui_mode(self, mode: str) -> None:
        """Reflect ``wizard`` or ``advanced`` in the exclusive toggle."""
        self._ui_mode = "advanced" if mode == "advanced" else "wizard"
        self.wizard_button.setChecked(self._ui_mode == "wizard")
        self.advanced_button.setChecked(self._ui_mode == "advanced")

    def open_preferences(self) -> None:
        dialog = PreferencesDialog(self._config, self._theme_manager, self)
        if dialog.exec():
            self._config = dialog.config

    def start_queue(
        self,
        paths: Sequence[Path],
        options: PlanOptions,
        *,
        output_dir: Path | None = None,
        threads: int | None = None,
        replace_original: bool = False,
    ) -> QueueWorker:
        """Start converting *paths* in a worker thread and return its worker."""
        if self.has_running_queue():
            raise RuntimeError(_("A conversion is already running."))
        processor = FileProcessor(
            self._ffmpeg_info,
            options,
            output_dir=output_dir,
            threads=threads,
            replace_original=replace_original,
        )
        worker = QueueWorker(processor, self._ffmpeg_info.ffprobe_path)
        worker.add_files(paths)
        worker.finished.connect(self._on_queue_finished)
        self.queue_panel.connect_worker(worker)
        self.queue_worker = worker
        self.queue_thread = start_worker_thread(worker)
        return worker

    def _on_queue_finished(self, _report: QueueReport) -> None:
        # The worker and thread schedule their own deletion after finishing.
        self.queue_worker = None
        self.queue_thread = None

    def has_running_queue(self) -> bool:
        return self.queue_thread is not None and self.queue_thread.isRunning()

    def cancel_queue(self) -> None:
        """Cancel the running conversion and wait for its thread to stop."""
        if self.queue_worker is not None:
            self.queue_worker.cancel()
        if self.queue_thread is not None:
            self.queue_thread.quit()
            self.queue_thread.wait(5000)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.has_running_queue() and not self._confirm_quit():
            event.ignore()
            return
        if self.has_running_queue():
            self.cancel_queue()
        super().closeEvent(event)

    def _confirm_quit(self) -> bool:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(_("Conversion in progress"))
        box.setText(_("A conversion is still running."))
        box.setInformativeText(_("If you quit now, the conversion will be cancelled."))
        quit_button = box.addButton(
            _("Cancel conversion and quit"), QMessageBox.ButtonRole.DestructiveRole
        )
        box.addButton(_("Keep converting"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        return box.clickedButton() is quit_button

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        compact = event.size().width() < COMPACT_WIDTH
        if compact == self._compact:
            return
        self._compact = compact
        self.splitter.setOrientation(
            Qt.Orientation.Vertical if compact else Qt.Orientation.Horizontal
        )
        if not compact:
            self.splitter.setSizes([STEP_LIST_WIDTH, 640, QUEUE_PANEL_WIDTH])

    def _build_mode_button(self, text: str, name: str, button_id: int) -> QPushButton:
        button = QPushButton(text, self)
        button.setObjectName(name)
        button.setAccessibleName(text)
        button.setCheckable(True)
        self.mode_group.addButton(button, button_id)
        return button

    def _build_top_bar(self) -> QWidget:
        bar = QWidget(self)
        bar.setObjectName("topBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(18, 12, 18, 12)
        row.setSpacing(12)

        brand = QLabel(_("Reduvid"), bar)
        brand.setObjectName("brand")
        brand.setProperty("role", "heading")
        brand.setAccessibleName(_("Reduvid"))
        row.addWidget(brand)
        row.addStretch(1)
        row.addWidget(self.wizard_button)
        row.addWidget(self.advanced_button)
        row.addWidget(self.preferences_button)
        self.mode_group.idClicked.connect(self._on_mode_clicked)
        return bar

    def _on_mode_clicked(self, button_id: int) -> None:
        self.set_ui_mode("advanced" if button_id == 1 else "wizard")

    def _build_step_list(self) -> QWidget:
        panel = QWidget(self)
        panel.setObjectName("stepList")
        panel.setAccessibleName(_("Wizard steps"))
        panel.setMinimumWidth(STEP_LIST_WIDTH)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 20, 14, 20)
        layout.setSpacing(6)

        title = QLabel(_("Steps"), panel)
        title.setProperty("role", "kicker")
        layout.addWidget(title)
        for number, step_title in enumerate(_step_titles(), start=1):
            label = QLabel(f"{number}. {step_title}", panel)
            label.setWordWrap(True)
            layout.addWidget(label)
        layout.addStretch(1)
        return panel

    def _build_content(self) -> QStackedWidget:
        stack = QStackedWidget(self)
        stack.setObjectName("content")
        stack.setAccessibleName(_("Step content"))
        for step_title in _step_titles():
            page = QWidget(stack)
            layout = QVBoxLayout(page)
            heading = QLabel(step_title, page)
            heading.setProperty("role", "heading")
            heading.setWordWrap(True)
            placeholder = QLabel(_("This step is not available yet."), page)
            placeholder.setProperty("role", "muted")
            placeholder.setWordWrap(True)
            layout.addWidget(heading)
            layout.addWidget(placeholder)
            layout.addStretch(1)
            stack.addWidget(page)
        return stack
