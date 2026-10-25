# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Theme-aware progress bar with the motif of each design direction."""

from __future__ import annotations

import tomllib
from contextlib import suppress

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPaintEvent, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from reduvid.core.config import load_config
from reduvid.gui.theme.active import active_tokens
from reduvid.gui.theme.tokens import ThemeTokens
from reduvid.gui.widgets.motifs import (
    draw_fold_fill,
    draw_hatched_track,
    draw_mechanical_counter,
    draw_origami_cat,
    draw_tape_reels,
    draw_tape_stripe,
    primary_family,
)


def _configured_reduce_motion() -> bool:
    try:
        config, _invalid = load_config()
    except (OSError, tomllib.TOMLDecodeError):
        return False
    return config.reduce_motion


def _theme_kind(tokens: ThemeTokens) -> str:
    if tokens.fold is not None:
        return "plegat"
    if tokens.accent3 is not None:
        return "cinta"
    return "riso"


class ThemedProgressBar(QWidget):
    """Progress bar painted by hand with the active theme's motif."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        tokens: ThemeTokens | None = None,
        reduce_motion: bool | None = None,
    ) -> None:
        super().__init__(parent)
        self._minimum = 0
        self._maximum = 100
        self._value = 0
        self._tokens = tokens
        self._reduce_motion = (
            _configured_reduce_motion() if reduce_motion is None else reduce_motion
        )
        self.setMinimumHeight(18)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    @property
    def tokens(self) -> ThemeTokens:
        return self._tokens if self._tokens is not None else active_tokens()

    def set_theme_tokens(self, tokens: ThemeTokens) -> None:
        self._tokens = tokens
        self.update()

    @property
    def reduce_motion(self) -> bool:
        return self._reduce_motion

    def set_reduce_motion(self, reduce_motion: bool) -> None:
        self._reduce_motion = reduce_motion
        self.update()

    def setRange(self, minimum: int, maximum: int) -> None:
        if maximum < minimum:
            maximum = minimum
        self._minimum = minimum
        self._maximum = maximum
        self._value = min(max(self._value, minimum), maximum)
        self.update()

    def minimum(self) -> int:
        return self._minimum

    def maximum(self) -> int:
        return self._maximum

    def value(self) -> int:
        return self._value

    def setValue(self, value: int) -> None:
        clamped = min(max(int(value), self._minimum), self._maximum)
        if clamped != self._value:
            self._value = clamped
            self.update()

    def sizeHint(self) -> QSize:
        return QSize(140, 18)

    def _fraction(self) -> float:
        span = self._maximum - self._minimum
        if span <= 0:
            return 0.0
        return min(max((self._value - self._minimum) / span, 0.0), 1.0)

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        tokens = self.tokens
        kind = _theme_kind(tokens)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = float(tokens.radius)
        fraction = self._fraction()

        if kind == "riso":
            draw_hatched_track(painter, rect, tokens)
        else:
            painter.setPen(QPen(QColor(tokens.line), tokens.border_width))
            painter.setBrush(QColor(tokens.track))
            painter.drawRoundedRect(rect, radius, radius)

        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        painter.save()
        painter.setClipPath(clip)
        if kind == "plegat":
            draw_fold_fill(painter, rect, fraction, tokens)
            if fraction > 0.02:
                cat_width = max(10.0, rect.height() * 0.8)
                cat_left = rect.left() + rect.width() * fraction - cat_width - 2
                cat_rect = QRectF(
                    max(rect.left() + 2, cat_left),
                    rect.top() + 2,
                    cat_width,
                    rect.height() - 4,
                )
                draw_origami_cat(painter, cat_rect, fraction, tokens)
        elif kind == "riso":
            if fraction > 0:
                painter.fillRect(
                    QRectF(rect.left(), rect.top(), rect.width() * fraction, rect.height()),
                    QColor(tokens.accent),
                )
            if fraction > 0.02:
                cat_width = max(10.0, rect.height() * 0.75)
                cat_left = rect.left() + rect.width() * fraction - cat_width - 2
                cat_rect = QRectF(
                    max(rect.left() + 2, cat_left),
                    rect.top() + 2,
                    cat_width,
                    rect.height() - 4,
                )
                draw_origami_cat(painter, cat_rect, fraction, tokens)
            # Keep the percentage clear of the cat, which rides the fill edge.
            percent_rect = QRectF(rect).adjusted(0, 0, -rect.width() * 0.08, 0)
            painter.setFont(_riso_percent_font(tokens, fraction, rect.height()))
            painter.setPen(QColor(tokens.text))
            painter.drawText(
                percent_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{round(fraction * 100):d}%",
            )
        else:
            draw_tape_stripe(painter, rect, tokens)
            draw_tape_reels(painter, rect, fraction, tokens)
            counter = QRectF(
                rect.center().x() - min(36.0, rect.width() * 0.22),
                rect.top() + rect.height() * 0.28,
                min(72.0, rect.width() * 0.44),
                rect.height() * 0.6,
            )
            draw_mechanical_counter(painter, counter, f"{round(fraction * 100):03d}", tokens)
        painter.restore()

        painter.setPen(QPen(QColor(tokens.line), tokens.border_width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, radius, radius)
        painter.end()


def _riso_percent_font(tokens: ThemeTokens, fraction: float, height: float) -> QFont:
    font = QFont(primary_family(tokens.display))
    font.setPointSizeF(max(6.0, height * 0.5))
    font.setWeight(QFont.Weight.Bold)
    # Archivo is a variable font; silently keep a fixed width if the axis is
    # unavailable on this Qt build or font.
    with suppress(AttributeError, TypeError, ValueError):
        font.setVariableAxis(QFont.Tag("wdth"), 125 - 63 * fraction)
    return font
