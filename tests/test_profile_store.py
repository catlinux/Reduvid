# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from pathlib import Path

import pytest

from reduvid.core import profile_store
from reduvid.core.plan import PlanOptions
from reduvid.core.profile_store import (
    delete_profile,
    list_profiles,
    load_profile,
    save_profile,
)


def test_full_options_round_trip(tmp_path: Path) -> None:
    directory = tmp_path / "profiles"
    options = PlanOptions(
        destination="modern",
        quality="high",
        container="mp4",
        max_height=720,
        audio_languages=frozenset({"en", "es"}),
        subtitle_languages=frozenset({"ca"}),
        one_audio_per_language=True,
        reduce_audio=True,
    )

    save_profile("Mi perfil ñ 😀", options, directory)

    assert load_profile("Mi perfil ñ 😀", directory) == options
    assert list_profiles(directory) == ("Mi perfil ñ 😀",)
    contents = next(directory.glob("*.toml")).read_text(encoding="utf-8")
    for key in (
        "name",
        "destination",
        "quality",
        "container",
        "max_height",
        "audio_languages",
        "subtitle_languages",
        "one_audio_per_language",
        "reduce_audio",
    ):
        assert f"{key} =" in contents
    assert "audio_tracks" not in contents


def test_track_indices_are_not_stored(tmp_path: Path) -> None:
    directory = tmp_path / "profiles"
    save_profile("pistas", PlanOptions(audio_tracks=frozenset({1, 3})), directory)

    assert load_profile("pistas", directory).audio_tracks is None


def test_windows_reserved_names_get_a_safe_file(tmp_path: Path) -> None:
    directory = tmp_path / "profiles"
    save_profile("CON", PlanOptions(quality="high"), directory)

    assert [path.name for path in directory.glob("*.toml")] == ["_CON.toml"]
    assert load_profile("CON", directory).quality == "high"


def test_none_and_empty_sets_survive(tmp_path: Path) -> None:
    directory = tmp_path / "profiles"
    save_profile("sin opciones", PlanOptions(), directory)
    empty = PlanOptions(
        audio_languages=frozenset(),
        subtitle_languages=frozenset(),
    )
    save_profile("conjuntos vacíos", empty, directory)

    assert load_profile("sin opciones", directory) == PlanOptions()
    assert load_profile("conjuntos vacíos", directory) == empty


def test_missing_and_invalid_fields_use_defaults(tmp_path: Path) -> None:
    directory = tmp_path / "profiles"
    directory.mkdir()
    (directory / "partial.toml").write_text(
        "\n".join(
            (
                'name = "partial"',
                "destination = 7",
                'quality = "high"',
                'container = "avi"',
                'max_height = "720"',
                'audio_languages = "en"',
                'subtitle_languages = ["ca", 3]',
                'audio_tracks = ["1"]',
                'one_audio_per_language = "yes"',
                "reduce_audio = 1",
                'unknown = "ignored"',
            )
        ),
        encoding="utf-8",
    )
    (directory / "minimal.toml").write_text('name = "minimal"\n', encoding="utf-8")

    assert load_profile("partial", directory) == PlanOptions(quality="high")
    assert load_profile("minimal", directory) == PlanOptions()


def test_unsafe_names_stay_inside_the_profiles_directory(tmp_path: Path) -> None:
    directory = tmp_path / "profiles"
    names = (
        "Con espacios ñ 😀",
        "a/b",
        "a:b",
        "perfil .. raro",
        "../fuera",
        ".oculto",
        "..",
    )
    for name in names:
        save_profile(name, PlanOptions(quality="high"), directory)

    assert set(list_profiles(directory)) == set(names)
    files = list(directory.glob("*.toml"))
    assert len(files) == len(names)
    assert all(file.parent == directory for file in files)
    assert all(
        "/" not in file.name and "\\" not in file.name and ":" not in file.name for file in files
    )
    assert all(load_profile(name, directory).quality == "high" for name in names)


@pytest.mark.parametrize("name", ["", "   ", "\t\n", ".", "..."])
def test_empty_or_reserved_names_are_rejected(name: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        save_profile(name, PlanOptions(), tmp_path / "profiles")


def test_saving_the_same_name_replaces_the_profile(tmp_path: Path) -> None:
    directory = tmp_path / "profiles"
    save_profile("cine", PlanOptions(quality="high"), directory)
    save_profile("cine", PlanOptions(quality="max_savings", container="mp4"), directory)

    assert list_profiles(directory) == ("cine",)
    loaded = load_profile("cine", directory)
    assert loaded.quality == "max_savings"
    assert loaded.container == "mp4"
    assert len(list(directory.glob("*.toml"))) == 1


def test_list_profiles_is_sorted_and_empty_when_missing(tmp_path: Path) -> None:
    directory = tmp_path / "profiles"

    assert list_profiles(directory) == ()

    for name in ("zeta", "alfa", "beta"):
        save_profile(name, PlanOptions(), directory)

    assert list_profiles(directory) == ("alfa", "beta", "zeta")


def test_missing_profile_raises_and_delete_is_idempotent(tmp_path: Path) -> None:
    directory = tmp_path / "profiles"

    with pytest.raises(FileNotFoundError):
        load_profile("missing", directory)
    delete_profile("missing", directory)
    delete_profile("missing", directory)


def test_delete_removes_only_the_named_profile(tmp_path: Path) -> None:
    directory = tmp_path / "profiles"
    save_profile("uno", PlanOptions(), directory)
    save_profile("dos", PlanOptions(), directory)

    delete_profile("uno", directory)

    assert list_profiles(directory) == ("dos",)


def test_profile_with_quotes_and_unicode_round_trips(tmp_path: Path) -> None:
    directory = tmp_path / "profiles"
    name = 'Perfil "cine" de vacances ñ'
    options = PlanOptions(destination="archive")

    save_profile(name, options, directory)

    assert list_profiles(directory) == (name,)
    assert load_profile(name, directory) == options


def test_default_directory_uses_platformdirs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(profile_store, "user_config_dir", lambda _app: str(tmp_path))

    save_profile("default", PlanOptions(), None)

    assert (tmp_path / "profiles").is_dir()
    assert list_profiles() == ("default",)
    assert load_profile("default") == PlanOptions()


def test_no_temporary_files_are_left(tmp_path: Path) -> None:
    directory = tmp_path / "profiles"

    save_profile("atomic", PlanOptions(), directory)

    assert [file.name for file in directory.iterdir()] == ["atomic.toml"]
