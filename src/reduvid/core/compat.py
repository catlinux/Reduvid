# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Cinecat compatibility traffic light computed from an encoding plan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from reduvid.core.plan import EncodePlan, Warning

CompatLevel = Literal["direct", "partial", "blocked"]


@dataclass(frozen=True)
class CompatStatus:
    level: CompatLevel
    reasons: tuple[Warning, ...] = ()


def cinecat_status(plan: EncodePlan) -> CompatStatus:
    """Classify how likely Cinecat is to direct-play the planned output.

    Blocking warnings win. Cinecat only direct-plays MP4 with 8-bit video and no
    discarded image subtitles; anything else makes it transcode.
    """
    blocking = tuple(warning for warning in plan.warnings if warning.params.get("blocking") is True)
    if blocking:
        return CompatStatus("blocked", blocking)

    reasons: list[Warning] = []
    if plan.destination != "cinecat":
        reasons.append(Warning("not_direct_play_profile", {"destination": plan.destination}))
    if plan.container != "mp4":
        reasons.append(Warning("not_direct_play_container", {"container": plan.container}))
    for video in plan.videos:
        if video.pixel_format is not None and "10" in video.pixel_format:
            reasons.append(Warning("ten_bit_video", {"stream_index": video.stream_index}))
    reasons.extend(
        warning
        for warning in plan.warnings
        if warning.code in {"image_subtitle_burn_in", "image_subtitle_dropped_mp4"}
    )

    if reasons:
        return CompatStatus("partial", tuple(reasons))
    return CompatStatus("direct")
