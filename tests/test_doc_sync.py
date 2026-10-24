# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from pathlib import Path

from scripts.check_doc_sync import check


def test_matching_pair(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Uno\n## Dos\n", encoding="utf-8")
    (tmp_path / "README.en.md").write_text("# One\n## Two\n", encoding="utf-8")
    assert check(tmp_path) == []


def test_missing_pair(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Uno\n", encoding="utf-8")
    assert any("README.en.md" in error for error in check(tmp_path))


def test_different_heading_structure(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Uno\n## Dos\n", encoding="utf-8")
    (tmp_path / "README.en.md").write_text("# One\n### Two\n", encoding="utf-8")
    assert check(tmp_path)


def test_ignores_headings_in_fenced_code(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Uno\n```\n## ejemplo\n```\n", encoding="utf-8")
    (tmp_path / "README.en.md").write_text("# One\n```\n### sample\n```\n", encoding="utf-8")
    assert check(tmp_path) == []
