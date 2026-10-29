# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Tests for the release-notes extraction script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "release_notes.py"
CHANGELOG = """# Changelog

## [Unreleased]

## [1.2.3] - 2026-01-02

### Added

- First change.
- Second change.

## [1.2.2] - 2026-01-01

- Old change.
"""


def run(version: str, changelog: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), version, "--changelog", str(changelog)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_release_notes_are_extracted_with_crlf(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_bytes(CHANGELOG.replace("\n", "\r\n").encode("utf-8"))

    result = run("1.2.3", changelog)

    assert result.returncode == 0
    assert result.stdout == "### Added\n\n- First change.\n- Second change.\n"
    assert result.stderr == ""


def test_missing_version_fails_with_a_clear_message(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")

    result = run("9.9.9", changelog)

    assert result.returncode == 1
    assert "9.9.9" in result.stderr
    assert result.stdout == ""
