# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Qt must run without a display in tests."""

from __future__ import annotations

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest


@pytest.fixture(scope="session")
def qapp():
    """Provide one offscreen QApplication for the whole session."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    yield application


@pytest.fixture(autouse=True)
def english_language():
    """Keep user-facing strings deterministic in GUI tests."""
    from reduvid.i18n import setup_language

    setup_language("en")
    yield
    setup_language("en")
