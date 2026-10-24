# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Contrast checks for the six token sets (no Qt needed)."""

from __future__ import annotations

import pytest

from reduvid.gui.theme.tokens import THEMES

PAIRS = (
    ("text", "bg"),
    ("text", "surface"),
    ("muted", "bg"),
    ("on_accent", "accent"),
)


def relative_luminance(color: str) -> float:
    """Return the WCAG relative luminance of a ``#RRGGBB`` colour."""
    value = color.lstrip("#")
    channels = [int(value[index : index + 2], 16) / 255 for index in (0, 2, 4)]

    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground: str, background: str) -> float:
    """Return the WCAG contrast ratio between two colours."""
    first = relative_luminance(foreground)
    second = relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def test_all_six_theme_sets_exist() -> None:
    expected = {
        (theme, mode) for theme in ("plegat", "riso", "cinta") for mode in ("light", "dark")
    }

    assert set(THEMES) == expected


@pytest.mark.parametrize(("theme", "mode"), sorted(THEMES))
def test_text_contrast_meets_wcag_aa(theme: str, mode: str) -> None:
    tokens = THEMES[(theme, mode)]

    for foreground, background in PAIRS:
        ratio = contrast_ratio(getattr(tokens, foreground), getattr(tokens, background))
        assert ratio >= 4.5, f"{theme}/{mode} {foreground}/{background}: {ratio:.2f}"
