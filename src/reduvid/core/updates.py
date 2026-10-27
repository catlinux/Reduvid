# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Check, download and prepare Reduvid updates from GitHub releases."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import platformdirs

from reduvid.core.process import hidden_window_kwargs

UpdateErrorCode = Literal[
    "no_asset",
    "no_checksum",
    "checksum_mismatch",
    "cancelled",
    "network",
    "install_failed",
]
InstallKind = Literal["windows_installer", "appimage", "source"]

_RELEASES_URL = "https://api.github.com/repos/catlinux/Reduvid/releases/latest"
_CHECK_INTERVAL_SECONDS = 24 * 60 * 60
_HTTP_TIMEOUT_SECONDS = 10.0
_STATE_FILENAME = "updates.json"
_VERSION_PATTERN = re.compile(r"v?([0-9]+)\.([0-9]+)\.([0-9]+)")


@dataclass(frozen=True)
class UpdateInfo:
    """A newer GitHub release and the assets it publishes."""

    version: str
    tag: str
    notes: str
    page_url: str
    assets: dict[str, str]
    checksums_url: str | None


class UpdateError(RuntimeError):
    """An update could not be prepared or installed."""

    def __init__(self, code: UpdateErrorCode, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"Update failed ({code}): {detail}")


def parse_version(text: str) -> tuple[int, int, int] | None:
    """Parse a plain or ``v``-prefixed SemVer version."""
    match = _VERSION_PATTERN.fullmatch(text)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _default_opener(request: urllib.request.Request, timeout: float) -> bytes:
    response = urllib.request.urlopen(request, timeout=timeout)  # noqa: S310
    return bytes(response.read())


def _default_stream(url: str) -> Iterable[bytes]:
    response = urllib.request.urlopen(url, timeout=_HTTP_TIMEOUT_SECONDS)  # noqa: S310
    try:
        while chunk := response.read(64 * 1024):
            yield chunk
    finally:
        response.close()


def _timestamp(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return None
    else:
        return None
    return number if math.isfinite(number) else None


def _last_check(path: Path) -> float | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if isinstance(payload, int | float):
        return _timestamp(payload)
    if not isinstance(payload, dict):
        return None
    for key in ("last_check", "checked_at", "timestamp"):
        timestamp = _timestamp(payload.get(key))
        if timestamp is not None:
            return timestamp
    return None


def _write_last_check(path: Path, value: float) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"last_check": value}), encoding="utf-8")
    except OSError:
        pass


def _info_from_release(payload: bytes, current: tuple[int, int, int]) -> UpdateInfo | None:
    release = json.loads(payload.decode("utf-8"))
    if not isinstance(release, dict):
        return None
    if release.get("draft") or release.get("prerelease"):
        return None
    tag = release.get("tag_name")
    if not isinstance(tag, str):
        return None
    tag_version = parse_version(tag)
    if tag_version is None or tag_version <= current:
        return None

    raw_assets = release.get("assets")
    assets: dict[str, str] = {}
    checksums_url: str | None = None
    if isinstance(raw_assets, list):
        for item in raw_assets:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            url = item.get("browser_download_url")
            # Never download an installer over a connection that is not encrypted.
            if isinstance(name, str) and isinstance(url, str) and url.startswith("https://"):
                assets[name] = url
                if name == "SHA256SUMS":
                    checksums_url = url

    body = release.get("body")
    page_url = release.get("html_url")
    return UpdateInfo(
        version=tag[1:] if tag.startswith("v") else tag,
        tag=tag,
        notes=body if isinstance(body, str) else "",
        page_url=page_url if isinstance(page_url, str) else "",
        assets=assets,
        checksums_url=checksums_url,
    )


def check_for_update(
    current: str,
    *,
    now: float | None = None,
    state_dir: Path | None = None,
    opener: Callable[[urllib.request.Request, float], bytes] | None = None,
    force: bool = False,
) -> UpdateInfo | None:
    """Return a newer release, at most once per 24 hours unless forced."""
    try:
        current_version = parse_version(current)
        if current_version is None:
            return None
        timestamp = time.time() if now is None else now
        directory = state_dir or Path(platformdirs.user_cache_dir("reduvid"))
        state_path = directory / _STATE_FILENAME
        if not force:
            last_check = _last_check(state_path)
            if last_check is not None and 0 <= timestamp - last_check < _CHECK_INTERVAL_SECONDS:
                return None

        request = urllib.request.Request(
            _RELEASES_URL,
            headers={
                "User-Agent": f"Reduvid/{current}",
                "Accept": "application/vnd.github+json",
            },
        )
        fetch = opener if opener is not None else _default_opener
        payload = fetch(request, _HTTP_TIMEOUT_SECONDS)
        # Only a successful answer starts the 24 h wait, so being offline retries next start.
        _write_last_check(state_path, timestamp)
        return _info_from_release(payload, current_version)
    except Exception:
        return None


def install_kind() -> InstallKind:
    """Return how this Reduvid installation can replace itself."""
    if "APPIMAGE" in os.environ:
        return "appimage"
    if sys.platform == "win32" and bool(getattr(sys, "frozen", False)):
        return "windows_installer"
    return "source"


def asset_name(info: UpdateInfo, kind: InstallKind) -> str | None:
    """Return the release asset name for *kind*, if it is published."""
    if kind == "windows_installer":
        name = f"Reduvid-Setup-{info.version}.exe"
    elif kind == "appimage":
        name = f"Reduvid-{info.version}-x86_64.AppImage"
    else:
        return None
    return name if name in info.assets else None


def _valid_sha256(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _checksum_for(payload: bytes, filename: str) -> str | None:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return None
    for line in text.splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        digest, name = parts
        name = name.strip()
        if name.startswith("*"):
            name = name[1:]
        if name == filename and _valid_sha256(digest):
            return digest.lower()
    return None


def download_update(
    info: UpdateInfo,
    kind: InstallKind,
    dest_dir: Path,
    *,
    opener_stream: Callable[[str], Iterable[bytes]] | None = None,
    progress: Callable[[int, int | None], None] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> Path:
    """Download and verify an update asset, returning its final path."""
    name = asset_name(info, kind)
    if name is None:
        raise UpdateError("no_asset", "The release does not publish this asset.")
    if info.checksums_url is None:
        raise UpdateError("no_checksum", "The release has no SHA256SUMS asset.")

    stream = opener_stream if opener_stream is not None else _default_stream
    part: Path | None = None
    try:
        checksum_payload = b"".join(stream(info.checksums_url))
        expected = _checksum_for(checksum_payload, name)
        if expected is None:
            raise UpdateError("no_checksum", f"{name} is not listed in SHA256SUMS.")

        dest_dir.mkdir(parents=True, exist_ok=True)
        url = info.assets[name]
        part = dest_dir / f"{name}.part"
        final = dest_dir / name
        digest = hashlib.sha256()
        downloaded = 0
        if cancel is not None and cancel():
            raise UpdateError("cancelled", "The update was cancelled.")

        with part.open("wb") as output:
            for chunk in stream(url):
                if cancel is not None and cancel():
                    raise UpdateError("cancelled", "The update was cancelled.")
                output.write(chunk)
                digest.update(chunk)
                downloaded += len(chunk)
                if progress is not None:
                    progress(downloaded, None)

        if digest.hexdigest().lower() != expected:
            raise UpdateError("checksum_mismatch", "The downloaded file is corrupt.")
        part.replace(final)
        return final
    except UpdateError:
        raise
    except Exception as error:
        raise UpdateError("network", str(error)) from error
    finally:
        if part is not None:
            with suppress(OSError):
                part.unlink(missing_ok=True)


def launch_windows_installer(installer: Path) -> None:
    """Start a detached silent Windows installer."""
    arguments = [str(installer), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]
    try:
        kwargs = hidden_window_kwargs()
    except AttributeError:
        kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = int(getattr(subprocess, "DETACHED_PROCESS", 0x00000008)) | int(
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        )
    subprocess.Popen(arguments, **kwargs)  # noqa: S603


def replace_appimage(new: Path, current: Path) -> None:
    """Atomically replace the running AppImage with *new*."""
    if new.parent != current.parent:
        raise UpdateError("install_failed", "Both AppImages must share a folder.")
    try:
        new.chmod(0o755)
        os.replace(new, current)  # noqa: PTH105
    except OSError as error:
        raise UpdateError("install_failed", str(error)) from error
