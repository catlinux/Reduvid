# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Named PlanOptions profiles stored as individual TOML files."""

from __future__ import annotations

import os
import re
import tempfile
import tomllib
from pathlib import Path

from platformdirs import user_config_dir

from reduvid.core.plan import PlanOptions

_UNSAFE_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def list_profiles(path: Path | None = None) -> tuple[str, ...]:
    """Return the stored profile names, sorted alphabetically."""
    names = [
        name
        for file_path in _profile_files(_profiles_dir(path))
        if (name := _stored_name(file_path)) is not None
    ]
    return tuple(sorted(names))


def load_profile(name: str, path: Path | None = None) -> PlanOptions:
    """Load the profile stored under *name*."""
    directory = _profiles_dir(path)
    for file_path in _profile_files(directory):
        raw = _read_profile(file_path)
        if raw is None or raw.get("name") != name:
            continue
        return _options_from_raw(raw)
    raise FileNotFoundError(name)


def save_profile(name: str, options: PlanOptions, path: Path | None = None) -> None:
    """Atomically write the profile, replacing an existing one with the same name."""
    if not name.strip():
        raise ValueError("profile name must not be empty")
    directory = _profiles_dir(path)
    directory.mkdir(parents=True, exist_ok=True)
    target = _target_path(directory, name)
    _write_profile(target, name, options)


def delete_profile(name: str, path: Path | None = None) -> None:
    """Delete the profile if it exists; deleting a missing profile is a no-op."""
    for file_path in _profile_files(_profiles_dir(path)):
        raw = _read_profile(file_path)
        if raw is not None and raw.get("name") == name:
            file_path.unlink(missing_ok=True)


def _profiles_dir(path: Path | None) -> Path:
    if path is not None:
        return path
    return Path(user_config_dir("reduvid")) / "profiles"


def _profile_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        (
            file_path
            for file_path in directory.glob("*.toml")
            if file_path.is_file() and not file_path.name.startswith(".")
        ),
        key=lambda file_path: file_path.name.casefold(),
    )


def _read_profile(file_path: Path) -> dict[str, object] | None:
    try:
        with file_path.open("rb") as handle:
            raw: dict[str, object] = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    return raw


def _stored_name(file_path: Path) -> str | None:
    raw = _read_profile(file_path)
    if raw is None:
        return None
    name = raw.get("name")
    return name if isinstance(name, str) else None


def _options_from_raw(raw: dict[str, object]) -> PlanOptions:
    destination = raw.get("destination", "jellyfin")
    quality = raw.get("quality", "balanced")
    container = raw.get("container", "mkv")
    if not isinstance(destination, str) or not isinstance(quality, str):
        raise ValueError("invalid profile destination or quality")
    if container not in ("mkv", "mp4"):
        raise ValueError("invalid profile container")
    max_height = raw.get("max_height")
    if max_height is not None and (not isinstance(max_height, int) or isinstance(max_height, bool)):
        raise ValueError("invalid profile max_height")
    return PlanOptions(
        destination=destination,
        quality=quality,
        container=container,
        max_height=max_height,
        audio_languages=_languages(raw, "audio_languages"),
        subtitle_languages=_languages(raw, "subtitle_languages"),
    )


def _languages(raw: dict[str, object], key: str) -> frozenset[str] | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"invalid profile {key}")
    return frozenset(value)


def _safe_filename(name: str) -> str:
    safe = _UNSAFE_FILENAME.sub("_", name).strip().rstrip(". ")
    if safe in ("", ".", ".."):
        raise ValueError("profile name must contain valid filename characters")
    return safe


def _target_path(directory: Path, name: str) -> Path:
    base = _safe_filename(name)
    candidate = directory / f"{base}.toml"
    index = 2
    while candidate.exists():
        if _stored_name(candidate) == name:
            return candidate
        candidate = directory / f"{base}-{index}.toml"
        index += 1
    return candidate


def _write_profile(target: Path, name: str, options: PlanOptions) -> None:
    lines = [
        f"name = {_toml_string(name)}",
        f"destination = {_toml_string(options.destination)}",
        f"quality = {_toml_string(options.quality)}",
        f"container = {_toml_string(options.container)}",
    ]
    if options.max_height is not None:
        lines.append(f"max_height = {options.max_height}")
    if options.audio_languages is not None:
        lines.append(f"audio_languages = {_toml_list(options.audio_languages)}")
    if options.subtitle_languages is not None:
        lines.append(f"subtitle_languages = {_toml_list(options.subtitle_languages)}")
    payload = "\n".join(lines) + "\n"

    descriptor, temporary_name = tempfile.mkstemp(
        dir=target.parent, prefix=".profile-", suffix=".toml"
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
        temporary_path.replace(target)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _toml_list(values: frozenset[str]) -> str:
    return "[" + ", ".join(_toml_string(value) for value in sorted(values)) + "]"


def _toml_string(value: str) -> str:
    characters: list[str] = []
    for character in value:
        if character == '"':
            characters.append('\\"')
        elif character == "\\":
            characters.append("\\\\")
        elif character == "\n":
            characters.append("\\n")
        elif character == "\r":
            characters.append("\\r")
        elif character == "\t":
            characters.append("\\t")
        elif ord(character) > 0xFFFF:
            characters.append(f"\\U{ord(character):08X}")
        elif not 0x20 <= ord(character) <= 0x7E:
            characters.append(f"\\u{ord(character):04X}")
        else:
            characters.append(character)
    return f'"{"".join(characters)}"'
