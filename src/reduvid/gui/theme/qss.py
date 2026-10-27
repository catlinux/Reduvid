# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Build the Qt stylesheet from the design tokens."""

from __future__ import annotations

from string import Template

from reduvid.gui.theme.tokens import ThemeTokens

_TEMPLATE = Template(
    """
QMainWindow, QDialog, QWidget {
    background-color: ${bg};
    color: ${text};
    font-family: ${body};
    font-size: 15px;
}

QLabel {
    background-color: transparent;
    color: ${text};
}
QLabel[role="muted"] {
    color: ${muted};
}
QLabel[role="heading"] {
    font-family: ${display};
    font-size: 24px;
    font-weight: ${display_weight};
}
QLabel[role="display"] {
    font-family: ${display};
    font-size: ${heading_size}px;
    font-weight: ${display_weight};
}
QLabel[role="kicker"] {
    font-family: ${mono};
    font-size: 12px;
    font-weight: 700;
    color: ${muted};
}
QLabel[role="chip"] {
    background-color: ${chip_bg};
    color: ${chip_fg};
    padding: 2px 7px;
    border-radius: ${control_radius}px;
    font-size: 12px;
    font-weight: 600;
}
QLabel[role="chip"][tone="warn"] {
    background-color: ${warn_bg};
    color: ${warn_fg};
}
QLabel[role="tag"] {
    background-color: ${tag_bg};
    color: ${tag_fg};
    padding: 2px 7px;
    font-size: 11px;
    font-weight: 700;
}
QLabel[role="size"] {
    font-family: ${display};
    font-size: 24px;
    font-weight: ${display_weight};
}

QPushButton {
    background-color: ${surface};
    color: ${text};
    border: ${border_width}px solid ${line};
    border-radius: ${radius}px;
    padding: 9px 16px;
    font-weight: 700;
}
QPushButton:hover {
    background-color: ${soft};
}
QPushButton:pressed {
    background-color: ${line};
}
QPushButton:focus {
    border-color: ${accent};
    border-width: 2px;
}
QPushButton:disabled {
    background-color: ${bg};
    color: ${muted};
    border-color: ${line};
}
QPushButton[role="primary"] {
    background-color: ${accent};
    color: ${on_accent};
    border-color: ${accent};
    border-radius: ${control_radius}px;
    min-height: 40px;
}
QPushButton[role="ghost"] {
    background-color: transparent;
    border: ${border_width}px solid ${text};
    border-radius: ${control_radius}px;
    min-height: 40px;
}
QPushButton[role="primary"]:hover {
    border-color: ${accent2};
}
QPushButton[role="primary"]:pressed {
    background-color: ${accent2};
    border-color: ${accent2};
}
QPushButton[role="primary"]:focus {
    border-color: ${on_accent};
}
QPushButton[role="primary"]:disabled {
    background-color: ${line};
    color: ${muted};
    border-color: ${line};
}
QPushButton[role="secondary"] {
    background-color: transparent;
}
QPushButton[role="danger"] {
    background-color: ${warn_bg};
    color: ${warn_fg};
    border-color: ${warn_fg};
}
QPushButton[role="danger"]:hover {
    border-color: ${accent};
}
QPushButton[role="danger"]:focus {
    border-color: ${accent};
}
QPushButton[role="danger"]:disabled {
    background-color: ${bg};
    color: ${muted};
    border-color: ${line};
}

QFrame#card {
    background-color: ${surface};
    border: ${border_width}px solid ${line};
    border-radius: ${radius}px;
}
QFrame#card[checked="true"] {
    background-color: ${soft};
    border-color: ${accent};
}

QAbstractButton#card {
    background-color: ${surface};
    border: ${border_width}px solid ${line};
    border-radius: ${radius}px;
    text-align: left;
}
QAbstractButton#card:hover {
    border-color: ${muted};
}
QAbstractButton#card[checked="true"], QAbstractButton#card:checked {
    background-color: ${soft};
    border-color: ${accent};
}
QAbstractButton#card:focus {
    border-color: ${accent};
    border-width: 2px;
}

#stepList QPushButton {
    background-color: transparent;
    border: 0;
    color: ${muted};
    padding: 6px 8px;
    text-align: left;
}
#stepList QPushButton[state="done"] {
    color: ${text};
}
#stepList QPushButton[state="current"] {
    background-color: ${soft};
    color: ${text};
    font-weight: 700;
}
#stepList QPushButton:focus {
    border: 1px solid ${accent};
}

#segmented {
    border: ${border_width}px solid ${text};
    border-radius: ${control_radius}px;
}
#segmented QPushButton {
    border: 0;
    background-color: transparent;
    border-radius: 0;
    padding: 6px 12px;
}
#segmented QPushButton:checked {
    background-color: ${text};
    color: ${bg};
}

#sideBar {
    background-color: ${sidebar_bg};
    border-right: ${border_width}px solid ${sidebar_line};
}
#sideBar QLabel {
    color: ${sidebar_text};
}
#sideBar QLabel[role="muted"] {
    color: ${sidebar_muted};
}
#sideBar QPushButton {
    background-color: transparent;
    border: 0;
    color: ${sidebar_text};
}
#sideBar QPushButton[state="current"] {
    background-color: ${surface};
    color: ${text};
    border: ${border_width}px solid ${line};
    font-weight: 700;
}

#compatLight {
    border: ${border_width}px solid ${line};
    border-radius: ${radius}px;
    padding: 2px 8px;
}
#compatLight[level="direct"] {
    background-color: ${soft};
    color: ${text};
    border-color: ${accent};
}
#compatLight[level="partial"] {
    background-color: ${warn_bg};
    color: ${warn_fg};
    border-color: ${accent2};
}
#compatLight[level="blocked"] {
    background-color: ${warn_bg};
    color: ${warn_fg};
    border-color: ${warn_fg};
}

QLineEdit, QComboBox {
    background-color: ${surface};
    color: ${text};
    border: ${border_width}px solid ${line};
    border-radius: ${radius}px;
    padding: 7px 10px;
    selection-background-color: ${accent};
    selection-color: ${on_accent};
}
QLineEdit:hover, QComboBox:hover {
    border-color: ${muted};
}
QLineEdit:focus, QComboBox:focus, QComboBox:on {
    border-color: ${accent};
    border-width: 2px;
}
QLineEdit:disabled, QComboBox:disabled {
    background-color: ${bg};
    color: ${muted};
    border-color: ${line};
}
QComboBox::drop-down {
    border: 0;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: ${surface};
    color: ${text};
    border: ${border_width}px solid ${line};
    selection-background-color: ${soft};
    selection-color: ${text};
}

QCheckBox, QRadioButton {
    background-color: transparent;
    color: ${text};
    spacing: 8px;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border: 2px solid ${text};
    background-color: ${surface};
}
QCheckBox::indicator {
    border-radius: 3px;
}
QRadioButton::indicator {
    border-radius: 8px;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: ${accent};
    border-color: ${accent};
}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {
    background-color: ${bg};
    border-color: ${muted};
}
QCheckBox:focus, QRadioButton:focus {
    color: ${accent};
}
QCheckBox:focus::indicator, QRadioButton:focus::indicator {
    border-color: ${accent};
}

QSpinBox:focus {
    border-color: ${accent};
    border-width: 2px;
}
QListWidget:focus {
    border: ${border_width}px solid ${accent};
}
QToolButton:focus {
    border: 1px solid ${accent};
}
QPlainTextEdit:focus {
    border: ${border_width}px solid ${accent};
}

QProgressBar {
    background-color: ${track};
    border: ${border_width}px solid ${line};
    border-radius: ${radius}px;
    color: ${text};
    text-align: center;
    min-height: 14px;
    max-height: 18px;
}
QProgressBar::chunk {
    background: ${progress_fill};
    border-radius: ${radius}px;
}

QScrollBar:vertical {
    background: ${bg};
    width: 12px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: ${line};
    min-height: 28px;
    border-radius: 6px;
}
QScrollBar::handle:vertical:hover, QScrollBar::handle:vertical:pressed {
    background: ${accent};
}
QScrollBar:horizontal {
    background: ${bg};
    height: 12px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: ${line};
    min-width: 28px;
    border-radius: 6px;
}
QScrollBar::handle:horizontal:hover, QScrollBar::handle:horizontal:pressed {
    background: ${accent};
}
QScrollBar::add-line, QScrollBar::sub-line {
    width: 0;
    height: 0;
}
QScrollBar::add-page, QScrollBar::sub-page {
    background: transparent;
}

QToolTip {
    background-color: ${text};
    color: ${bg};
    border: 1px solid ${line};
    padding: 6px 8px;
}

QGroupBox {
    background-color: transparent;
    border: ${border_width}px solid ${line};
    border-radius: ${radius}px;
    margin-top: 14px;
    padding: 10px 12px 12px 12px;
    font-weight: 700;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: ${text};
    background-color: ${bg};
}

#stepList {
    background-color: transparent;
    border-right: ${border_width}px solid ${line};
}
#queuePanel {
    background-color: ${surface};
    border-left: ${border_width}px solid ${line};
}
#optionCard {
    background-color: ${surface};
    border: ${border_width}px solid ${line};
    border-radius: ${card_radius}px;
}
#optionCard[selected="true"] {
    background-color: ${selected_bg};
    border-color: ${selected_bg};
    color: ${selected_fg};
}
#optionCard[selected="true"] QLabel {
    color: ${selected_fg};
}
#optionCard[selected="true"] QLabel[role="muted"] {
    color: ${selected_muted};
}
#contextPanel {
    background-color: transparent;
}
#transportBar {
    background-color: ${surface};
    border-top: ${border_width}px solid ${line};
}
#transportBar QLabel[role="size"] {
    font-size: 30px;
}
#warnChip {
    background-color: ${warn_bg};
    color: ${warn_fg};
    border: ${border_width}px solid ${warn_fg};
    border-radius: ${radius}px;
    padding: 6px 10px;
}
"""
)


def build_qss(tokens: ThemeTokens) -> str:
    """Return the stylesheet for *tokens* with every placeholder substituted."""
    return _TEMPLATE.substitute(
        bg=tokens.bg,
        surface=tokens.surface,
        text=tokens.text,
        muted=tokens.muted,
        line=tokens.line,
        accent=tokens.accent,
        accent2=tokens.accent2,
        on_accent=tokens.on_accent,
        soft=tokens.soft,
        warn_bg=tokens.warn_bg,
        warn_fg=tokens.warn_fg,
        track=tokens.track,
        radius=tokens.radius,
        border_width=tokens.border_width,
        body=tokens.body,
        display=tokens.display,
        mono=tokens.mono,
        display_weight=tokens.display_weight,
        sidebar_bg=tokens.sidebar_bg,
        sidebar_text=tokens.sidebar_text,
        sidebar_muted=tokens.sidebar_muted,
        sidebar_line=tokens.sidebar_line,
        selected_bg=tokens.selected_bg,
        selected_fg=tokens.selected_fg,
        selected_muted=tokens.selected_muted,
        tag_bg=tokens.tag_bg,
        tag_fg=tokens.tag_fg,
        chip_bg=tokens.chip_bg,
        chip_fg=tokens.chip_fg,
        control_radius=tokens.control_radius,
        card_radius=tokens.card_radius,
        heading_size=tokens.heading_size,
        progress_fill=_progress_fill(tokens),
    )


def _progress_fill(tokens: ThemeTokens) -> str:
    """Return the progress fill: solid, or the gradient the mockup uses.

    The repeating stripe of Plegat and the dotted track of Riso are simplified
    here; their full motifs belong to step 2.11.
    """
    if tokens.accent3 is not None:
        return (
            "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 {tokens.accent}, stop:0.33 {tokens.accent}, "
            f"stop:0.34 {tokens.accent3}, stop:0.66 {tokens.accent3}, "
            f"stop:0.67 {tokens.accent2}, stop:1 {tokens.accent2})"
        )
    if tokens.fold is not None:
        return (
            "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 {tokens.accent}, stop:0.82 {tokens.accent}, "
            f"stop:0.85 {tokens.fold}, stop:0.9 {tokens.fold}, "
            f"stop:0.93 {tokens.accent}, stop:1 {tokens.accent})"
        )
    return tokens.accent
