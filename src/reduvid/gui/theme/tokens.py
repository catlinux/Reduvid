# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Design tokens for the three themes, copied from ``docs/design/mockups.html``."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemeTokens:
    """Colours, shapes and typography of one theme in one colour mode."""

    bg: str
    surface: str
    text: str
    muted: str
    line: str
    accent: str
    accent2: str
    accent3: str | None
    fold: str | None
    on_accent: str
    soft: str
    warn_bg: str
    warn_fg: str
    # Simple base colour of the progress track; the dotted/striped motif from
    # the mockups is drawn in step 2.11.
    track: str
    radius: int
    border_width: int
    display: str
    body: str
    mono: str
    display_weight: int
    body_weight: int


THEMES: dict[tuple[str, str], ThemeTokens] = {
    ("plegat", "light"): ThemeTokens(
        bg="#F0F3F2",
        surface="#FFFFFF",
        text="#15292B",
        muted="#52676A",
        line="#CFD8D7",
        accent="#0F5E63",
        accent2="#D39B14",
        accent3=None,
        fold="#0A4245",
        on_accent="#FFFFFF",
        soft="#E1EBEA",
        warn_bg="#F6E6BC",
        warn_fg="#15292B",
        track="#E1EBEA",
        radius=0,
        border_width=1,
        display='"Bricolage Grotesque", "Trebuchet MS", sans-serif',
        body='"Instrument Sans", "Segoe UI", sans-serif',
        mono='"Instrument Sans", sans-serif',
        display_weight=750,
        body_weight=400,
    ),
    ("plegat", "dark"): ThemeTokens(
        bg="#0C1819",
        surface="#132628",
        text="#E3EDEB",
        muted="#92A8A7",
        line="#264241",
        accent="#45AAAD",
        accent2="#E7B33A",
        accent3=None,
        fold="#2A7A7D",
        on_accent="#0C1819",
        soft="#183031",
        warn_bg="#4A3A12",
        warn_fg="#F6E6BC",
        track="#183031",
        radius=0,
        border_width=1,
        display='"Bricolage Grotesque", "Trebuchet MS", sans-serif',
        body='"Instrument Sans", "Segoe UI", sans-serif',
        mono='"Instrument Sans", sans-serif',
        display_weight=750,
        body_weight=400,
    ),
    ("riso", "light"): ThemeTokens(
        bg="#EEF0EA",
        surface="#F8F9F5",
        text="#1E2440",
        muted="#565E7E",
        line="#1E2440",
        accent="#FF6A3D",
        accent2="#3D5AA8",
        accent3=None,
        fold=None,
        on_accent="#1E2440",
        soft="#DDE2EF",
        warn_bg="#FFD9CC",
        warn_fg="#1E2440",
        track="#F8F9F5",
        radius=0,
        border_width=2,
        display='"Archivo", "Arial Narrow", sans-serif',
        body='"Atkinson Hyperlegible", "Verdana", sans-serif',
        mono='"Archivo", sans-serif',
        display_weight=800,
        body_weight=400,
    ),
    ("riso", "dark"): ThemeTokens(
        bg="#141830",
        surface="#1C2142",
        text="#E8EAF3",
        muted="#A6ADC9",
        line="#E8EAF3",
        accent="#FF7A4D",
        accent2="#8AA2FF",
        accent3=None,
        fold=None,
        on_accent="#141830",
        soft="#272E5A",
        warn_bg="#5A2C24",
        warn_fg="#FFD9CC",
        track="#1C2142",
        radius=0,
        border_width=2,
        display='"Archivo", "Arial Narrow", sans-serif',
        body='"Atkinson Hyperlegible", "Verdana", sans-serif',
        mono='"Archivo", sans-serif',
        display_weight=800,
        body_weight=400,
    ),
    ("cinta", "light"): ThemeTokens(
        bg="#E6E7EA",
        surface="#FBFBFC",
        text="#16171A",
        muted="#5A5E66",
        line="#C3C6CC",
        accent="#D93A26",
        accent2="#F2A93B",
        accent3="#EE7330",
        fold=None,
        on_accent="#FFFFFF",
        soft="#EEEFF1",
        warn_bg="#FCE3B8",
        warn_fg="#16171A",
        track="#2A2420",
        radius=3,
        border_width=1,
        display='"Barlow Condensed", "Arial Narrow", sans-serif',
        body='"Barlow", "Segoe UI", sans-serif',
        mono='"JetBrains Mono", ui-monospace, monospace',
        display_weight=700,
        body_weight=400,
    ),
    ("cinta", "dark"): ThemeTokens(
        bg="#0F1012",
        surface="#1D1F23",
        text="#ECEDEF",
        muted="#9DA2AB",
        line="#33363C",
        accent="#F0553F",
        accent2="#F5B54C",
        accent3="#F5883F",
        fold=None,
        on_accent="#0F1012",
        soft="#272A2F",
        warn_bg="#4A3514",
        warn_fg="#FCE3B8",
        track="#3A322C",
        radius=3,
        border_width=1,
        display='"Barlow Condensed", "Arial Narrow", sans-serif',
        body='"Barlow", "Segoe UI", sans-serif',
        mono='"JetBrains Mono", ui-monospace, monospace',
        display_weight=700,
        body_weight=400,
    ),
}
