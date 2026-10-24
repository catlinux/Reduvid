# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Extract translatable strings and update the shipped catalogs."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from babel.messages.catalog import Catalog
from babel.messages.extract import extract_from_dir
from babel.messages.pofile import read_po, write_po

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "src" / "reduvid"
LOCALE_DIR = SOURCE_DIR / "locale"
LANGUAGES = ("ca", "es")
# A fixed date keeps the committed catalogs stable between extractions.
FIXED_DATE = datetime(2026, 10, 24, tzinfo=UTC)


def extract_catalog() -> Catalog:
    """Collect every ``_()`` and ``ngettext()`` message from the package."""
    catalog = Catalog(
        project="Reduvid",
        copyright_holder="Catlinux",
        msgid_bugs_address="https://github.com/catlinux/Reduvid/issues",
        creation_date=FIXED_DATE,
    )
    for filename, lineno, message, comments, context in extract_from_dir(
        str(SOURCE_DIR),
        method_map=[("**.py", "python")],
        keywords={"_": None, "ngettext": (1, 2)},
        strip_comment_tags=True,
    ):
        catalog.add(message, None, [(filename, lineno)], auto_comments=comments, context=context)
    return catalog


def write_pot(template: Catalog, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        write_po(handle, template, width=100, sort_output=True)


def update_catalogs(template: Catalog, locale_dir: Path) -> None:
    for language in LANGUAGES:
        po_path = locale_dir / language / "LC_MESSAGES" / "reduvid.po"
        with po_path.open("rb") as handle:
            catalog = read_po(handle, locale=language)
        catalog.update(template, update_creation_date=False)
        catalog.creation_date = FIXED_DATE
        catalog.revision_date = FIXED_DATE
        with po_path.open("wb") as handle:
            write_po(handle, catalog, width=100, sort_output=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract and update Reduvid translations.")
    parser.add_argument("--pot", type=Path, default=LOCALE_DIR / "reduvid.pot")
    parser.add_argument("--no-update", action="store_true", help="Only write the .pot file.")
    arguments = parser.parse_args(argv)

    template = extract_catalog()
    write_pot(template, arguments.pot)
    if not arguments.no_update:
        update_catalogs(template, LOCALE_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
