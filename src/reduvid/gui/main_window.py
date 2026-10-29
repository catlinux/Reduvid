# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Main window skeleton: top bar, step list, content and queue panels."""

from __future__ import annotations

import urllib.request
from collections.abc import Callable, Iterable, Sequence
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, QTimer, Slot
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

from reduvid import __version__
from reduvid.core.config import Config, UiMode, save_config
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.pipeline import FileProcessor
from reduvid.core.plan import PlanOptions
from reduvid.core.report import QueueReport
from reduvid.gui.advanced_page import AdvancedPage
from reduvid.gui.preferences import PreferencesDialog
from reduvid.gui.queue_panel import QueuePanel
from reduvid.gui.theme.manager import ThemeManager
from reduvid.gui.update_notice import UpdateNotice
from reduvid.gui.widgets.step_list import StepList
from reduvid.gui.widgets.wizard_nav import WizardNav
from reduvid.gui.wizard.step_destination import StepDestination
from reduvid.gui.wizard.step_keep import StepKeep
from reduvid.gui.wizard.step_quality import StepQuality
from reduvid.gui.wizard.step_summary import StepSummary
from reduvid.gui.wizard.step_target import StepTarget
from reduvid.gui.wizard.step_videos import StepVideos
from reduvid.gui.wizard_state import WizardState
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
        self.setWindowTitle(_("Reduvid {version}").format(version=__version__))
        self._config = config
        self._ffmpeg_info = ffmpeg_info
        self._theme_manager = theme_manager
        self._ui_mode: UiMode = config.ui_mode
        self._compact = False

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.wizard_button = self._build_mode_button(_("&Wizard"), "wizardButton", 0)
        self.advanced_button = self._build_mode_button(_("&Advanced"), "advancedButton", 1)
        self.preferences_button = QPushButton(_("&Preferences"), self)
        self.preferences_button.setObjectName("preferencesButton")
        self.preferences_button.setAccessibleName(_("&Preferences"))
        self.preferences_button.clicked.connect(self.open_preferences)

        self.step_list = StepList(_step_titles(), self)
        self.step_list.setMinimumWidth(STEP_LIST_WIDTH)
        self.step_list.selected.connect(self.set_current_step)
        self.wizard_state = WizardState(config, self)
        self.content = self._build_content()
        self.step_summary.start_requested.connect(self._start_from_summary)
        self.wizard_nav = WizardNav(self)
        self.wizard_nav.back_clicked.connect(self._go_back)
        self.wizard_nav.next_clicked.connect(self._go_next)
        self._current_step = 0
        self.advanced_page = AdvancedPage(self.wizard_state, self._ffmpeg_info, self)
        self.advanced_page.summary.start_requested.connect(self._start_from_summary)
        self.wizard_panel = self._build_content_panel()
        self.center_stack = QStackedWidget(self)
        self.center_stack.setObjectName("centerStack")
        self.center_stack.addWidget(self.wizard_panel)
        self.center_stack.addWidget(self.advanced_page)
        self.queue_panel = QueuePanel(self)
        self.queue_panel.setMinimumWidth(QUEUE_PANEL_WIDTH)
        self.queue_worker: QueueWorker | None = None
        self.queue_thread: QThread | None = None
        self.update_notice = UpdateNotice(self._config, self)
        self.update_notice.config_changed.connect(self._on_update_config_changed)
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.setObjectName("bodySplitter")
        self.splitter.setAccessibleName(_("Main panels"))
        self.splitter.addWidget(self.step_list)
        self.splitter.addWidget(self.center_stack)
        self.splitter.addWidget(self.queue_panel)
        self.splitter.setSizes([STEP_LIST_WIDTH, 640, QUEUE_PANEL_WIDTH])

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_top_bar())
        layout.addWidget(self.update_notice)
        layout.addWidget(self.splitter, 1)
        self.setCentralWidget(central)
        QWidget.setTabOrder(self.wizard_button, self.advanced_button)
        QWidget.setTabOrder(self.advanced_button, self.preferences_button)
        QWidget.setTabOrder(self.preferences_button, self.step_list)
        self.resize(self._initial_size())
        self.set_ui_mode(config.ui_mode, save=False)
        self.wizard_state.changed.connect(self._update_navigation)
        self.set_current_step(0)

    @property
    def current_step(self) -> int:
        return self._current_step

    def set_current_step(self, index: int) -> None:
        if not 0 <= index < self.content.count():
            raise IndexError(index)
        self._current_step = index
        self.step_list.set_current(index)
        self.content.setCurrentIndex(index)
        refresh = getattr(self.content.widget(index), "refresh", None)
        if callable(refresh):
            refresh()
        self._update_navigation()

    def _go_back(self) -> None:
        if self._current_step > 0:
            self.set_current_step(self._current_step - 1)

    def _go_next(self) -> None:
        if self._current_step < self.content.count() - 1:
            self.set_current_step(self._current_step + 1)

    def _update_navigation(self) -> None:
        titles = _step_titles()
        index = self._current_step
        self.wizard_nav.set_back_enabled(index > 0)
        if index >= len(titles) - 1:
            self.wizard_nav.set_next_text(None)
            self.wizard_nav.set_next_enabled(False)
            return
        self.wizard_nav.set_next_text(titles[index + 1])
        self.wizard_nav.set_next_enabled(index != 0 or self.wizard_state.ready)

    @property
    def ui_mode(self) -> str:
        return self._ui_mode

    def set_ui_mode(self, mode: str, *, save: bool = True) -> None:
        """Switch between the assistant and the advanced page, keeping the state."""
        if self.has_running_queue():
            self._sync_mode_buttons()
            return
        normalized: UiMode = "advanced" if mode == "advanced" else "wizard"
        changed = normalized != self._ui_mode
        self._ui_mode = normalized
        self._sync_mode_buttons()
        advanced = self._ui_mode == "advanced"
        self.step_list.setVisible(not advanced)
        self.center_stack.setCurrentWidget(self.advanced_page if advanced else self.wizard_panel)
        if advanced:
            self.advanced_page.refresh()
        if save and changed:
            self._config = replace(self._config, ui_mode=self._ui_mode)
            save_config(self._config)

    def _sync_mode_buttons(self) -> None:
        self.wizard_button.setChecked(self._ui_mode == "wizard")
        self.advanced_button.setChecked(self._ui_mode == "advanced")

    def set_mode_switch_enabled(self, enabled: bool) -> None:
        self.wizard_button.setEnabled(enabled)
        self.advanced_button.setEnabled(enabled)

    def _active_summary(self) -> StepSummary:
        if self._ui_mode == "advanced":
            return self.advanced_page.summary
        return self.step_summary

    def open_preferences(self) -> None:
        previous_updates = self._config.check_updates
        dialog = PreferencesDialog(self._config, self._theme_manager, self)
        if dialog.exec():
            self._config = dialog.config
            self.wizard_state.set_hw_decode(self._config.hw_decode)
            self.update_notice.set_config(self._config)
            if self._config.check_updates and not previous_updates:
                self.update_notice.check_now()

    @Slot(object)
    def _on_update_config_changed(self, config: object) -> None:
        if isinstance(config, Config):
            self._config = config

    def start_update_checks(
        self,
        *,
        opener: Callable[[urllib.request.Request, float], bytes] | None = None,
        state_dir: Path | None = None,
        download_dir: Path | None = None,
        opener_stream: Callable[[str], Iterable[bytes]] | None = None,
    ) -> None:
        """Start the update notice after the window and event loop exist."""
        QTimer.singleShot(
            0,
            lambda: self.update_notice.start(
                opener=opener,
                state_dir=state_dir,
                download_dir=download_dir,
                opener_stream=opener_stream,
            ),
        )

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
            hw_decode=self.wizard_state.hw_decode,
        )
        worker = QueueWorker(processor, self._ffmpeg_info.ffprobe_path)
        worker.add_files(paths)
        worker.finished.connect(self._on_queue_finished)
        self.queue_panel.connect_worker(worker)
        self.queue_worker = worker
        self.update_notice.set_queue_running(True)
        self.queue_thread = start_worker_thread(worker)
        return worker

    def _start_from_summary(self) -> None:
        if self.has_running_queue():
            return
        self._cancel_estimates()
        summary = self._active_summary()
        summary.resolve_blocking()
        paths = summary.remaining_paths()
        if not paths:
            return
        worker = self.start_queue(
            paths,
            self.wizard_state.options(),
            output_dir=self.wizard_state.output_dir,
            threads=self.wizard_state.threads,
            replace_original=self.wizard_state.replace_original,
        )
        worker.finished.connect(self._on_queue_report)
        summary.set_running(True)
        self.set_mode_switch_enabled(False)

    def _on_queue_report(self, report: QueueReport) -> None:
        summary = self._active_summary()
        summary.set_running(False)
        summary.show_report(report)
        self.set_mode_switch_enabled(True)

    def _on_queue_finished(self, _report: QueueReport) -> None:
        # The worker and thread schedule their own deletion after finishing.
        self.queue_worker = None
        self.queue_thread = None
        self.update_notice.set_queue_running(False)

    def has_running_queue(self) -> bool:
        return self.queue_thread is not None and self.queue_thread.isRunning()

    def cancel_queue(self) -> None:
        """Cancel the running conversion and wait for its thread to stop."""
        if self.queue_worker is not None:
            self.queue_worker.cancel()
        if self.queue_thread is not None:
            self.queue_thread.quit()
            self.queue_thread.wait(5000)

    def _cancel_estimates(self) -> None:
        self.step_quality.cancel_estimate()
        self.step_summary.cancel_estimate()
        self.advanced_page.summary.cancel_estimate()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.has_running_queue() and not self._confirm_quit():
            event.ignore()
            return
        if self.has_running_queue():
            self.cancel_queue()
        self.update_notice.prepare_close()
        self._cancel_estimates()
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

    def _initial_size(self) -> QSize:
        # Clamp to the available screen so high DPI scaling (e.g. 200%) does not
        # start the window larger than the desktop, which would leave the queue
        # panel cut off instead of falling back to the compact stacked layout.
        preferred = QSize(1100, 720)
        screen = self.screen()
        if screen is None:
            return preferred
        available = screen.availableSize()
        return QSize(
            min(preferred.width(), available.width()),
            min(preferred.height(), available.height()),
        )

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
        mode = "advanced" if button_id == 1 else "wizard"
        if self.has_running_queue():
            self._sync_mode_buttons()
            return
        self.set_ui_mode(mode)

    def _build_content_panel(self) -> QWidget:
        panel = QWidget(self)
        panel.setObjectName("contentPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 20, 16, 12)
        layout.setSpacing(12)
        layout.addWidget(self.content, 1)
        layout.addWidget(self.wizard_nav)
        return panel

    def _build_content(self) -> QStackedWidget:
        stack = QStackedWidget(self)
        stack.setObjectName("content")
        stack.setAccessibleName(_("Step content"))
        stack.addWidget(StepVideos(self.wizard_state, self._ffmpeg_info.ffprobe_path, parent=stack))
        stack.addWidget(StepTarget(self.wizard_state, stack))
        self.step_quality = StepQuality(self.wizard_state, self._ffmpeg_info, stack)
        stack.addWidget(self.step_quality)
        self.step_keep = StepKeep(self.wizard_state, self._ffmpeg_info, stack)
        stack.addWidget(self.step_keep)
        self.step_destination = StepDestination(self.wizard_state, stack)
        stack.addWidget(self.step_destination)
        self.step_summary = StepSummary(self.wizard_state, self._ffmpeg_info, stack)
        stack.addWidget(self.step_summary)
        return stack
