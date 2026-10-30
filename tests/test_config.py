# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

import tomllib
from pathlib import Path

import pytest

from reduvid.core import config as config_module
from reduvid.core.config import Config, config_path, load_config, save_config


def test_missing_file_returns_defaults(tmp_path: Path) -> None:
    loaded, invalid = load_config(tmp_path / "missing.toml")

    assert loaded == Config()
    assert loaded.hw_decode is True
    assert loaded.check_updates is True
    assert loaded.updates_notice_seen is False
    assert invalid == ()


def test_round_trip_keeps_spaces_accents_and_quotes(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "config.toml"
    output_dir = tmp_path / 'Mis vídeos "finales"' / "còpia"
    original = Config(
        ffmpeg_path=tmp_path / "Program Files" / "ffmpeg.exe",
        language="ca",
        theme="riso",
        color_mode="dark",
        ui_mode="advanced",
        reduce_motion=True,
        output_dir=output_dir,
        destination="archive",
        quality="max_savings",
        container="mp4",
        hw_decode=False,
        check_updates=False,
        updates_notice_seen=True,
        last_run_version="9.8.7",
    )

    save_config(original, target)

    loaded, invalid = load_config(target)
    assert loaded == original
    assert invalid == ()


def test_save_escapes_special_characters(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    output_dir = Path('ruta con "comillas" i \\ barra i ó')

    save_config(Config(output_dir=output_dir), target)

    contents = target.read_text(encoding="utf-8")
    assert '"comillas"' not in contents
    assert "\\u00F3" in contents
    assert load_config(target)[0].output_dir == output_dir


def test_unknown_keys_are_ignored_and_invalid_keys_reported(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text(
        "\n".join(
            (
                "theme = 3",
                "language = 'fr'",
                "reduce_motion = 'yes'",
                "unknown_key = 1",
                "[unknown_section]",
                "value = 'ignored'",
            )
        ),
        encoding="utf-8",
    )

    loaded, invalid = load_config(target)

    assert loaded == Config()
    assert set(invalid) == {"theme", "language", "reduce_motion"}


def test_legacy_destination_is_migrated(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text(
        'destination = "jellyfin"\ncontainer = "mkv"\n',
        encoding="utf-8",
    )

    loaded, invalid = load_config(target)

    assert loaded.destination == "cinecat"
    # The old default "mkv" goes back to automatic, which is MP4 for Cinecat.
    assert loaded.container is None
    assert invalid == ()


def test_container_is_kept_when_not_migrating(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text('destination = "cinecat"\ncontainer = "mkv"\n', encoding="utf-8")

    loaded, _invalid = load_config(target)

    assert loaded.container == "mkv"


def test_automatic_container_is_none_and_is_not_saved(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"

    save_config(Config(), target)

    loaded, invalid = load_config(target)
    assert loaded.container is None
    assert invalid == ()
    assert "container" not in target.read_text(encoding="utf-8")


def test_invalid_container_falls_back_to_automatic(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text('container = "avi"\n', encoding="utf-8")

    loaded, invalid = load_config(target)

    assert loaded.container is None
    assert invalid == ("container",)


def test_hw_decode_can_be_disabled_in_toml(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text("hw_decode = false\n", encoding="utf-8")

    loaded, invalid = load_config(target)

    assert loaded.hw_decode is False
    assert invalid == ()


def test_invalid_hw_decode_is_reported_and_uses_the_default(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text("hw_decode = 'yes'\n", encoding="utf-8")

    loaded, invalid = load_config(target)

    assert loaded.hw_decode is True
    assert invalid == ("hw_decode",)


def test_update_flags_can_be_disabled_in_toml(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text(
        "check_updates = false\nupdates_notice_seen = true\n",
        encoding="utf-8",
    )

    loaded, invalid = load_config(target)

    assert loaded.check_updates is False
    assert loaded.updates_notice_seen is True
    assert invalid == ()


def test_last_run_version_is_saved_and_loaded(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text('last_run_version = "1.2.3"\n', encoding="utf-8")

    loaded, invalid = load_config(target)

    assert loaded.last_run_version == "1.2.3"
    assert invalid == ()

    save_config(loaded, target)
    loaded_again, invalid_again = load_config(target)
    assert loaded_again.last_run_version == "1.2.3"
    assert invalid_again == ()


def test_invalid_last_run_version_is_reported_and_ignored(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text('last_run_version = "not-a-version"\n', encoding="utf-8")

    loaded, invalid = load_config(target)

    assert loaded.last_run_version is None
    assert invalid == ("last_run_version",)


def test_invalid_update_flags_are_reported_and_use_defaults(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text(
        "check_updates = 'no'\nupdates_notice_seen = 1\n",
        encoding="utf-8",
    )

    loaded, invalid = load_config(target)

    assert loaded.check_updates is True
    assert loaded.updates_notice_seen is False
    assert loaded.last_run_version is None
    assert set(invalid) == {"check_updates", "updates_notice_seen"}


def test_ffmpeg_path_is_accepted_at_root_and_in_section(tmp_path: Path) -> None:
    root_target = tmp_path / "root.toml"
    root_target.write_text("ffmpeg_path = 'C:/ffmpeg/bin/ffmpeg.exe'\n", encoding="utf-8")
    section_target = tmp_path / "section.toml"
    section_target.write_text("[ffmpeg]\npath = 'C:/ffmpeg/bin/ffmpeg.exe'\n", encoding="utf-8")

    root_config, root_invalid = load_config(root_target)
    section_config, section_invalid = load_config(section_target)

    assert root_config.ffmpeg_path == Path("C:/ffmpeg/bin/ffmpeg.exe")
    assert section_config.ffmpeg_path == root_config.ffmpeg_path
    assert root_invalid == section_invalid == ()


def test_invalid_ffmpeg_path_is_reported(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text("ffmpeg_path = 4\n", encoding="utf-8")

    loaded, invalid = load_config(target)

    assert loaded.ffmpeg_path is None
    assert invalid == ("ffmpeg_path",)


def test_save_overwrites_previous_configuration(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    save_config(Config(theme="riso"), target)
    save_config(Config(theme="cinta", reduce_motion=True), target)

    loaded, invalid = load_config(target)

    assert loaded.theme == "cinta"
    assert loaded.reduce_motion is True
    assert invalid == ()


def test_config_path_uses_the_platform_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(config_module, "user_config_dir", lambda _app: str(tmp_path))

    assert config_path() == tmp_path / "config.toml"


def test_malformed_file_raises(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text("theme = [\n", encoding="utf-8")

    with pytest.raises(tomllib.TOMLDecodeError):
        load_config(target)
