# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Update notice and background-check tests, without network or processes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, Signal

from reduvid import __version__
from reduvid.core.config import Config, load_config
from reduvid.core.updates import UpdateError, UpdateInfo
from reduvid.gui import update_notice
from reduvid.gui.update_notice import UpdateNotice


def info(kind: str = "source") -> UpdateInfo:
    return UpdateInfo(
        version="1.3.0",
        tag="v1.3.0",
        notes="Changes in this release.",
        page_url="https://example.test/release",
        assets={
            "Reduvid-Setup-1.3.0.exe": "https://example.test/setup.exe",
            "Reduvid-1.3.0-x86_64.AppImage": "https://example.test/appimage",
            "SHA256SUMS": "https://example.test/SHA256SUMS",
        },
        checksums_url="https://example.test/SHA256SUMS",
    )


class FakeThread:
    def isRunning(self) -> bool:
        return False

    def wait(self, _timeout: int = 0) -> bool:
        return True


class RecordingOpener:
    def __init__(self, release: UpdateInfo) -> None:
        self.release = release
        self.calls = 0

    def __call__(self, _request: object, _timeout: float) -> bytes:
        self.calls += 1
        return json.dumps(
            {
                "tag_name": self.release.tag,
                "body": self.release.notes,
                "html_url": self.release.page_url,
                "draft": False,
                "prerelease": False,
                "assets": [
                    {"name": name, "browser_download_url": url}
                    for name, url in self.release.assets.items()
                ],
            }
        ).encode()


class FakeIntroDialog:
    disabled = False
    calls: ClassVar[list[int]] = []

    def __init__(self, _parent: object) -> None:
        pass

    def exec(self) -> int:
        type(self).calls.append(1)
        return 1


def test_intro_runs_before_the_background_check(tmp_path: Path, qapp) -> None:
    FakeIntroDialog.calls = []
    opener = RecordingOpener(info())
    config = Config(updates_notice_seen=False, check_updates=True)
    changes: list[Config] = []
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(update_notice, "UpdateIntroDialog", FakeIntroDialog)
    monkeypatch.setattr(update_notice, "install_kind", lambda: "source")
    monkeypatch.setattr(update_notice, "start_worker_thread", lambda worker: _run_worker(worker))
    try:
        notice = UpdateNotice(config, opener=opener, state_dir=tmp_path)
        notice.config_changed.connect(changes.append)
        notice.start()
    finally:
        monkeypatch.undo()

    assert FakeIntroDialog.calls == [1]
    assert opener.calls == 1
    assert changes[-1].updates_notice_seen is True
    assert changes[-1].check_updates is True
    assert not notice.isHidden()
    assert notice.message_label.text() == "Reduvid 1.3.0 is available"


def test_updated_notice_is_shown_and_saved(tmp_path: Path, qapp) -> None:
    target = tmp_path / "config.toml"
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("reduvid.core.config.config_path", lambda: target)
    try:
        notice = UpdateNotice(
            Config(
                updates_notice_seen=True,
                check_updates=False,
                last_run_version="0.8.0",
            )
        )
        changes: list[Config] = []
        notice.config_changed.connect(changes.append)
        notice.start()
    finally:
        monkeypatch.undo()

    assert notice._updated_version == __version__
    assert notice.message_label.text() == f"Reduvid was updated to version {__version__}."
    assert not notice.got_it_button.isHidden()
    assert notice.install_button.isHidden()
    assert changes[-1].last_run_version == __version__
    loaded, invalid = load_config(target)
    assert loaded.last_run_version == __version__
    assert invalid == ()

    notice.got_it_button.click()

    assert notice.isHidden()


@pytest.mark.parametrize("last_run_version", [None, __version__, "99.0.0"])
def test_no_updated_notice_for_new_same_or_newer_start(last_run_version: str | None, qapp) -> None:
    notice = UpdateNotice(
        Config(
            updates_notice_seen=True,
            check_updates=False,
            last_run_version=last_run_version,
        )
    )

    notice.start()

    assert notice._updated_version is None
    assert notice.isHidden()


def test_updated_notice_has_priority_over_available_update(
    qapp, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(update_notice, "install_kind", lambda: "windows_installer")
    notice = UpdateNotice(
        Config(
            updates_notice_seen=True,
            check_updates=False,
            last_run_version="0.8.0",
        )
    )
    notice.start()

    notice.show_info(info())

    assert notice.message_label.text() == f"Reduvid was updated to version {__version__}."
    assert notice.install_button.isHidden()

    notice.got_it_button.click()

    assert notice.message_label.text() == "Reduvid 1.3.0 is available"
    assert not notice.install_button.isHidden()


def test_windows_install_shows_progress_message_before_closing(
    tmp_path: Path, qapp, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "Reduvid-Setup-1.3.0.exe"
    path.write_bytes(b"installer")
    launched: list[tuple[Path, bool]] = []
    timers: list[tuple[int, object]] = []
    quits: list[bool] = []

    def launch(installer: Path, *, relaunch: bool = False) -> None:
        launched.append((installer, relaunch))

    class FakeApplication:
        def quit(self) -> None:
            quits.append(True)

    monkeypatch.setattr(update_notice, "launch_windows_installer", launch)
    monkeypatch.setattr(
        update_notice.QTimer,
        "singleShot",
        lambda delay, callback: timers.append((delay, callback)),
    )
    monkeypatch.setattr(
        update_notice.QApplication,
        "instance",
        lambda: FakeApplication(),
    )
    notice = UpdateNotice(Config(updates_notice_seen=True))
    notice._info = info()
    notice._kind = "windows_installer"

    notice._download_done(path)

    assert launched == [(path, True)]
    assert timers and timers[0][0] == 2500
    assert quits == []
    assert notice.message_label.text() == (
        "Installing Reduvid 1.3.0… Reduvid will open again when it finishes."
    )
    assert notice.got_it_button.isHidden()
    assert notice.install_button.isHidden()

    timers[0][1]()
    assert quits == [True]


def test_windows_install_does_not_close_when_launch_fails(
    tmp_path: Path, qapp, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "Reduvid-Setup-1.3.0.exe"
    timers: list[object] = []

    def launch(_installer: Path, *, relaunch: bool = False) -> None:
        raise UpdateError("install_failed", "cannot start")

    monkeypatch.setattr(update_notice, "launch_windows_installer", launch)
    monkeypatch.setattr(
        update_notice.QTimer, "singleShot", lambda _delay, callback: timers.append(callback)
    )
    notice = UpdateNotice(Config(updates_notice_seen=True))
    notice._info = info()
    notice._kind = "windows_installer"

    notice._download_done(path)

    assert timers == []
    assert not notice.error_label.isHidden()
    assert "not be installed" in notice.error_label.text()


def test_first_run_can_disable_checks_without_network(tmp_path: Path, qapp) -> None:
    FakeIntroDialog.calls = []
    FakeIntroDialog.disabled = True
    opener = RecordingOpener(info())
    changes: list[Config] = []
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(update_notice, "UpdateIntroDialog", FakeIntroDialog)
    try:
        notice = UpdateNotice(
            Config(updates_notice_seen=False, check_updates=True),
            opener=opener,
            state_dir=tmp_path,
        )
        notice.config_changed.connect(changes.append)
        notice.start()
    finally:
        FakeIntroDialog.disabled = False
        monkeypatch.undo()

    assert opener.calls == 0
    assert changes[-1].updates_notice_seen is True
    assert changes[-1].check_updates is False


def test_update_disabled_shows_no_intro_and_no_network(tmp_path: Path, qapp) -> None:
    FakeIntroDialog.calls = []
    opener = RecordingOpener(info())
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(update_notice, "UpdateIntroDialog", FakeIntroDialog)
    try:
        notice = UpdateNotice(
            Config(updates_notice_seen=True, check_updates=False),
            opener=opener,
            state_dir=tmp_path,
        )
        notice.start()
    finally:
        monkeypatch.undo()

    assert FakeIntroDialog.calls == []
    assert opener.calls == 0
    assert notice.isHidden()


def test_source_notice_only_opens_the_release_page(qapp, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(update_notice, "install_kind", lambda: "source")
    notice = UpdateNotice(Config(updates_notice_seen=True))
    opened: list[str] = []
    monkeypatch.setattr(
        update_notice.QDesktopServices,
        "openUrl",
        lambda url: opened.append(url.toString()),
    )

    notice.show_info(info())

    assert not notice.isHidden()
    assert notice.install_button.isHidden()
    assert notice.on_close_button.isHidden()
    assert not notice.page_button.isHidden()
    assert notice.message_label.text() == "Reduvid 1.3.0 is available"

    notice.page_button.click()

    assert opened == ["https://example.test/release"]


def test_install_notice_shows_actions_notes_and_waits_during_a_queue(
    qapp, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(update_notice, "install_kind", lambda: "windows_installer")
    notice = UpdateNotice(Config(updates_notice_seen=True))

    notice.show_info(info())

    assert not notice.install_button.isHidden()
    assert not notice.on_close_button.isHidden()
    assert not notice.later_button.isHidden()
    assert notice.page_button.isHidden()

    notice.whats_new_button.click()
    assert not notice.notes_label.isHidden()
    assert notice.notes_label.text() == "Changes in this release."

    notice.set_queue_running(True)
    assert notice.isHidden()
    notice.set_queue_running(False)
    assert not notice.isHidden()


def test_download_failure_is_shown_without_installing(
    qapp, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(update_notice, "install_kind", lambda: "windows_installer")
    notice = UpdateNotice(Config(updates_notice_seen=True))
    notice.show_info(info())

    notice._download_failed("checksum_mismatch", "bad digest")

    assert not notice.error_label.isHidden()
    assert "corrupt" in notice.error_label.text()
    assert not notice.install_button.isHidden()


def test_cancelled_download_is_deleted_and_not_installed(
    tmp_path: Path, qapp, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "Reduvid-Setup-1.3.0.exe"
    path.write_bytes(b"installer")
    launched: list[Path] = []
    monkeypatch.setattr(
        update_notice,
        "launch_windows_installer",
        lambda installer, *, relaunch=False: launched.append(installer),
    )
    notice = UpdateNotice(Config(updates_notice_seen=True))
    notice._kind = "windows_installer"
    notice._download_cancelled = True

    notice._download_done(path)

    assert not path.exists()
    assert launched == []


def test_appimage_cross_folder_download_is_staged_before_replace(tmp_path: Path, qapp) -> None:
    current = tmp_path / "apps" / "Reduvid.AppImage"
    current.parent.mkdir()
    current.write_bytes(b"old")
    downloaded = tmp_path / "cache" / "Reduvid-1.3.0-x86_64.AppImage"
    downloaded.parent.mkdir()
    downloaded.write_bytes(b"new")

    UpdateNotice._install_appimage(downloaded, current)

    assert current.read_bytes() == b"new"
    assert downloaded.read_bytes() == b"new"


def test_on_close_download_is_applied_only_at_close(
    tmp_path: Path, qapp, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "Reduvid-Setup-1.3.0.exe"
    path.write_bytes(b"installer")
    launched: list[Path] = []
    relaunches: list[bool] = []

    class FakeDownloadWorker(QObject):
        progress = Signal(int, object)
        done = Signal(object)
        failed = Signal(str, str)
        finished = Signal()

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            super().__init__()

        def run(self) -> None:
            self.done.emit(path)
            self.finished.emit()

        def cancel(self) -> None:
            pass

    monkeypatch.setattr(update_notice, "install_kind", lambda: "windows_installer")
    monkeypatch.setattr(update_notice, "UpdateDownloadWorker", FakeDownloadWorker)
    monkeypatch.setattr(update_notice, "start_worker_thread", lambda worker: _run_worker(worker))
    monkeypatch.setattr(
        update_notice,
        "launch_windows_installer",
        lambda installer, *, relaunch=False: (
            launched.append(installer),
            relaunches.append(relaunch),
        ),
    )
    notice = UpdateNotice(Config(updates_notice_seen=True), download_dir=tmp_path)
    notice.show_info(info())

    notice._start_download(install_on_close=True)

    assert notice._download_path == path
    assert launched == []
    notice.prepare_close()
    assert launched == [path]
    assert relaunches == [False]


def test_saved_first_run_choice_is_persisted(tmp_path: Path, qapp) -> None:
    target = tmp_path / "config.toml"
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("reduvid.core.config.config_path", lambda: target)
    monkeypatch.setattr(update_notice, "UpdateIntroDialog", FakeIntroDialog)
    monkeypatch.setattr(update_notice, "start_worker_thread", lambda _worker: FakeThread())
    try:
        notice = UpdateNotice(Config(updates_notice_seen=False, check_updates=True))
        notice.start()
    finally:
        monkeypatch.undo()

    loaded, invalid = load_config(target)
    assert loaded.updates_notice_seen is True
    assert loaded.check_updates is True
    assert invalid == ()


def _run_worker(worker: object) -> FakeThread:
    worker.run()  # type: ignore[attr-defined]
    return FakeThread()
