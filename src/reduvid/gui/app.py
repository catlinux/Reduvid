# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Graphical application entry point."""

from __future__ import annotations

import faulthandler
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QWidget

from reduvid.core.config import Config, load_config
from reduvid.core.ffmpeg import FFmpegInfo, detect_ffmpeg
from reduvid.gui.ffmpeg_missing import FFmpegMissingWidget
from reduvid.gui.main_window import MainWindow
from reduvid.gui.theme.manager import ThemeManager
from reduvid.i18n import setup_language


def application_icon() -> QIcon:
    suffix = "ico" if sys.platform == "win32" else "png"
    path = Path(__file__).resolve().parents[1] / "resources" / "icon" / f"reduvid.{suffix}"
    return QIcon(str(path))


def create_application(argv: Sequence[str] | None = None) -> QApplication:
    """Return the running application or create it offscreen-friendly."""
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication([sys.argv[0], *(argv or ())])


def load_user_config() -> Config:
    """Read the configuration, falling back to defaults if it is unreadable."""
    try:
        config, _invalid_keys = load_config()
    except (OSError, tomllib.TOMLDecodeError):
        return Config()
    return config


def find_ffmpeg(config: Config) -> FFmpegInfo | None:
    try:
        return detect_ffmpeg(config.ffmpeg_path)
    except OSError:
        return None


def build_screen(
    config: Config, ffmpeg_info: FFmpegInfo | None, theme_manager: ThemeManager
) -> QWidget:
    """Return the screen to show: the missing-FFmpeg page or the main window."""
    if ffmpeg_info is None:
        return FFmpegMissingWidget(config)
    return MainWindow(config, ffmpeg_info, theme_manager)


def create_screen(config: Config, theme_manager: ThemeManager) -> QWidget:
    return build_screen(config, find_ffmpeg(config), theme_manager)


def run_application(app: QApplication, screen: QWidget) -> int:
    """Show *screen* and run the Qt event loop."""
    screen.show()
    return app.exec()


def main(argv: Sequence[str] | None = None) -> int:
    """Start Reduvid's graphical interface."""
    # A native crash would otherwise end with a bare "Bus error"; this prints where
    # each Python thread was. There is no stderr when running without a console.
    if sys.stderr is not None:
        faulthandler.enable()
    config = load_user_config()
    setup_language(config.language)
    app = create_application(argv)
    app.setApplicationName("Reduvid")
    app.setWindowIcon(application_icon())
    theme_manager = ThemeManager(app)
    theme_manager.apply(config.theme, config.color_mode)
    screen = create_screen(config, theme_manager)
    if isinstance(screen, FFmpegMissingWidget):

        def show_main_window(info: FFmpegInfo) -> None:
            window = MainWindow(config, info, theme_manager)
            window.show()
            screen.close()

        screen.ffmpeg_found.connect(show_main_window)
    return run_application(app, screen)
