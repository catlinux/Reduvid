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
    )

    save_profile("Mi perfil ñ 😀", options, directory)

    assert load_profile("Mi perfil ñ 😀", directory) == options
    assert list_profiles(directory) == ("Mi perfil ñ 😀",)
    assert any(directory.glob("*.toml"))


def test_none_and_empty_language_sets_survive(tmp_path: Path) -> None:
    directory = tmp_path / "profiles"
    save_profile("sin idiomas", PlanOptions(), directory)
    save_profile(
        "idiomas vacíos",
        PlanOptions(
            audio_languages=frozenset(),
            subtitle_languages=frozenset(),
        ),
        directory,
    )

    assert load_profile("sin idiomas", directory) == PlanOptions()
    assert load_profile("idiomas vacíos", directory).audio_languages == frozenset()
    assert load_profile("idiomas vacíos", directory).subtitle_languages == frozenset()


def test_sanitized_names_keep_the_real_name(tmp_path: Path) -> None:
    directory = tmp_path / "profiles"
    save_profile("a/b", PlanOptions(quality="high"), directory)
    save_profile("a:b", PlanOptions(quality="max_savings"), directory)

    assert set(list_profiles(directory)) == {"a/b", "a:b"}
    assert load_profile("a/b", directory).quality == "high"
    assert load_profile("a:b", directory).quality == "max_savings"

    files = sorted(directory.glob("*.toml"))
    assert len(files) == 2
    assert all("/" not in file.name and ":" not in file.name for file in files)


def test_list_profiles_is_sorted_and_empty_when_missing(tmp_path: Path) -> None:
    directory = tmp_path / "profiles"

    assert list_profiles(directory) == ()

    for name in ("zeta", "alfa", "beta"):
        save_profile(name, PlanOptions(), directory)

    assert list_profiles(directory) == ("alfa", "beta", "zeta")


def test_saving_the_same_name_replaces_the_profile(tmp_path: Path) -> None:
    directory = tmp_path / "profiles"
    save_profile("cine", PlanOptions(quality="high"), directory)
    save_profile("cine", PlanOptions(quality="max_savings", container="mp4"), directory)

    assert list_profiles(directory) == ("cine",)
    loaded = load_profile("cine", directory)
    assert loaded.quality == "max_savings"
    assert loaded.container == "mp4"
    assert len(list(directory.glob("*.toml"))) == 1


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


@pytest.mark.parametrize("name", ["", "   ", ".", "..."])
def test_empty_sanitized_name_is_rejected(name: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        save_profile(name, PlanOptions(), tmp_path / "profiles")


def test_profile_with_quotes_and_unicode_round_trips(tmp_path: Path) -> None:
    directory = tmp_path / "profiles"
    name = 'Perfil "cine" de vacances ñ'

    save_profile(name, PlanOptions(destination="archive"), directory)

    assert list_profiles(directory) == (name,)
    assert load_profile(name, directory).destination == "archive"


def test_default_directory_uses_platformdirs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(profile_store, "user_config_dir", lambda _app: str(tmp_path))

    save_profile("default", PlanOptions(), None)

    assert (tmp_path / "profiles").is_dir()
    assert list_profiles() == ("default",)


def test_no_temporary_files_are_left(tmp_path: Path) -> None:
    directory = tmp_path / "profiles"

    save_profile("atomic", PlanOptions(), directory)

    assert [file.name for file in directory.iterdir()] == ["atomic.toml"]
