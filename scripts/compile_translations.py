# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Compile gettext catalogs (``.po``) into binary catalogs (``.mo``)."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po

ROOT = Path(__file__).resolve().parent.parent
LOCALE_DIR = ROOT / "src" / "reduvid" / "locale"


def compile_catalog(po_path: Path) -> Path:
    """Compile one ``.po`` file beside itself and return the ``.mo`` path."""
    mo_path = po_path.with_suffix(".mo")
    with po_path.open("rb") as po_file:
        catalog = read_po(po_file)
    with mo_path.open("wb") as mo_file:
        write_mo(mo_file, catalog)
    return mo_path


def compile_translations(locale_dir: Path) -> list[Path]:
    """Compile every ``.po`` under ``<locale>/LC_MESSAGES``."""
    return [compile_catalog(po_path) for po_path in sorted(locale_dir.glob("*/LC_MESSAGES/*.po"))]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile Reduvid translations.")
    parser.add_argument("--locale-dir", type=Path, default=LOCALE_DIR)
    arguments = parser.parse_args(argv)

    for mo_path in compile_translations(arguments.locale_dir):
        print(mo_path.relative_to(arguments.locale_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
