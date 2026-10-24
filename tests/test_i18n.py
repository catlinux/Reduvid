# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

import locale
from collections.abc import Iterator
from pathlib import Path

import pytest

from reduvid import i18n


@pytest.fixture(autouse=True)
def restore_english(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    yield
    monkeypatch.undo()
    i18n.setup_language("en")


def clear_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(variable, raising=False)


def test_requested_language_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_environment(monkeypatch)
    monkeypatch.setenv("LANG", "fr_FR.UTF-8")

    assert i18n.setup_language("ca") == "ca"


def test_priority_list_in_language(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_environment(monkeypatch)
    monkeypatch.setattr(locale, "getlocale", lambda: (None, None))
    monkeypatch.setenv("LANGUAGE", "fr_FR:ca_ES.UTF-8")

    assert i18n.setup_language() == "ca"


def test_lc_all_takes_precedence_over_lang(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_environment(monkeypatch)
    monkeypatch.setattr(locale, "getlocale", lambda: (None, None))
    monkeypatch.setenv("LC_ALL", "es_ES.UTF-8")
    monkeypatch.setenv("LC_MESSAGES", "ca_ES.UTF-8")
    monkeypatch.setenv("LANG", "ca_ES.UTF-8")

    assert i18n.setup_language() == "es"


def test_locale_getlocale_is_the_last_source(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_environment(monkeypatch)
    monkeypatch.setattr(locale, "getlocale", lambda: ("es_ES", "cp1252"))

    assert i18n.setup_language() == "es"


def test_unsupported_system_language_falls_back_to_english(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_environment(monkeypatch)
    monkeypatch.setattr(locale, "getlocale", lambda: ("fr_FR", "UTF-8"))

    assert i18n.setup_language() == "en"


def test_unsupported_requested_language_falls_back_to_the_system(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_environment(monkeypatch)
    monkeypatch.setattr(locale, "getlocale", lambda: (None, None))
    monkeypatch.setenv("LANG", "ca_ES.UTF-8")

    assert i18n.setup_language("fr") == "ca"


def test_missing_catalog_keeps_the_msgid(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(i18n, "LOCALE_DIR", tmp_path)

    assert i18n.setup_language("ca") == "ca"
    assert i18n._("File: {path}") == "File: {path}"
    assert i18n.ngettext("{count} file", "{count} files", 2) == "{count} files"
