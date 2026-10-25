# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Build the Windows onedir package with PyInstaller."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "packaging" / "windows" / "reduvid.spec"


def main() -> int:
    translations = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "scripts" / "compile_translations.py")],
        cwd=ROOT,
        check=False,
    )
    if translations.returncode != 0:
        return translations.returncode

    build = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "PyInstaller",
            str(SPEC),
            "--distpath",
            str(ROOT / "dist" / "windows"),
            "--workpath",
            str(ROOT / "build" / "windows"),
            "--noconfirm",
        ],
        cwd=ROOT,
        check=False,
    )
    return build.returncode


if __name__ == "__main__":
    raise SystemExit(main())
