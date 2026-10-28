# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QScrollArea

from reduvid.gui.queue_panel import QueuePanel


def test_queue_items_live_in_a_scroll_area(qapp) -> None:
    panel = QueuePanel()
    panel.resize(300, 300)
    panel.show()
    for number in range(8):
        panel._ensure_item(Path(f"/videos/película-con-un-nombre-largo-{number}.mkv"))
    qapp.processEvents()

    scroll = panel.findChild(QScrollArea, "queueScroll")
    assert scroll is not None
    assert scroll.widget() is panel.items_container
    assert scroll.widget().minimumSizeHint().height() > scroll.viewport().height()
    panel.reset()
    panel._ensure_item(Path("/videos/uno.mkv"))
    assert panel.items_layout.count() == 2
