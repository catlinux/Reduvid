# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Application start-up decisions and the missing-FFmpeg screen."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QFileDialog, QLineEdit

from reduvid.core.config import Config, load_config
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.gui import app
from reduvid.gui.ffmpeg_missing import FFmpegMissingWidget
from reduvid.gui.main_window import MainWindow
from reduvid.gui.theme.manager import ThemeManager


def ffmpeg_info() -> FFmpegInfo:
    return FFmpegInfo(
        Path("ffmpeg"), Path("ffprobe"), "6.1", frozenset({"libx264"}), frozenset(), ()
    )


def test_missing_ffmpeg_shows_its_screen(monkeypatch: pytest.MonkeyPatch, qapp) -> None:
    monkeypatch.setattr("reduvid.gui.app.detect_ffmpeg", lambda _path: None)

    screen = app.create_screen(Config(), ThemeManager(qapp))

    assert isinstance(screen, FFmpegMissingWidget)
    assert screen.objectName() == "ffmpegMissing"


def test_found_ffmpeg_shows_the_main_window(monkeypatch: pytest.MonkeyPatch, qapp) -> None:
    monkeypatch.setattr("reduvid.gui.app.detect_ffmpeg", lambda _path: ffmpeg_info())

    screen = app.create_screen(Config(), ThemeManager(qapp))

    assert isinstance(screen, MainWindow)


def test_find_ffmpeg_reports_none_on_os_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing(_path: Path | None) -> FFmpegInfo | None:
        raise OSError("broken")

    monkeypatch.setattr("reduvid.gui.app.detect_ffmpeg", failing)

    assert app.find_ffmpeg(Config()) is None


def test_unreadable_config_falls_back_to_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing() -> tuple[Config, tuple[str, ...]]:
        raise OSError("unreadable")

    monkeypatch.setattr("reduvid.gui.app.load_config", failing)

    assert app.load_user_config() == Config()


def test_missing_ffmpeg_screen_explains_the_commands(qapp) -> None:
    widget = FFmpegMissingWidget(Config())

    commands = [field.text() for field in widget.findChildren(QLineEdit)]

    assert "winget install Gyan.FFmpeg" in commands
    assert "sudo apt install ffmpeg" in commands
    assert "sudo dnf install ffmpeg" in commands
    assert widget.choose_button.accessibleName()
    assert widget.retry_button.accessibleName()


def test_retry_emits_when_ffmpeg_is_found(monkeypatch: pytest.MonkeyPatch, qapp) -> None:
    info = ffmpeg_info()
    monkeypatch.setattr("reduvid.gui.ffmpeg_missing.detect_ffmpeg", lambda _path: info)
    widget = FFmpegMissingWidget(Config())
    found: list[FFmpegInfo] = []
    widget.ffmpeg_found.connect(found.append)

    widget.retry_button.click()

    assert found == [info]


def test_choosing_a_path_saves_it_in_the_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, qapp
) -> None:
    from reduvid.core import config as config_module

    target = tmp_path / "config.toml"
    executable = tmp_path / "ffmpeg"
    executable.touch()
    monkeypatch.setattr(config_module, "config_path", lambda: target)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *_args, **_kwargs: (str(executable), "")),
    )
    monkeypatch.setattr("reduvid.gui.ffmpeg_missing.detect_ffmpeg", lambda _path: None)
    widget = FFmpegMissingWidget(Config())

    widget.choose_button.click()

    loaded, invalid = load_config(target)
    assert invalid == ()
    assert loaded.ffmpeg_path == executable
    assert widget.status_label.text()


def test_missing_screen_survives_a_search_that_raises(
    monkeypatch: pytest.MonkeyPatch, qapp
) -> None:
    def explode(_path: Path | None) -> str:
        raise OSError(448, "untrusted mount point")

    monkeypatch.setattr("reduvid.gui.ffmpeg_missing.describe_search", explode)

    widget = FFmpegMissingWidget(Config())

    assert "search failed" in widget.details_label.text()
