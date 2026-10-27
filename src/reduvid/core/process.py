# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Shared subprocess options for the windowed application."""

from __future__ import annotations

import subprocess
import sys
from typing import Any


def hidden_window_kwargs() -> dict[str, Any]:
    """Keep child processes from opening a console window on Windows.

    The packaged application runs without a console, so every child process
    would otherwise create its own console window.
    """
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}
