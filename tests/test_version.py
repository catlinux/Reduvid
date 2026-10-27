# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from reduvid import __version__


def test_version() -> None:
    assert __version__ == "0.6.1"
