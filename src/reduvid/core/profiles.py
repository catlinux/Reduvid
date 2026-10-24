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
    "jellyfin": Profile(
        name="jellyfin",
        video_codec="libx264",  # Widely supported by Jellyfin playback devices.
        preset="medium",  # The balanced default encoding speed.
        video_profile="high",  # High@4.1 decodes on nearly every TV, phone, and browser.
        video_level="4.1",  # Higher levels trigger Jellyfin transcoding on many clients.
        pixel_format="yuv420p",  # Eight-bit output avoids client transcodes caused by 10-bit video.
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
