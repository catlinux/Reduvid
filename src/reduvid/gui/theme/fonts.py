# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Register the bundled font families with Qt exactly once."""

from __future__ import annotations

import warnings
from pathlib import Path

from PySide6.QtGui import QFontDatabase

FONTS_DIR = Path(__file__).resolve().parents[2] / "resources" / "fonts"

_loaded_fonts: dict[str, str] | None = None


def register_fonts() -> dict[str, str]:
    """Load every bundled ``.ttf`` and return the real family of each file.

    The result maps the font's path relative to ``resources/fonts`` to the
    family name reported by Qt. Calling it again returns the same mapping.
    """
    global _loaded_fonts
    if _loaded_fonts is not None:
        return dict(_loaded_fonts)

    loaded: dict[str, str] = {}
    for path in sorted(FONTS_DIR.rglob("*.ttf")):
        key = path.relative_to(FONTS_DIR).as_posix()
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id == -1:
            warnings.warn(f"Could not load font file: {key}", RuntimeWarning, stacklevel=2)
            loaded[key] = ""
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if not families:
            warnings.warn(f"Qt loaded no family from: {key}", RuntimeWarning, stacklevel=2)
            loaded[key] = ""
            continue
        loaded[key] = families[0]

    _loaded_fonts = loaded
    return dict(loaded)
