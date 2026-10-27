# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Named PlanOptions profiles stored as individual TOML files."""

from __future__ import annotations

import os
import re
import tempfile
import tomllib
from pathlib import Path
from typing import Literal, cast

from platformdirs import user_config_dir

from reduvid.core.plan import PlanOptions

_UNSAFE_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_DESTINATIONS = ("cinecat", "modern", "archive")
_QUALITIES = ("high", "balanced", "max_savings")
_CONTAINERS = ("mkv", "mp4")
_WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)


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
    raw_destination = raw.get("destination")
    destination = (
        "cinecat"
        if raw_destination == "jellyfin"
        else _string_choice(raw, "destination", _DESTINATIONS, "cinecat")
    )
    quality = _string_choice(raw, "quality", _QUALITIES, "balanced")
    raw_container = raw.get("container")
    if raw_destination == "jellyfin" and raw_container == "mkv":
        # Jellyfin profiles stored the old "mkv" default; Cinecat needs the automatic MP4.
        raw_container = None
    container: Literal["mkv", "mp4"] | None = (
        cast(Literal["mkv", "mp4"], raw_container) if raw_container in _CONTAINERS else None
    )
    return PlanOptions(
        destination=destination,
        quality=quality,
        container=container,
        max_height=_optional_int(raw.get("max_height")),
        audio_languages=_string_set(raw.get("audio_languages")),
        subtitle_languages=_string_set(raw.get("subtitle_languages")),
        one_audio_per_language=_boolean(raw.get("one_audio_per_language")),
        reduce_audio=_boolean(raw.get("reduce_audio")),
    )


def _string_choice(raw: dict[str, object], key: str, choices: tuple[str, ...], default: str) -> str:
    value = raw.get(key)
    return value if isinstance(value, str) and value in choices else default


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _string_set(value: object) -> frozenset[str] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return frozenset(value)


def _boolean(value: object) -> bool:
    return value if isinstance(value, bool) else False


def _safe_filename(name: str) -> str:
    raw = _UNSAFE_FILENAME.sub("_", name)
    safe = raw.strip().strip(". ")
    if safe == "" and raw.strip() == "..":
        safe = "profile"
    if safe in ("", ".", ".."):
        raise ValueError("profile name must contain valid filename characters")
    if safe.split(".")[0].upper() in _WINDOWS_RESERVED:
        safe = f"_{safe}"
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
    ]
    if options.container is not None:
        lines.append(f"container = {_toml_string(options.container)}")
    if options.max_height is not None:
        lines.append(f"max_height = {options.max_height}")
    if options.audio_languages is not None:
        lines.append(f"audio_languages = {_toml_string_set(options.audio_languages)}")
    if options.subtitle_languages is not None:
        lines.append(f"subtitle_languages = {_toml_string_set(options.subtitle_languages)}")
    # audio_tracks is left out: stream indices belong to one file and would pick the
    # wrong tracks in the other videos a profile is applied to.
    lines.append(
        f"one_audio_per_language = {'true' if options.one_audio_per_language else 'false'}"
    )
    lines.append(f"reduce_audio = {'true' if options.reduce_audio else 'false'}")
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


def _toml_string_set(values: frozenset[str]) -> str:
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
