# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Pure painting helpers for the distinctive motif of each theme."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF

from reduvid.gui.theme.tokens import ThemeTokens


def primary_family(families: str) -> str:
    """Pick the first family from a CSS-style family list."""
    return families.split(",", 1)[0].strip().strip("\"'")


def draw_fold_corner(painter: QPainter, rect: QRectF, tokens: ThemeTokens) -> None:
    """Draw the folded paper corner of Plegat in the top-right corner."""
    if tokens.fold is None:
        return
    size = min(22.0, rect.width() / 4, rect.height() / 3)
    corner = QPolygonF(
        [
            QPointF(rect.right() - size, rect.top()),
            QPointF(rect.right(), rect.top()),
            QPointF(rect.right(), rect.top() + size),
        ]
    )
    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(tokens.fold))
    painter.drawPolygon(corner)
    painter.restore()


def draw_offset_shadow(painter: QPainter, rect: QRectF, tokens: ThemeTokens) -> None:
    """Approximate the Riso misregistered second ink along two card edges."""
    offset = max(2, tokens.border_width * 2)
    painter.save()
    painter.setPen(QPen(QColor(tokens.accent2), offset))
    radius = max(0.0, float(tokens.radius))
    painter.drawLine(
        QPointF(rect.left() + radius, rect.bottom() - offset / 2),
        QPointF(rect.right() - radius, rect.bottom() - offset / 2),
    )
    painter.drawLine(
        QPointF(rect.right() - offset / 2, rect.top() + radius),
        QPointF(rect.right() - offset / 2, rect.bottom() - radius),
    )
    painter.restore()


def draw_origami_cat(painter: QPainter, rect: QRectF, progress: float, tokens: ThemeTokens) -> None:
    """Draw a small folded-paper cat that folds down as progress grows."""
    if rect.width() <= 0 or rect.height() <= 0:
        return
    value = min(max(progress, 0.0), 1.0)
    width, height = rect.width(), rect.height()

    def point(x: float, y: float) -> QPointF:
        return QPointF(rect.left() + x * width, rect.top() + y * height)

    body = QPolygonF(
        [
            point(0.08, 0.86),
            point(0.50, 0.34 + 0.16 * value),
            point(0.92, 0.86),
        ]
    )
    head = QPolygonF(
        [
            point(0.50, 0.34 + 0.16 * value),
            point(0.34, 0.10),
            point(0.62, 0.04),
            point(0.70, 0.30 + 0.12 * value),
        ]
    )
    ear = QPolygonF([point(0.62, 0.04), point(0.66, -0.04), point(0.70, 0.08)])
    tail = QPolygonF([point(0.86, 0.86), point(0.98, 0.70), point(0.92, 0.90)])

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(tokens.fold or tokens.text), max(1, tokens.border_width)))
    painter.setBrush(QColor(tokens.text))
    painter.drawPolygon(body)
    painter.setBrush(QColor(tokens.accent2 if tokens.fold is not None else tokens.accent))
    painter.drawPolygon(head)
    painter.drawPolygon(ear)
    painter.drawPolygon(tail)
    painter.drawLine(point(0.50, 0.34 + 0.16 * value), point(0.44, 0.86))
    painter.restore()


def draw_hatched_track(painter: QPainter, rect: QRectF, tokens: ThemeTokens) -> None:
    """Fill the Riso track with a fine diagonal ink pattern."""
    if rect.width() <= 0 or rect.height() <= 0:
        return
    path = QPainterPath()
    path.addRoundedRect(rect, float(tokens.radius), float(tokens.radius))
    painter.save()
    painter.setClipPath(path)
    painter.fillPath(path, QColor(tokens.surface))
    painter.setPen(QPen(QColor(tokens.accent2), 1))
    spacing = max(4, tokens.border_width * 3)
    position = rect.left() - rect.height()
    while position < rect.right():
        painter.drawLine(
            QPointF(position, rect.bottom()),
            QPointF(position + rect.height(), rect.top()),
        )
        position += spacing
    painter.restore()


def draw_fold_fill(painter: QPainter, rect: QRectF, progress: float, tokens: ThemeTokens) -> None:
    """Paint the Plegat progress as an accordion of folded paper segments."""
    value = min(max(progress, 0.0), 1.0)
    if value <= 0:
        return
    width = rect.width() * value
    painter.save()
    painter.setClipRect(QRectF(rect.left(), rect.top(), width, rect.height()))
    painter.fillRect(rect, QColor(tokens.accent))
    fold = QColor(tokens.fold or tokens.accent2)
    painter.setPen(QPen(fold, max(1, tokens.border_width)))
    step = max(8.0, rect.height() * 0.8)
    position = rect.left()
    index = 0
    while position < rect.left() + width:
        painter.drawLine(
            QPointF(position, rect.top()),
            QPointF(position + step / 2, rect.bottom()),
        )
        position += step
        index += 1
    painter.restore()


def draw_tape_stripe(painter: QPainter, rect: QRectF, tokens: ThemeTokens) -> None:
    """Draw the three-colour cassette label stripe of Cinta."""
    colors = [tokens.accent, tokens.accent3 or tokens.accent2, tokens.accent2]
    stripe_height = max(2.0, rect.height() * 0.18)
    third = rect.width() / 3
    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)
    for index, color in enumerate(colors):
        painter.fillRect(
            QRectF(rect.left() + index * third, rect.top(), third, stripe_height),
            QColor(color),
        )
    painter.restore()


def draw_tape_reels(painter: QPainter, rect: QRectF, progress: float, tokens: ThemeTokens) -> None:
    """Draw the two cassette reels: the left empties as the right fills."""
    value = min(max(progress, 0.0), 1.0)
    if rect.width() <= 0 or rect.height() <= 0:
        return
    radius = min(rect.height() * 0.36, rect.width() * 0.12)
    centers = (
        QPointF(rect.left() + rect.width() * 0.16, rect.center().y()),
        QPointF(rect.left() + rect.width() * 0.84, rect.center().y()),
    )
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    for index, center in enumerate(centers):
        painter.setPen(QPen(QColor(tokens.line), max(1, tokens.border_width)))
        painter.setBrush(QColor(tokens.surface))
        painter.drawEllipse(center, radius, radius)
        state = (1 - value) if index == 0 else value
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tokens.accent if index == 0 else tokens.accent2))
        painter.drawEllipse(center, radius * (0.25 + 0.7 * state), radius * (0.25 + 0.7 * state))
    painter.restore()


def draw_mechanical_counter(
    painter: QPainter, rect: QRectF, text: str, tokens: ThemeTokens
) -> None:
    """Draw the Cinta mechanical counter with separated digit windows."""
    if not text or rect.width() <= 0 or rect.height() <= 0:
        return
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(tokens.line), max(1, tokens.border_width)))
    painter.setBrush(QColor(tokens.surface))
    painter.drawRoundedRect(rect, max(1.0, float(tokens.radius)), max(1.0, float(tokens.radius)))
    font = QFont(primary_family(tokens.mono))
    font.setPointSizeF(max(6.0, rect.height() * 0.55))
    font.setWeight(QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor(tokens.text))
    cell = rect.width() / max(1, len(text))
    for index, character in enumerate(text):
        cell_rect = QRectF(rect.left() + index * cell, rect.top(), cell, rect.height())
        if index:
            painter.setPen(QPen(QColor(tokens.line), 1))
            painter.drawLine(cell_rect.topLeft(), cell_rect.bottomLeft())
            painter.setPen(QColor(tokens.text))
        painter.drawText(cell_rect, Qt.AlignmentFlag.AlignCenter, character)
    painter.restore()
