# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""The application exposes the project icon for its windows."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from reduvid.gui.app import application_icon


def test_application_icon_loads(qapp) -> None:
    icon = application_icon()

    assert not icon.isNull()
    assert icon.availableSizes()
