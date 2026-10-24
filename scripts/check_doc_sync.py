# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

import re
import sys
from pathlib import Path

HEADING = re.compile(r"^ {0,3}(#{1,6})(?:\s|$)")
ROOT_PAIRS = ("README", "CHANGELOG", "TODO", "CONTRIBUTING")


def _headings(path: Path) -> list[int]:
    levels: list[int] = []
    in_fence = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
        elif not in_fence:
            match = HEADING.match(line)
            if match:
                levels.append(len(match.group(1)))
    return levels


def check(root: Path) -> list[str]:
    errors: list[str] = []
    pairs: set[tuple[Path, Path]] = set()
    for path in root.glob("*.md"):
        if path.name.endswith(".en.md"):
            continue
        translated = path.with_name(f"{path.stem}.en.md")
        if translated.is_file():
            pairs.add((path, translated))
    for name in ROOT_PAIRS:
        source = root / f"{name}.md"
        translated = root / f"{name}.en.md"
        if source.is_file() and not translated.is_file():
            errors.append(f"{source.relative_to(root)}: falta {translated.relative_to(root)}")
        elif translated.is_file() and not source.is_file():
            errors.append(f"{translated.relative_to(root)}: falta {source.relative_to(root)}")
    spanish = root / "docs/es"
    if spanish.exists():
        for source in spanish.rglob("*.md"):
            translated = root / "docs/en" / source.relative_to(spanish)
            if translated.is_file():
                pairs.add((source, translated))
            else:
                errors.append(f"{source.relative_to(root)}: falta {translated.relative_to(root)}")
    english = root / "docs/en"
    if english.exists():
        for translated in english.rglob("*.md"):
            source = root / "docs/es" / translated.relative_to(english)
            if not source.is_file():
                errors.append(f"{translated.relative_to(root)}: falta {source.relative_to(root)}")
    for source, translated in sorted(pairs):
        if _headings(source) != _headings(translated):
            errors.append(
                f"{source.relative_to(root)} y {translated.relative_to(root)}: "
                "estructura de títulos distinta"
            )
    return errors


def main() -> int:
    errors = check(Path.cwd())
    for error in errors:
        print(error, file=sys.stderr)
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
