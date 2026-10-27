# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Update checks, downloads and installation helpers, without network or processes."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

from reduvid.core import updates


def release_payload(
    tag: str = "v1.3.0",
    *,
    draft: bool = False,
    prerelease: bool = False,
) -> dict[str, object]:
    return {
        "tag_name": tag,
        "draft": draft,
        "prerelease": prerelease,
        "body": "Changes",
        "html_url": "https://github.com/catlinux/Reduvid/releases/tag/v1.3.0",
        "assets": [
            {
                "name": "Reduvid-Setup-1.3.0.exe",
                "browser_download_url": "https://example.test/setup.exe",
            },
            {
                "name": "Reduvid-1.3.0-x86_64.AppImage",
                "browser_download_url": "https://example.test/appimage",
            },
            {
                "name": "SHA256SUMS",
                "browser_download_url": "https://example.test/SHA256SUMS",
            },
        ],
    }


class RecordingOpener:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.calls = 0
        self.request: object = None
        self.timeout: float | None = None

    def __call__(self, request: object, timeout: float) -> bytes:
        self.calls += 1
        self.request = request
        self.timeout = timeout
        return self.payload


class StreamOpener:
    def __init__(self, values: dict[str, bytes | Exception]) -> None:
        self.values = values
        self.calls: list[str] = []

    def __call__(self, url: str):
        self.calls.append(url)
        value = self.values[url]
        if isinstance(value, Exception):
            raise value
        yield value


def make_info(
    *,
    assets: dict[str, str] | None = None,
    checksums_url: str | None = "https://example.test/SHA256SUMS",
) -> updates.UpdateInfo:
    return updates.UpdateInfo(
        version="1.2.3",
        tag="v1.2.3",
        notes="Notes",
        page_url="https://example.test/release",
        assets=assets
        if assets is not None
        else {
            "Reduvid-Setup-1.2.3.exe": "https://example.test/setup.exe",
            "SHA256SUMS": "https://example.test/SHA256SUMS",
        },
        checksums_url=checksums_url,
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.2.3", (1, 2, 3)),
        ("v1.2.3", (1, 2, 3)),
        ("v0.0.1", (0, 0, 1)),
        ("1.2", None),
        ("1.2.3.4", None),
        ("v1.2.3-beta", None),
        ("V1.2.3", None),
        ("foo", None),
    ],
)
def test_parse_version(text: str, expected: tuple[int, int, int] | None) -> None:
    assert updates.parse_version(text) == expected


def test_check_for_update_reads_a_newer_release(tmp_path: Path) -> None:
    opener = RecordingOpener(json.dumps(release_payload()).encode())

    info = updates.check_for_update("1.2.3", now=1000.0, state_dir=tmp_path, opener=opener)

    assert info is not None
    assert info.version == "1.3.0"
    assert info.tag == "v1.3.0"
    assert info.notes == "Changes"
    assert info.page_url.endswith("v1.3.0")
    assert info.checksums_url == "https://example.test/SHA256SUMS"
    assert "Reduvid-Setup-1.3.0.exe" in info.assets
    assert opener.calls == 1
    assert opener.timeout == 10.0
    assert opener.request is not None
    request = opener.request
    assert request.get_header("User-agent") == "Reduvid/1.2.3"  # type: ignore[attr-defined]
    assert request.get_header("Accept") == "application/vnd.github+json"  # type: ignore[attr-defined]
    assert request.full_url == updates._RELEASES_URL  # type: ignore[attr-defined]


@pytest.mark.parametrize("current", ["1.3.0", "1.4.0"])
def test_check_for_update_ignores_same_or_older_versions(tmp_path: Path, current: str) -> None:
    opener = RecordingOpener(json.dumps(release_payload()).encode())

    assert (
        updates.check_for_update(current, now=1000.0, state_dir=tmp_path, opener=opener, force=True)
        is None
    )


@pytest.mark.parametrize("field", ["draft", "prerelease"])
def test_check_for_update_ignores_drafts_and_prereleases(tmp_path: Path, field: str) -> None:
    payload = release_payload()
    payload[field] = True
    opener = RecordingOpener(json.dumps(payload).encode())

    assert (
        updates.check_for_update("1.2.3", now=1000.0, state_dir=tmp_path, opener=opener, force=True)
        is None
    )


def test_check_for_update_caches_for_24_hours_and_can_be_forced(tmp_path: Path) -> None:
    payload = json.dumps(release_payload()).encode()
    opener = RecordingOpener(payload)

    first = updates.check_for_update("1.2.3", now=1000.0, state_dir=tmp_path, opener=opener)
    second = updates.check_for_update(
        "1.2.3", now=1000.0 + 23 * 3600, state_dir=tmp_path, opener=opener
    )
    forced = updates.check_for_update(
        "1.2.3",
        now=1000.0 + 23 * 3600,
        state_dir=tmp_path,
        opener=opener,
        force=True,
    )

    assert first is not None
    assert second is None
    assert forced is not None
    assert opener.calls == 2
    state = json.loads((tmp_path / "updates.json").read_text(encoding="utf-8"))
    assert state["last_check"] == 1000.0 + 23 * 3600


def test_check_for_update_never_raises_and_survives_bad_json(tmp_path: Path) -> None:
    def broken(_request: object, _timeout: float) -> bytes:
        raise OSError("offline")

    assert (
        updates.check_for_update("1.2.3", now=1000.0, state_dir=tmp_path, opener=broken, force=True)
        is None
    )
    assert (
        updates.check_for_update(
            "1.2.3",
            now=1000.0,
            state_dir=tmp_path,
            opener=lambda _request, _timeout: b"not json",
            force=True,
        )
        is None
    )


def test_install_kind_uses_the_environment_and_platform(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("APPIMAGE", raising=False)
    monkeypatch.setattr(updates.sys, "platform", "linux")
    monkeypatch.delattr(updates.sys, "frozen", raising=False)

    assert updates.install_kind() == "source"

    monkeypatch.setenv("APPIMAGE", str(tmp_path / "Reduvid.AppImage"))
    assert updates.install_kind() == "appimage"

    monkeypatch.delenv("APPIMAGE")
    monkeypatch.setattr(updates.sys, "platform", "win32")
    monkeypatch.setattr(updates.sys, "frozen", True, raising=False)
    assert updates.install_kind() == "windows_installer"

    monkeypatch.setattr(updates.sys, "frozen", False, raising=False)
    assert updates.install_kind() == "source"


def test_asset_name_matches_the_published_assets() -> None:
    info = make_info(
        assets={
            "Reduvid-Setup-1.2.3.exe": "https://example.test/setup.exe",
            "Reduvid-1.2.3-x86_64.AppImage": "https://example.test/appimage",
        }
    )

    assert updates.asset_name(info, "windows_installer") == "Reduvid-Setup-1.2.3.exe"
    assert updates.asset_name(info, "appimage") == "Reduvid-1.2.3-x86_64.AppImage"
    assert updates.asset_name(info, "source") is None
    assert updates.asset_name(make_info(assets={}), "windows_installer") is None


def test_download_update_verifies_and_returns_the_file(tmp_path: Path) -> None:
    content = b"the update"
    digest = hashlib.sha256(content).hexdigest()
    info = make_info()
    stream = StreamOpener(
        {
            "https://example.test/SHA256SUMS": (f"{digest} *Reduvid-Setup-1.2.3.exe\n".encode()),
            "https://example.test/setup.exe": content,
        }
    )
    progress: list[tuple[int, int | None]] = []

    result = updates.download_update(
        info,
        "windows_installer",
        tmp_path,
        opener_stream=stream,
        progress=lambda downloaded, total: progress.append((downloaded, total)),
    )

    assert result == tmp_path / "Reduvid-Setup-1.2.3.exe"
    assert result.read_bytes() == content
    assert not (tmp_path / "Reduvid-Setup-1.2.3.exe.part").exists()
    assert progress == [(len(content), None)]


def test_download_update_rejects_missing_assets_or_checksums(tmp_path: Path) -> None:
    with pytest.raises(updates.UpdateError) as no_asset:
        updates.download_update(make_info(assets={}), "windows_installer", tmp_path)
    assert no_asset.value.code == "no_asset"

    with pytest.raises(updates.UpdateError) as no_checksum:
        updates.download_update(make_info(checksums_url=None), "windows_installer", tmp_path)
    assert no_checksum.value.code == "no_checksum"


def test_download_update_rejects_a_bad_checksum(tmp_path: Path) -> None:
    info = make_info()
    stream = StreamOpener(
        {
            "https://example.test/SHA256SUMS": (
                f"{hashlib.sha256(b'other').hexdigest()}  Reduvid-Setup-1.2.3.exe\n".encode()
            ),
            "https://example.test/setup.exe": b"the update",
        }
    )

    with pytest.raises(updates.UpdateError) as raised:
        updates.download_update(info, "windows_installer", tmp_path, opener_stream=stream)

    assert raised.value.code == "checksum_mismatch"
    assert not list(tmp_path.glob("*.part"))


def test_download_update_rejects_a_missing_checksum(tmp_path: Path) -> None:
    info = make_info()
    stream = StreamOpener(
        {
            "https://example.test/SHA256SUMS": b"",
            "https://example.test/setup.exe": b"the update",
        }
    )

    with pytest.raises(updates.UpdateError) as raised:
        updates.download_update(info, "windows_installer", tmp_path, opener_stream=stream)

    assert raised.value.code == "no_checksum"
    assert not list(tmp_path.glob("*.part"))


def test_download_update_cancel_removes_the_part_file(tmp_path: Path) -> None:
    content = b"the update"
    digest = hashlib.sha256(content).hexdigest()
    info = make_info()
    stream = StreamOpener(
        {
            "https://example.test/SHA256SUMS": (f"{digest}  Reduvid-Setup-1.2.3.exe\n".encode()),
            "https://example.test/setup.exe": content,
        }
    )

    with pytest.raises(updates.UpdateError) as raised:
        updates.download_update(
            info,
            "windows_installer",
            tmp_path,
            opener_stream=stream,
            cancel=lambda: True,
        )

    assert raised.value.code == "cancelled"
    assert not list(tmp_path.glob("*.part"))
    assert not (tmp_path / "Reduvid-Setup-1.2.3.exe").exists()


def test_download_update_network_error_removes_the_part_file(tmp_path: Path) -> None:
    content = b"the update"
    digest = hashlib.sha256(content).hexdigest()
    info = make_info()
    stream = StreamOpener(
        {
            "https://example.test/SHA256SUMS": (f"{digest}  Reduvid-Setup-1.2.3.exe\n".encode()),
            "https://example.test/setup.exe": OSError("offline"),
        }
    )

    with pytest.raises(updates.UpdateError) as raised:
        updates.download_update(info, "windows_installer", tmp_path, opener_stream=stream)

    assert raised.value.code == "network"
    assert not list(tmp_path.glob("*.part"))


def test_replace_appimage_is_atomic_and_checks_the_folder(tmp_path: Path) -> None:
    current = tmp_path / "Reduvid.AppImage"
    new = tmp_path / "Reduvid-new.AppImage"
    current.write_bytes(b"old")
    new.write_bytes(b"new")

    updates.replace_appimage(new, current)

    assert not new.exists()
    assert current.read_bytes() == b"new"
    if os.name != "nt":
        assert stat.S_IMODE(current.stat().st_mode) == 0o755

    other = tmp_path / "other"
    other.mkdir()
    misplaced = other / "Reduvid.AppImage"
    misplaced.write_bytes(b"new")
    with pytest.raises(updates.UpdateError) as raised:
        updates.replace_appimage(misplaced, current)
    assert raised.value.code == "install_failed"


def test_launch_windows_installer_uses_detached_flags(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def popen(args: list[str], **kwargs: object) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(updates.subprocess, "Popen", popen)
    monkeypatch.setattr(updates.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    monkeypatch.setattr(updates.sys, "platform", "win32")
    installer = tmp_path / "Reduvid-Setup-1.3.0.exe"

    updates.launch_windows_installer(installer)

    expected = getattr(subprocess, "DETACHED_PROCESS", 0x00000008) | getattr(
        subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200
    )
    assert calls == [
        (
            [
                str(installer),
                "/SILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
            ],
            {"creationflags": expected},
        )
    ]


def test_a_failed_check_does_not_start_the_24_hour_wait(tmp_path: Path) -> None:
    def offline(request: object, timeout: float) -> bytes:
        raise OSError("no network")

    assert updates.check_for_update("1.0.0", now=1000.0, state_dir=tmp_path, opener=offline) is None

    opener = RecordingOpener(json.dumps(release_payload()).encode("utf-8"))
    info = updates.check_for_update("1.0.0", now=1001.0, state_dir=tmp_path, opener=opener)

    assert opener.calls == 1
    assert info is not None


def test_assets_without_https_are_ignored(tmp_path: Path) -> None:
    payload = release_payload()
    payload["assets"] = [
        {"name": "Reduvid-Setup-1.3.0.exe", "browser_download_url": "http://example.test/s.exe"},
        {"name": "SHA256SUMS", "browser_download_url": "https://example.test/SHA256SUMS"},
    ]
    opener = RecordingOpener(json.dumps(payload).encode("utf-8"))

    info = updates.check_for_update("1.0.0", now=0.0, state_dir=tmp_path, opener=opener)

    assert info is not None
    assert "Reduvid-Setup-1.3.0.exe" not in info.assets
    assert updates.asset_name(info, "windows_installer") is None
