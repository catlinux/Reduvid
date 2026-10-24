# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po

from reduvid import i18n
from reduvid.core.plan import Warning
from reduvid.messages import error_text, warning_text

ROOT = Path(__file__).resolve().parent.parent
LOCALE_DIR = ROOT / "src" / "reduvid" / "locale"
WARNING_PARAMS: dict[str, dict[str, object]] = {
    "resolution_reduced_4k_to_1080p": {"stream_index": 0},
    "hdr_converted_to_sdr": {"stream_index": 0},
    "hdr_tonemap_unavailable": {"stream_index": 0, "blocking": True},
    "audio_recoded": {"stream_index": 1, "codec": "aac"},
    "image_subtitle_burn_in": {"stream_index": 2},
    "image_subtitle_dropped_mp4": {"stream_index": 2},
    "audio_filter_kept_all": {},
}
ERROR_CODES = (
    "no_space",
    "corrupt_input",
    "missing_codec",
    "permission_denied",
    "cancelled",
    "verification_failed",
    "probe_failed",
    "unknown",
)


@pytest.fixture(scope="module")
def compiled_catalogs(tmp_path_factory: pytest.TempPathFactory) -> Path:
    target = tmp_path_factory.mktemp("locale")
    for language in ("ca", "es"):
        po_path = LOCALE_DIR / language / "LC_MESSAGES" / "reduvid.po"
        with po_path.open("rb") as po_file:
            catalog = read_po(po_file)
        mo_path = target / language / "LC_MESSAGES" / "reduvid.mo"
        mo_path.parent.mkdir(parents=True)
        with mo_path.open("wb") as mo_file:
            write_mo(mo_file, catalog)
    return target


@pytest.fixture(autouse=True)
def active_catalogs(monkeypatch: pytest.MonkeyPatch, compiled_catalogs: Path) -> Iterator[None]:
    monkeypatch.setattr(i18n, "LOCALE_DIR", compiled_catalogs)
    yield
    monkeypatch.undo()
    i18n.setup_language("en")


def english_warnings() -> dict[str, str]:
    i18n.setup_language("en")
    return {code: warning_text(Warning(code, params)) for code, params in WARNING_PARAMS.items()}


def english_errors() -> dict[str, str]:
    i18n.setup_language("en")
    return {code: error_text(code) for code in ERROR_CODES}


def test_translation_is_read_at_call_time() -> None:
    i18n.setup_language("ca")
    catalan = i18n._("File: {path}")
    i18n.setup_language("es")
    spanish = i18n._("File: {path}")
    i18n.setup_language("en")

    assert catalan == "Fitxer: {path}"
    assert spanish == "Archivo: {path}"
    assert i18n._("File: {path}") == "File: {path}"


def test_every_warning_has_catalan_and_spanish_text() -> None:
    english = english_warnings()

    for language in ("ca", "es"):
        i18n.setup_language(language)
        for code, params in WARNING_PARAMS.items():
            text = warning_text(Warning(code, params))
            assert text
            assert text != english[code]


def test_every_error_code_has_catalan_and_spanish_text() -> None:
    english = english_errors()

    for language in ("ca", "es"):
        i18n.setup_language(language)
        for code in ERROR_CODES:
            text = error_text(code)
            assert text
            assert text != english[code]


def test_unknown_error_code_uses_the_unknown_text() -> None:
    i18n.setup_language("ca")

    assert error_text("not_a_real_code") == error_text("unknown")


def test_unknown_warning_code_is_reported() -> None:
    i18n.setup_language("ca")

    text = warning_text(Warning("not_a_real_code"))

    assert "not_a_real_code" in text
    assert text != warning_text(Warning("audio_filter_kept_all"))


def test_catalogs_have_no_untranslated_entries() -> None:
    for language in ("ca", "es"):
        po_path = LOCALE_DIR / language / "LC_MESSAGES" / "reduvid.po"
        with po_path.open("rb") as po_file:
            catalog = read_po(po_file)
        missing = [message.id for message in catalog if message.id and not message.string]
        fuzzy = [message.id for message in catalog if message.id and message.fuzzy]
        assert missing == []
        assert fuzzy == []


def test_pot_is_up_to_date(tmp_path: Path) -> None:
    extracted = tmp_path / "reduvid.pot"
    subprocess.run(
        [
            sys.executable,
            "scripts/extract_translations.py",
            "--pot",
            str(extracted),
            "--no-update",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )

    with (LOCALE_DIR / "reduvid.pot").open("rb") as pot_file:
        committed = read_po(pot_file)
    with extracted.open("rb") as pot_file:
        fresh = read_po(pot_file)

    committed_ids = {message.id for message in committed if message.id}
    fresh_ids = {message.id for message in fresh if message.id}
    assert committed_ids == fresh_ids
