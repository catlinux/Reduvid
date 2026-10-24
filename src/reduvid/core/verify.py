# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Verify a converted media file before it is finalized."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from reduvid.core.probe import ProbeError, probe_media

VerificationReason = Literal["ok", "duration_mismatch", "probe_failed", "output_too_large"]


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    reason: VerificationReason
    output_duration: float | None = None
    output_size: int | None = None


def verify_output(
    ffprobe_path: Path,
    original_path: Path,
    original_duration: float,
    original_size: int,
    output_path: Path,
) -> VerificationResult:
    """Probe output and check its duration and size against the original."""
    try:
        output = probe_media(ffprobe_path, output_path)
    except ProbeError:
        return VerificationResult(False, "probe_failed")

    if abs(output.duration - original_duration) > max(1.0, original_duration * 0.005):
        return VerificationResult(False, "duration_mismatch", output.duration, output.size)
    if output.size >= original_size:
        return VerificationResult(False, "output_too_large", output.duration, output.size)
    return VerificationResult(True, "ok", output.duration, output.size)
