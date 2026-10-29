# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Preferences dialog tests; the real user configuration is never touched."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QDialogButtonBox

from reduvid import __version__
from reduvid.core import config as config_module
from reduvid.core.config import Config, load_config
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.gui.preferences import PreferencesDialog
from reduvid.gui.theme.manager import ThemeManager


def ffmpeg_info() -> FFmpegInfo:
    return FFmpegInfo(
        Path("ffmpeg"), Path("ffprobe"), "6.1", frozenset({"libx264"}), frozenset(), ()
    )


def test_dialog_loads_the_current_configuration(qapp) -> None:
    config = Config(
        theme="riso",
        color_mode="dark",
        language="ca",
        reduce_motion=True,
        ffmpeg_path=Path("/opt/ffmpeg"),
    )

    dialog = PreferencesDialog(config, ThemeManager(qapp))

    assert dialog.theme_combo.currentData() == "riso"
    assert dialog.mode_combo.currentData() == "dark"
    assert dialog.language_combo.currentData() == "ca"
    assert dialog.reduce_motion.isChecked()
    assert dialog.ffmpeg_edit.text() == str(Path("/opt/ffmpeg"))


def test_accept_saves_and_keeps_the_other_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, qapp
) -> None:
    target = tmp_path / "config.toml"
    monkeypatch.setattr(config_module, "config_path", lambda: target)
    manager = ThemeManager(qapp)
    original = Config(
        theme="riso",
        color_mode="dark",
        language="ca",
        output_dir=tmp_path / "output",
        destination="archive",
        quality="high",
        container="mp4",
    )
    dialog = PreferencesDialog(original, manager)

    dialog.theme_combo.setCurrentIndex(dialog.theme_combo.findData("cinta"))
    dialog.mode_combo.setCurrentIndex(dialog.mode_combo.findData("light"))
    dialog.language_combo.setCurrentIndex(dialog.language_combo.findData("es"))
    dialog.reduce_motion.setChecked(True)
    dialog.ffmpeg_edit.setText(str(tmp_path / "ffmpeg"))
    dialog.accept()

    loaded, invalid = load_config(target)
    assert invalid == ()
    assert (loaded.theme, loaded.color_mode, loaded.language) == ("cinta", "light", "es")
    assert loaded.reduce_motion is True
    assert loaded.ffmpeg_path == tmp_path / "ffmpeg"
    assert loaded.output_dir == tmp_path / "output"
    assert (loaded.destination, loaded.quality, loaded.container) == ("archive", "high", "mp4")
    assert (manager.theme, manager.mode) == ("cinta", "light")


def test_empty_ffmpeg_path_is_saved_as_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, qapp
) -> None:
    target = tmp_path / "config.toml"
    monkeypatch.setattr(config_module, "config_path", lambda: target)
    dialog = PreferencesDialog(Config(ffmpeg_path=Path("/opt/ffmpeg")), ThemeManager(qapp))

    dialog.ffmpeg_edit.setText("")
    dialog.accept()

    loaded, _invalid = load_config(target)
    assert loaded.ffmpeg_path is None


def test_check_button_reports_the_detected_version(monkeypatch: pytest.MonkeyPatch, qapp) -> None:
    monkeypatch.setattr("reduvid.gui.preferences.detect_ffmpeg", lambda _path: ffmpeg_info())
    dialog = PreferencesDialog(Config(), ThemeManager(qapp))
    dialog.ffmpeg_edit.setText("/opt/ffmpeg")

    dialog.check_button.click()

    assert "6.1" in dialog.ffmpeg_status.text()


def test_check_button_reports_a_missing_ffmpeg(monkeypatch: pytest.MonkeyPatch, qapp) -> None:
    monkeypatch.setattr("reduvid.gui.preferences.detect_ffmpeg", lambda _path: None)
    dialog = PreferencesDialog(Config(), ThemeManager(qapp))

    dialog.check_button.click()

    assert "not found" in dialog.ffmpeg_status.text().lower()


def test_check_updates_option_loads_and_saves(qapp) -> None:
    dialog = PreferencesDialog(Config(check_updates=False), ThemeManager(qapp))

    assert dialog.check_updates.objectName() == "checkUpdatesCheck"
    assert dialog.check_updates.accessibleName()
    assert not dialog.check_updates.isChecked()
    assert dialog.check_updates_hint.property("role") == "muted"

    dialog.check_updates.setChecked(True)
    dialog.accept()

    assert dialog.config.check_updates is True


def test_dialog_shows_the_version(qapp) -> None:
    dialog = PreferencesDialog(Config(), ThemeManager(qapp))

    assert dialog.version_label.text() == f"Version {__version__}"
    assert dialog.version_label.property("role") == "muted"


def test_dialog_has_accessible_controls(qapp) -> None:
    dialog = PreferencesDialog(Config(), ThemeManager(qapp))

    button_box = dialog.findChild(QDialogButtonBox)
    assert button_box is not None
    assert dialog.theme_combo.accessibleName()
    assert dialog.mode_combo.accessibleName()
    assert dialog.language_combo.accessibleName()
    assert dialog.ffmpeg_edit.accessibleName()
    assert dialog.browse_button.accessibleName()
    assert dialog.check_button.accessibleName()
