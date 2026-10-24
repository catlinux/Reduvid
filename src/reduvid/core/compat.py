# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Jellyfin compatibility traffic light computed from an encoding plan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from reduvid.core.plan import EncodePlan, Warning

CompatLevel = Literal["direct", "partial", "blocked"]


@dataclass(frozen=True)
class CompatStatus:
    level: CompatLevel
    reasons: tuple[Warning, ...] = ()


def jellyfin_status(plan: EncodePlan) -> CompatStatus:
    """Classify how likely Jellyfin is to direct-play the planned output.

    The rule is intentionally simple: blocking warnings win; anything that makes
    Jellyfin transcode (a non-Jellyfin profile, 10-bit video or image subtitles it
    must burn in) is partial; everything else plays directly.
    """
    blocking = tuple(warning for warning in plan.warnings if warning.params.get("blocking") is True)
    if blocking:
        return CompatStatus("blocked", blocking)

    reasons: list[Warning] = []
    if plan.destination != "jellyfin":
        reasons.append(Warning("not_direct_play_profile", {"destination": plan.destination}))
    for video in plan.videos:
        if video.pixel_format is not None and "10" in video.pixel_format:
            reasons.append(Warning("ten_bit_video", {"stream_index": video.stream_index}))
    reasons.extend(warning for warning in plan.warnings if warning.code == "image_subtitle_burn_in")

    if reasons:
        return CompatStatus("partial", tuple(reasons))
    return CompatStatus("direct")
