# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Print the release notes for one version from CHANGELOG.md."""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CHANGELOG = ROOT / "CHANGELOG.md"


def extract_notes(changelog: str, version: str) -> str | None:
    """Return the section body for *version*, without its heading."""
    lines = changelog.splitlines()
    heading = re.compile(rf"^## \[{re.escape(version)}\] - ")
    next_section = re.compile(r"^## \[")
    start = next((index for index, line in enumerate(lines) if heading.match(line)), None)
    if start is None:
        return None

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if next_section.match(lines[index]):
            end = index
            break

    body = lines[start + 1 : end]
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()
    return "\n".join(body)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print release notes from a changelog.")
    parser.add_argument("version", help="version to extract, for example 1.2.3")
    parser.add_argument(
        "--changelog",
        type=Path,
        default=DEFAULT_CHANGELOG,
        help="changelog file (default: the repository CHANGELOG.md)",
    )
    arguments = parser.parse_args(argv)
    try:
        text = arguments.changelog.read_text(encoding="utf-8")
    except OSError as error:
        print(f"Could not read {arguments.changelog}: {error}", file=sys.stderr)
        return 1

    body = extract_notes(text, arguments.version)
    if body is None:
        print(
            f"Version {arguments.version} was not found in {arguments.changelog}.",
            file=sys.stderr,
        )
        return 1
    if body:
        print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
