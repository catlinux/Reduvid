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
    # Cinta keeps its dark casing in both colour modes.
    sidebar_bg: str
    sidebar_text: str
    sidebar_muted: str
    sidebar_line: str
    selected_bg: str
    selected_fg: str
    selected_muted: str
    tag_bg: str
    tag_fg: str
    chip_bg: str
    chip_fg: str
    # Painted by theme widgets; Qt stylesheets have no box-shadow.
    shadow_offset: int
    shadow_color: str
    control_radius: int
    card_radius: int
    heading_size: int
    heading_uppercase: bool
    heading_letter_spacing: float
    kicker_uppercase: bool


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
        sidebar_bg="#F0F3F2",
        sidebar_text="#15292B",
        sidebar_muted="#52676A",
        sidebar_line="#CFD8D7",
        selected_bg="#0F5E63",
        selected_fg="#FFFFFF",
        selected_muted="#D4E6E5",
        tag_bg="#D39B14",
        tag_fg="#15292B",
        chip_bg="#E1EBEA",
        chip_fg="#15292B",
        shadow_offset=0,
        shadow_color="#CFD8D7",
        control_radius=0,
        card_radius=0,
        heading_size=42,
        heading_uppercase=False,
        heading_letter_spacing=-1.2,
        kicker_uppercase=True,
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
        sidebar_bg="#0C1819",
        sidebar_text="#E3EDEB",
        sidebar_muted="#92A8A7",
        sidebar_line="#264241",
        selected_bg="#45AAAD",
        selected_fg="#0C1819",
        selected_muted="#16393A",
        tag_bg="#E7B33A",
        tag_fg="#0C1819",
        chip_bg="#183031",
        chip_fg="#E3EDEB",
        shadow_offset=0,
        shadow_color="#264241",
        control_radius=0,
        card_radius=0,
        heading_size=42,
        heading_uppercase=False,
        heading_letter_spacing=-1.2,
        kicker_uppercase=True,
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
        sidebar_bg="#EEF0EA",
        sidebar_text="#1E2440",
        sidebar_muted="#565E7E",
        sidebar_line="#1E2440",
        selected_bg="#FF6A3D",
        selected_fg="#1E2440",
        selected_muted="#1E2440",
        tag_bg="#1E2440",
        tag_fg="#FF6A3D",
        chip_bg="#F8F9F5",
        chip_fg="#1E2440",
        shadow_offset=4,
        shadow_color="#3D5AA8",
        control_radius=0,
        card_radius=0,
        heading_size=44,
        heading_uppercase=True,
        heading_letter_spacing=-0.4,
        kicker_uppercase=True,
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
        sidebar_bg="#141830",
        sidebar_text="#E8EAF3",
        sidebar_muted="#A6ADC9",
        sidebar_line="#E8EAF3",
        selected_bg="#FF7A4D",
        selected_fg="#141830",
        selected_muted="#141830",
        tag_bg="#141830",
        tag_fg="#FF7A4D",
        chip_bg="#1C2142",
        chip_fg="#E8EAF3",
        shadow_offset=4,
        shadow_color="#8AA2FF",
        control_radius=0,
        card_radius=0,
        heading_size=44,
        heading_uppercase=True,
        heading_letter_spacing=-0.4,
        kicker_uppercase=True,
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
        sidebar_bg="#16171A",
        sidebar_text="#ECEDEF",
        sidebar_muted="#9DA2AB",
        sidebar_line="#26282D",
        selected_bg="#FBFBFC",
        selected_fg="#16171A",
        selected_muted="#43474F",
        tag_bg="#FBFBFC",
        tag_fg="#16171A",
        chip_bg="#EEEFF1",
        chip_fg="#16171A",
        shadow_offset=0,
        shadow_color="#C3C6CC",
        control_radius=3,
        card_radius=3,
        heading_size=50,
        heading_uppercase=True,
        heading_letter_spacing=0.6,
        kicker_uppercase=True,
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
        sidebar_bg="#17181B",
        sidebar_text="#ECEDEF",
        sidebar_muted="#9DA2AB",
        sidebar_line="#26282D",
        selected_bg="#24262B",
        selected_fg="#ECEDEF",
        selected_muted="#9DA2AB",
        tag_bg="#1D1F23",
        tag_fg="#ECEDEF",
        chip_bg="#272A2F",
        chip_fg="#ECEDEF",
        shadow_offset=0,
        shadow_color="#33363C",
        control_radius=3,
        card_radius=3,
        heading_size=50,
        heading_uppercase=True,
        heading_letter_spacing=0.6,
        kicker_uppercase=True,
    ),
}
