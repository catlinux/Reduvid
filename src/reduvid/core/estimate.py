# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Extrapolate final size and encoding time from a short sample."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Estimate:
    """Projected size and duration for the full encode."""

    estimated_total_bytes: int
    estimated_total_seconds: float


def estimate_from_sample(
    original_sample_bytes: int,
    encoded_sample_bytes: int,
    sample_duration_seconds: float,
    total_duration_seconds: float,
    elapsed_encode_seconds: float,
) -> Estimate:
    """Extrapolate size and time linearly from the encoded sample."""
    if sample_duration_seconds <= 0:
        raise ValueError("sample_duration_seconds must be positive")
    factor = total_duration_seconds / sample_duration_seconds
    return Estimate(
        estimated_total_bytes=round(encoded_sample_bytes * factor),
        estimated_total_seconds=elapsed_encode_seconds * factor,
    )
