# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Shared subprocess options for the windowed application."""

from __future__ import annotations

import subprocess
import sys
from typing import Any

_PROCESS_SET_INFORMATION = 0x0200
_PROCESS_POWER_THROTTLING = 4
_PROCESS_POWER_THROTTLING_CURRENT_VERSION = 1
_PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 0x1


def hidden_window_kwargs() -> dict[str, Any]:
    """Keep child processes from opening a console window on Windows.

    The packaged application runs without a console, so every child process
    would otherwise create its own console window.
    """
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def disable_power_throttling(pid: int) -> bool:
    """Opt a process out of Windows' EcoQoS so it can use the performance cores.

    Windows 11 treats a below-normal, windowless process as background work and, on
    hybrid CPUs, keeps it on the efficiency cores: an encode ran on 4 of 16 threads,
    three times slower. Lowering the priority stays; only the core restriction goes.
    Returns False outside Windows or when the call fails.
    """
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes

    class _PowerThrottlingState(ctypes.Structure):
        _fields_ = (
            ("Version", wintypes.ULONG),
            ("ControlMask", wintypes.ULONG),
            ("StateMask", wintypes.ULONG),
        )

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(_PROCESS_SET_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        # Controlling EXECUTION_SPEED with the state bit cleared means "never throttle".
        state = _PowerThrottlingState(
            _PROCESS_POWER_THROTTLING_CURRENT_VERSION,
            _PROCESS_POWER_THROTTLING_EXECUTION_SPEED,
            0,
        )
        return bool(
            kernel32.SetProcessInformation(
                handle, _PROCESS_POWER_THROTTLING, ctypes.byref(state), ctypes.sizeof(state)
            )
        )
    finally:
        kernel32.CloseHandle(handle)
