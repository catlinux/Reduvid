# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Persistent user configuration with a minimal TOML writer."""

from __future__ import annotations

import os
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from platformdirs import user_config_dir

Language = Literal["ca", "es", "en"]
Theme = Literal["plegat", "riso", "cinta"]
ColorMode = Literal["system", "light", "dark"]
UiMode = Literal["wizard", "advanced"]
Destination = Literal["jellyfin", "modern", "archive"]
Quality = Literal["high", "balanced", "max_savings"]
Container = Literal["mkv", "mp4"]

_CONFIG_FILENAME = "config.toml"


@dataclass(frozen=True)
class Config:
    """User preferences shared by the CLI and the graphical interface."""

    ffmpeg_path: Path | None = None
    language: Language | None = None
    theme: Theme = "plegat"
    color_mode: ColorMode = "system"
    ui_mode: UiMode = "wizard"
    reduce_motion: bool = False
    output_dir: Path | None = None
    destination: Destination = "jellyfin"
    quality: Quality = "balanced"
    container: Container = "mkv"


def config_path() -> Path:
    """Return the location of the user configuration file."""
    return Path(user_config_dir("reduvid")) / _CONFIG_FILENAME


def load_config(path: Path | None = None) -> tuple[Config, tuple[str, ...]]:
    """Read the configuration, returning it with the invalid keys that were ignored.

    A missing file yields the defaults. Unreadable or malformed files propagate
    ``OSError`` or ``tomllib.TOMLDecodeError`` so callers can report them.
    """
    config_file = path if path is not None else config_path()
    try:
        with config_file.open("rb") as handle:
            raw: dict[str, object] = tomllib.load(handle)
    except (FileNotFoundError, NotADirectoryError, IsADirectoryError):
        return Config(), ()

    invalid: list[str] = []

    ffmpeg_path: Path | None = None
    configured_path: object = raw.get("ffmpeg_path")
    ffmpeg_section = raw.get("ffmpeg")
    section_path: object = ffmpeg_section.get("path") if isinstance(ffmpeg_section, dict) else None
    if not isinstance(configured_path, str) or not configured_path.strip():
        configured_path = section_path
    if isinstance(configured_path, str) and configured_path.strip():
        ffmpeg_path = Path(configured_path).expanduser()
    elif "ffmpeg_path" in raw or section_path is not None:
        invalid.append("ffmpeg_path")

    language: Language | None = None
    raw_language = raw.get("language")
    if raw_language is not None:
        if raw_language in ("ca", "es", "en"):
            language = raw_language
        else:
            invalid.append("language")

    theme: Theme = "plegat"
    raw_theme = raw.get("theme")
    if raw_theme is not None:
        if raw_theme in ("plegat", "riso", "cinta"):
            theme = raw_theme
        else:
            invalid.append("theme")

    color_mode: ColorMode = "system"
    raw_color_mode = raw.get("color_mode")
    if raw_color_mode is not None:
        if raw_color_mode in ("system", "light", "dark"):
            color_mode = raw_color_mode
        else:
            invalid.append("color_mode")

    ui_mode: UiMode = "wizard"
    raw_ui_mode = raw.get("ui_mode")
    if raw_ui_mode is not None:
        if raw_ui_mode in ("wizard", "advanced"):
            ui_mode = raw_ui_mode
        else:
            invalid.append("ui_mode")

    reduce_motion = False
    raw_reduce_motion = raw.get("reduce_motion")
    if raw_reduce_motion is not None:
        if isinstance(raw_reduce_motion, bool):
            reduce_motion = raw_reduce_motion
        else:
            invalid.append("reduce_motion")

    output_dir: Path | None = None
    raw_output_dir = raw.get("output_dir")
    if raw_output_dir is not None:
        if isinstance(raw_output_dir, str) and raw_output_dir.strip():
            output_dir = Path(raw_output_dir).expanduser()
        else:
            invalid.append("output_dir")

    destination: Destination = "jellyfin"
    raw_destination = raw.get("destination")
    if raw_destination is not None:
        if raw_destination in ("jellyfin", "modern", "archive"):
            destination = raw_destination
        else:
            invalid.append("destination")

    quality: Quality = "balanced"
    raw_quality = raw.get("quality")
    if raw_quality is not None:
        if raw_quality in ("high", "balanced", "max_savings"):
            quality = raw_quality
        else:
            invalid.append("quality")

    container: Container = "mkv"
    raw_container = raw.get("container")
    if raw_container is not None:
        if raw_container in ("mkv", "mp4"):
            container = raw_container
        else:
            invalid.append("container")

    config = Config(
        ffmpeg_path=ffmpeg_path,
        language=language,
        theme=theme,
        color_mode=color_mode,
        ui_mode=ui_mode,
        reduce_motion=reduce_motion,
        output_dir=output_dir,
        destination=destination,
        quality=quality,
        container=container,
    )
    return config, tuple(invalid)


def save_config(config: Config, path: Path | None = None) -> None:
    """Write the configuration atomically, creating its directory if needed."""
    config_file = path if path is not None else config_path()
    config_file.parent.mkdir(parents=True, exist_ok=True)

    entries: list[tuple[str, str]] = []
    if config.ffmpeg_path is not None:
        entries.append(("ffmpeg_path", _toml_string(str(config.ffmpeg_path))))
    if config.language is not None:
        entries.append(("language", _toml_string(config.language)))
    entries.append(("theme", _toml_string(config.theme)))
    entries.append(("color_mode", _toml_string(config.color_mode)))
    entries.append(("ui_mode", _toml_string(config.ui_mode)))
    entries.append(("reduce_motion", "true" if config.reduce_motion else "false"))
    if config.output_dir is not None:
        entries.append(("output_dir", _toml_string(str(config.output_dir))))
    entries.append(("destination", _toml_string(config.destination)))
    entries.append(("quality", _toml_string(config.quality)))
    entries.append(("container", _toml_string(config.container)))
    payload = "".join(f"{key} = {value}\n" for key, value in entries)

    descriptor, temporary_name = tempfile.mkstemp(
        dir=config_file.parent, prefix=".config-", suffix=".toml"
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
        temporary_path.replace(config_file)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _toml_string(value: str) -> str:
    """Quote *value* as a TOML basic string, escaping anything non-printable."""
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
