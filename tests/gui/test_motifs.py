# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Motif painting tests for the six theme sets."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPixmap

from reduvid.gui.theme.active import set_active_tokens
from reduvid.gui.theme.tokens import THEMES
from reduvid.gui.widgets.motifs import (
    draw_fold_corner,
    draw_fold_fill,
    draw_hatched_track,
    draw_mechanical_counter,
    draw_offset_shadow,
    draw_origami_cat,
    draw_tape_reels,
    draw_tape_stripe,
)
from reduvid.gui.widgets.option_card import OptionCard


@pytest.mark.parametrize("key", sorted(THEMES))
def test_all_motifs_paint_without_errors(key: tuple[str, str], qapp) -> None:
    tokens = THEMES[key]
    pixmap = QPixmap(320, 140)
    pixmap.fill()
    painter = QPainter(pixmap)
    rect = QRectF(10, 10, 300, 120)
    try:
        draw_fold_corner(painter, rect, tokens)
        draw_offset_shadow(painter, rect, tokens)
        draw_hatched_track(painter, rect, tokens)
        draw_tape_stripe(painter, rect, tokens)
        draw_mechanical_counter(painter, QRectF(80, 40, 120, 40), "042", tokens)
        for progress in (0.0, 0.25, 0.5, 0.75, 1.0):
            draw_fold_fill(painter, rect, progress, tokens)
            draw_origami_cat(painter, QRectF(250, 20, 40, 40), progress, tokens)
            draw_tape_reels(painter, rect, progress, tokens)
    finally:
        painter.end()
    assert not pixmap.isNull()


@pytest.mark.parametrize("key", sorted(THEMES))
def test_option_card_paints_checked_and_unchecked(key: tuple[str, str], qapp) -> None:
    tokens = THEMES[key]
    set_active_tokens(tokens)
    card = OptionCard("Jellyfin", "Recommended", "A description")
    card.resize(260, 90)
    try:
        card.grab()
        card.setChecked(True)
        card.grab()
        card.setChecked(False)
        card.grab()
    finally:
        card.deleteLater()
        set_active_tokens(THEMES[("plegat", "light")])
