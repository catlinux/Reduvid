# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Translation support without Qt, shared by the CLI and the interface."""

from __future__ import annotations

import gettext
import locale
import os
import re
from pathlib import Path

DOMAIN = "reduvid"
LOCALE_DIR = Path(__file__).resolve().parent / "locale"
LANGUAGES = ("ca", "es", "en")
DEFAULT_LANGUAGE = "en"

_translation: gettext.NullTranslations = gettext.NullTranslations()


def setup_language(lang: str | None = None) -> str:
    """Activate the requested or system language and return the effective one.

    ``ca``, ``es`` and ``en`` are supported; anything else falls back to the
    system language and, when that is not supported either, to English.
    """
    global _translation
    effective = _effective_language(lang)
    _translation = gettext.translation(
        DOMAIN, localedir=str(LOCALE_DIR), languages=[effective], fallback=True
    )
    return effective


def _(message: str) -> str:
    """Translate *message* using the currently active catalog."""
    return _translation.gettext(message)


def ngettext(singular: str, plural: str, count: int) -> str:
    """Translate a plural message using the currently active catalog."""
    return _translation.ngettext(singular, plural, count)


def _effective_language(lang: str | None) -> str:
    if lang:
        requested = _language_codes(lang)
        if requested and requested[0] in LANGUAGES:
            return requested[0]
    return _system_language()


def _system_language() -> str:
    for variable in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        for code in _language_codes(os.environ.get(variable)):
            if code in LANGUAGES:
                return code
    system_locale = locale.getlocale()
    for code in _language_codes(system_locale[0] if system_locale else None):
        if code in LANGUAGES:
            return code
    return DEFAULT_LANGUAGE


def _language_codes(value: str | None) -> list[str]:
    """Extract two-letter language codes from a locale value or priority list."""
    if not value:
        return []
    codes: list[str] = []
    for item in value.split(":"):
        code = re.split(r"[._@]", item.strip(), maxsplit=1)[0].lower()
        if len(code) == 2 and code.isalpha():
            codes.append(code)
    return codes
