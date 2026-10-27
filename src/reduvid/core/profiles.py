# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Data describing the available encoding targets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Profile:
    name: str
    video_codec: Literal["libx264", "libx265"]
    preset: Literal["medium", "slow"]
    video_profile: str | None = None
    video_level: str | None = None
    pixel_format: str | None = None


PROFILES: dict[str, Profile] = {
    "cinecat": Profile(
        name="cinecat",
        video_codec="libx264",  # Browsers and the Cinecat web player decode H.264 everywhere.
        preset="medium",  # Balanced speed; Cinecat direct play does not depend on the preset.
        video_profile="high",  # High profile at 8 bits is the broad browser baseline.
        video_level="4.1",  # Level 4.1 keeps 1080p within what the browser can decode.
        pixel_format="yuv420p",  # 8-bit 4:2:0 is what browsers expect for direct play.
    ),
    "modern": Profile(
        name="modern",
        video_codec="libx265",
        preset="medium",
    ),
    "archive": Profile(
        name="archive",
        video_codec="libx265",
        preset="slow",
    ),
}

QUALITY_CRFS: dict[str, dict[str, int]] = {
    "high": {"libx264": 19, "libx265": 21},
    "balanced": {"libx264": 22, "libx265": 24},
    "max_savings": {"libx264": 25, "libx265": 27},
}
