# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Build collision-free output paths and finalize verified files."""

from __future__ import annotations

import os
import platform
import re
from pathlib import Path


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    suffix = path.suffix
    stem = path.stem
    index = 2
    while True:
        candidate = path.with_name(f"{stem} ({index}){suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def build_output_path(input_path: Path, destination_dir: Path, container_extension: str) -> Path:
    """Return the first available output path without creating it."""
    extension = container_extension.lstrip(".")
    base = destination_dir / f"{input_path.stem}_reduvid.{extension}"
    return _unique_path(base)


def build_temp_path(output_path: Path) -> Path:
    """Return an available temporary path corresponding to an output path."""
    stem = re.sub(r"_reduvid(?: \(\d+\))?$", "", output_path.stem)
    base = output_path.with_name(f".{stem}.reduvid-tmp{output_path.suffix}")
    return _unique_path(base)


def finalize_output(temp_path: Path, output_path: Path) -> None:
    """Move a verified temporary file into place without replacing a file."""
    if platform.system() == "Windows":
        # Windows os.rename fails when the destination exists.
        os.rename(temp_path, output_path)  # noqa: PTH104
    else:
        # POSIX link creation is atomic and fails instead of replacing the destination.
        os.link(temp_path, output_path)
        temp_path.unlink()
