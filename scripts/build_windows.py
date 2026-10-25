# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Build the Windows onedir package and, when available, its Inno Setup installer."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "packaging" / "windows" / "reduvid.spec"
INSTALLER = ROOT / "packaging" / "windows" / "reduvid.iss"
VERSION_PATTERN = re.compile(r"^__version__\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)


def project_version() -> str:
    text = (ROOT / "src" / "reduvid" / "__init__.py").read_text(encoding="utf-8")
    match = VERSION_PATTERN.search(text)
    if match is None:
        raise ValueError("Could not read __version__ from src/reduvid/__init__.py")
    return match.group(1)


def build_package() -> int:
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


def build_installer() -> int:
    iscc = shutil.which("ISCC.exe") or shutil.which("iscc")
    if iscc is None:
        print(
            "Inno Setup (ISCC.exe) was not found on PATH; the onedir package is ready "
            "in dist/windows/Reduvid, but the installer was not generated. Install "
            "Inno Setup from https://jrsoftware.org/isdl.php and run this script again."
        )
        return 0

    try:
        version = project_version()
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1

    installer = subprocess.run(  # noqa: S603
        [iscc, f"/DMyAppVersion={version}", str(INSTALLER)],
        cwd=ROOT,
        check=False,
    )
    return installer.returncode


def main() -> int:
    package = build_package()
    if package != 0:
        return package
    return build_installer()


if __name__ == "__main__":
    raise SystemExit(main())
