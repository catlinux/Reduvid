# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Non-intrusive update notice and first-run update explanation."""

from __future__ import annotations

import os
import shutil
import urllib.request
from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import replace
from pathlib import Path

import platformdirs
from PySide6.QtCore import QProcess, Qt, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from reduvid import __version__
from reduvid.core.config import Config, save_config
from reduvid.core.updates import (
    InstallKind,
    UpdateError,
    UpdateInfo,
    install_kind,
    launch_windows_installer,
    replace_appimage,
)
from reduvid.gui.workers import (
    UpdateCheckWorker,
    UpdateDownloadWorker,
    start_worker_thread,
)
from reduvid.i18n import _

_UPDATE_DOWNLOAD_DIR = "updates"


class UpdateIntroDialog(QDialog):
    """One-time explanation of the update check, with an opt-out."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.disabled = False
        self.setObjectName("updateIntroDialog")
        self.setWindowTitle(_("Update checks"))
        text = QLabel(
            _(
                "Reduvid can check the public GitHub releases at most once every 24 hours. "
                "It sends no identifiers or usage data, downloads only over HTTPS and "
                "verifies the SHA256."
            ),
            self,
        )
        text.setWordWrap(True)
        self.accept_button = QPushButton(_("Got it"), self)
        self.accept_button.setObjectName("updateIntroAccept")
        self.accept_button.setAccessibleName(_("Got it"))
        self.accept_button.clicked.connect(self.accept)
        self.disable_button = QPushButton(_("Turn off"), self)
        self.disable_button.setObjectName("updateIntroDisable")
        self.disable_button.setAccessibleName(_("Turn off"))
        self.disable_button.clicked.connect(self._disable)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.accept_button)
        buttons.addWidget(self.disable_button)
        layout = QVBoxLayout(self)
        layout.addWidget(text)
        layout.addLayout(buttons)

    def _disable(self) -> None:
        self.disabled = True
        self.accept()


class UpdateNotice(QWidget):
    """A non-modal banner for a newer release and its download progress."""

    config_changed = Signal(object)

    def __init__(
        self,
        config: Config,
        parent: QWidget | None = None,
        *,
        opener: Callable[[urllib.request.Request, float], bytes] | None = None,
        state_dir: Path | None = None,
        download_dir: Path | None = None,
        opener_stream: Callable[[str], Iterable[bytes]] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("updateNotice")
        self.setAccessibleName(_("Update available"))
        self._config = config
        self._opener = opener
        self._state_dir = state_dir
        self._download_dir = (
            download_dir
            if download_dir is not None
            else Path(platformdirs.user_cache_dir("reduvid")) / _UPDATE_DOWNLOAD_DIR
        )
        self._opener_stream = opener_stream
        self._info: UpdateInfo | None = None
        self._kind: InstallKind = "source"
        self._queue_running = False
        self._started = False
        self._check_worker: UpdateCheckWorker | None = None
        self._check_thread: QThread | None = None
        self._download_worker: UpdateDownloadWorker | None = None
        self._download_thread: QThread | None = None
        self._download_path: Path | None = None
        self._install_on_close = False
        self._downloading = False
        self._download_cancelled = False
        self._build_ui()
        self.hide()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(6)

        row = QHBoxLayout()
        self.message_label = QLabel(self)
        self.message_label.setObjectName("updateMessage")
        self.message_label.setProperty("role", "heading")
        self.message_label.setWordWrap(True)
        row.addWidget(self.message_label, 1)

        self.whats_new_button = QPushButton(_("What's new"), self)
        self.whats_new_button.setObjectName("updateWhatsNew")
        self.whats_new_button.setAccessibleName(_("What's new"))
        self.whats_new_button.clicked.connect(self._toggle_notes)
        row.addWidget(self.whats_new_button)

        self.install_button = QPushButton(_("Install now"), self)
        self.install_button.setObjectName("updateInstall")
        self.install_button.setAccessibleName(_("Install now"))
        self.install_button.clicked.connect(self._install_now)
        row.addWidget(self.install_button)

        self.on_close_button = QPushButton(_("On close"), self)
        self.on_close_button.setObjectName("updateOnClose")
        self.on_close_button.setAccessibleName(_("On close"))
        self.on_close_button.clicked.connect(self._arm_install_on_close)
        row.addWidget(self.on_close_button)

        self.later_button = QPushButton(_("Not now"), self)
        self.later_button.setObjectName("updateLater")
        self.later_button.setAccessibleName(_("Not now"))
        self.later_button.clicked.connect(self._later)
        row.addWidget(self.later_button)

        self.page_button = QPushButton(_("Open page"), self)
        self.page_button.setObjectName("updatePage")
        self.page_button.setAccessibleName(_("Open page"))
        self.page_button.clicked.connect(self._open_page)
        row.addWidget(self.page_button)

        self.restart_button = QPushButton(_("Restart now"), self)
        self.restart_button.setObjectName("updateRestart")
        self.restart_button.setAccessibleName(_("Restart now"))
        self.restart_button.clicked.connect(self._restart)
        row.addWidget(self.restart_button)

        self.restart_later_button = QPushButton(_("Later"), self)
        self.restart_later_button.setObjectName("updateRestartLater")
        self.restart_later_button.setAccessibleName(_("Later"))
        self.restart_later_button.clicked.connect(self._later)
        row.addWidget(self.restart_later_button)
        layout.addLayout(row)

        self.notes_label = QLabel(self)
        self.notes_label.setObjectName("updateNotes")
        self.notes_label.setProperty("role", "muted")
        self.notes_label.setWordWrap(True)
        self.notes_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.notes_label)

        self.error_label = QLabel(self)
        self.error_label.setObjectName("updateError")
        self.error_label.setProperty("role", "muted")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setObjectName("updateProgress")
        self.progress_bar.setTextVisible(False)
        progress_row.addWidget(self.progress_bar, 1)
        self.cancel_button = QPushButton(_("Cancel"), self)
        self.cancel_button.setObjectName("updateCancel")
        self.cancel_button.setAccessibleName(_("Cancel"))
        self.cancel_button.clicked.connect(lambda: self.cancel_download())
        progress_row.addWidget(self.cancel_button)
        layout.addLayout(progress_row)

        self.notes_label.hide()
        self.error_label.hide()
        self.progress_bar.hide()
        self.cancel_button.hide()
        self.restart_button.hide()
        self.restart_later_button.hide()

    def set_config(self, config: Config) -> None:
        """Use *config* for later checks and notices."""
        self._config = config

    def start(
        self,
        *,
        opener: Callable[[urllib.request.Request, float], bytes] | None = None,
        state_dir: Path | None = None,
        download_dir: Path | None = None,
        opener_stream: Callable[[str], Iterable[bytes]] | None = None,
    ) -> None:
        """Resolve the first-run notice and start the background check."""
        if self._started:
            return
        self._started = True
        if opener is not None:
            self._opener = opener
        if state_dir is not None:
            self._state_dir = state_dir
        if download_dir is not None:
            self._download_dir = download_dir
        if opener_stream is not None:
            self._opener_stream = opener_stream

        if not self._config.updates_notice_seen:
            self._show_intro()
        if self._config.check_updates:
            self._start_check()

    def check_now(self) -> None:
        """Start a check if updates are enabled and the first-run notice is done."""
        if self._config.updates_notice_seen and self._config.check_updates:
            self._start_check()

    def _show_intro(self) -> None:
        dialog = UpdateIntroDialog(self.window())
        dialog.exec()
        disabled = bool(getattr(dialog, "disabled", False))
        config = replace(
            self._config,
            updates_notice_seen=True,
            check_updates=False if disabled else self._config.check_updates,
        )
        with suppress(OSError):
            save_config(config)
        self._config = config
        self.config_changed.emit(config)

    def _start_check(self) -> None:
        if self._check_worker is not None:
            return
        worker = UpdateCheckWorker(
            __version__,
            state_dir=self._state_dir,
            opener=self._opener,
        )
        worker.done.connect(self._check_done)
        worker.finished.connect(self._check_finished)
        self._check_worker = worker
        self._check_thread = start_worker_thread(worker)

    @Slot(object)
    def _check_done(self, info: object) -> None:
        if self._config.check_updates and isinstance(info, UpdateInfo):
            self.show_info(info)

    @Slot()
    def _check_finished(self) -> None:
        self._check_worker = None
        self._check_thread = None

    def show_info(self, info: UpdateInfo) -> None:
        """Show the banner for *info*, unless a conversion is running."""
        self._info = info
        self._kind = install_kind()
        self.message_label.setText(_("Reduvid {version} is available").format(version=info.version))
        self.notes_label.setText(info.notes or _("No release notes."))
        self.notes_label.hide()
        self.error_label.hide()
        self._show_actions()
        if not self._queue_is_running():
            self.show()

    def set_queue_running(self, running: bool) -> None:
        """Hide the banner during a conversion and show it again afterwards."""
        self._queue_running = running
        if running:
            self.hide()
        elif self._info is not None and not self._queue_is_running():
            self.show()

    def _queue_is_running(self) -> bool:
        if self._queue_running:
            return True
        checker = getattr(self.parent(), "has_running_queue", None)
        return bool(checker()) if callable(checker) else False

    def _show_actions(self) -> None:
        install = self._kind != "source"
        self.install_button.setVisible(install)
        self.on_close_button.setVisible(install)
        self.page_button.setVisible(not install)
        self.later_button.setVisible(True)
        self.whats_new_button.setVisible(True)
        self.restart_button.hide()
        self.restart_later_button.hide()
        self.progress_bar.hide()
        self.cancel_button.hide()

    def _toggle_notes(self) -> None:
        self.notes_label.setVisible(self.notes_label.isHidden())
        if self.notes_label.isVisible():
            self.message_label.setAccessibleDescription(self.notes_label.text())

    def _open_page(self) -> None:
        if self._info is not None and self._info.page_url:
            QDesktopServices.openUrl(QUrl(self._info.page_url))

    def _install_now(self) -> None:
        if self._queue_is_running() or self._downloading:
            return
        if self._kind == "source":
            self._open_page()
            return
        self._start_download(install_on_close=False)

    def _arm_install_on_close(self) -> None:
        if self._queue_is_running() or self._downloading or self._kind == "source":
            return
        self._start_download(install_on_close=True)

    def _start_download(self, *, install_on_close: bool) -> None:
        if self._info is None or self._download_worker is not None:
            return
        self._install_on_close = install_on_close
        self._download_path = None
        self._downloading = True
        self._download_cancelled = False
        self.error_label.hide()
        self.install_button.hide()
        self.on_close_button.hide()
        self.page_button.hide()
        self.later_button.hide()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.show()
        self.cancel_button.show()
        worker = UpdateDownloadWorker(
            self._info,
            self._kind,
            self._download_dir,
            opener_stream=self._opener_stream,
        )
        worker.progress.connect(self._download_progress)
        worker.done.connect(self._download_done)
        worker.failed.connect(self._download_failed)
        worker.finished.connect(self._download_finished)
        self._download_worker = worker
        self._download_thread = start_worker_thread(worker)

    @Slot(int, object)
    def _download_progress(self, downloaded: int, total: object) -> None:
        if isinstance(total, int) and total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(downloaded)
        else:
            self.progress_bar.setRange(0, 0)

    @Slot(object)
    def _download_done(self, path: object) -> None:
        if not isinstance(path, Path):
            self._download_failed("network", "Invalid download path")
            return
        if self._download_cancelled:
            with suppress(OSError):
                path.unlink(missing_ok=True)
            self.progress_bar.hide()
            self.cancel_button.hide()
            self._reset_actions()
            return
        self._downloading = False
        self._download_path = path
        self.progress_bar.hide()
        self.cancel_button.hide()
        if self._install_on_close or self._queue_is_running():
            if self._kind == "appimage" and not os.environ.get("APPIMAGE"):
                self._show_error("install_failed")
                self._reset_actions()
                return
            self._install_on_close = True
            self.later_button.show()
            self.message_label.setText(
                _("The update is ready and will be installed when Reduvid closes.")
            )
            return

        if self._kind == "windows_installer":
            try:
                launch_windows_installer(path)
            except (OSError, UpdateError) as error:
                self._show_error(getattr(error, "code", "install_failed"))
                self._reset_actions()
                return
            application = QApplication.instance()
            if application is not None:
                application.quit()
            return

        if self._kind == "appimage":
            current = os.environ.get("APPIMAGE")
            if not current:
                self._show_error("install_failed")
                self._reset_actions()
                return
            try:
                self._install_appimage(path, Path(current))
            except UpdateError as error:
                self._show_error(error.code)
                self._reset_actions()
                return
            self._install_on_close = False
            self.message_label.setText(_("The update is ready. Restart Reduvid to use it."))
            self.install_button.hide()
            self.on_close_button.hide()
            self.page_button.hide()
            self.later_button.hide()
            self.restart_button.show()
            self.restart_later_button.show()

    @Slot(str, str)
    def _download_failed(self, code: str, _detail: str) -> None:
        self._downloading = False
        self._download_path = None
        self._install_on_close = False
        self.progress_bar.hide()
        self.cancel_button.hide()
        if code != "cancelled" and not self._download_cancelled:
            self._show_error(code)
        self._reset_actions()

    @Slot()
    def _download_finished(self) -> None:
        self._download_worker = None
        self._download_thread = None

    def _show_error(self, code: str) -> None:
        messages = {
            "no_asset": _("This release does not include the file needed for this installation."),
            "no_checksum": _("The release has no checksum file, so the update was not installed."),
            "checksum_mismatch": _("The downloaded file is corrupt, so it was not installed."),
            "network": _("The update could not be downloaded. Check your connection."),
            "install_failed": _("The update could not be installed."),
        }
        self.error_label.setText(messages.get(code, _("The update could not be installed.")))
        self.error_label.show()

    def _reset_actions(self) -> None:
        self._downloading = False
        self._install_on_close = False
        self._download_path = None
        self.progress_bar.hide()
        self.cancel_button.hide()
        self._show_actions()

    def cancel_download(self, wait: bool = False) -> None:
        """Cancel an active download and remove its partial file."""
        self._download_cancelled = True
        if self._download_worker is not None:
            self._download_worker.cancel()
        if wait and self._download_thread is not None:
            wait_method = getattr(self._download_thread, "wait", None)
            if callable(wait_method):
                wait_method(5000)
        self._downloading = False
        self._install_on_close = False
        self._download_path = None
        self.progress_bar.hide()
        self.cancel_button.hide()
        self._show_actions()

    def prepare_close(self) -> None:
        """Cancel unfinished downloads or apply an update armed for closing."""
        if (
            self._download_path is None
            and self._download_thread is not None
            and getattr(self._download_thread, "isRunning", lambda: False)()
        ):
            self.cancel_download(wait=True)
            return
        if not self._install_on_close or self._download_path is None:
            return
        if self._queue_is_running():
            return
        path = self._download_path
        self._install_on_close = False
        try:
            if self._kind == "windows_installer":
                launch_windows_installer(path)
            elif self._kind == "appimage":
                current = os.environ.get("APPIMAGE")
                if current:
                    self._install_appimage(path, Path(current))
        except (OSError, UpdateError):
            pass

    @classmethod
    def _install_appimage(cls, path: Path, current: Path) -> None:
        """Replace *current* even when the cached file is on another tree."""
        try:
            replace_appimage(path, current)
        except UpdateError as error:
            if error.code != "install_failed" or path.parent == current.parent:
                raise
            replace_appimage(cls._stage_appimage(path, current), current)

    @staticmethod
    def _stage_appimage(path: Path, current: Path) -> Path:
        """Bring the cached AppImage into the current AppImage's folder."""
        staged = current.parent / path.name
        try:
            shutil.copy2(path, staged)
        except OSError as error:
            raise UpdateError("install_failed", str(error)) from error
        return staged

    def _restart(self) -> None:
        current = os.environ.get("APPIMAGE")
        if current:
            QProcess.startDetached(current, [])
        application = QApplication.instance()
        if application is not None:
            application.quit()

    def _later(self) -> None:
        self.cancel_download()
        self._info = None
        self.hide()
