# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Currently active theme tokens, shared with custom-painted widgets."""

from __future__ import annotations

from reduvid.gui.theme.tokens import THEMES, ThemeTokens

_active: ThemeTokens | None = None


def set_active_tokens(tokens: ThemeTokens) -> None:
    global _active
    _active = tokens


def active_tokens() -> ThemeTokens:
    """Return the tokens of the last applied theme (Plegat light by default)."""
    return _active if _active is not None else THEMES[("plegat", "light")]
