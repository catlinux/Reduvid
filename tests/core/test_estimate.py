# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

import pytest

from reduvid.core.estimate import Estimate, estimate_from_sample


def test_estimate_extrapolates_size_and_time() -> None:
    estimate = estimate_from_sample(
        original_sample_bytes=5_000_000,
        encoded_sample_bytes=1_000_000,
        sample_duration_seconds=30.0,
        total_duration_seconds=300.0,
        elapsed_encode_seconds=15.0,
    )

    assert estimate == Estimate(10_000_000, 150.0)


def test_estimate_rounds_the_projected_bytes() -> None:
    estimate = estimate_from_sample(
        original_sample_bytes=10,
        encoded_sample_bytes=1,
        sample_duration_seconds=3.0,
        total_duration_seconds=10.0,
        elapsed_encode_seconds=1.0,
    )

    assert estimate.estimated_total_bytes == 3
    assert estimate.estimated_total_seconds == pytest.approx(10 / 3)


def test_estimate_accepts_a_shorter_sample() -> None:
    estimate = estimate_from_sample(
        original_sample_bytes=300,
        encoded_sample_bytes=60,
        sample_duration_seconds=18.0,
        total_duration_seconds=30.0,
        elapsed_encode_seconds=9.0,
    )

    assert estimate.estimated_total_bytes == 100
    assert estimate.estimated_total_seconds == pytest.approx(15.0)


def test_zero_total_duration_returns_zeroes() -> None:
    estimate = estimate_from_sample(100, 10, 30, 0, 5)

    assert estimate == Estimate(0, 0.0)


@pytest.mark.parametrize("sample_duration", [0.0, -1.0])
def test_invalid_sample_duration_raises(sample_duration: float) -> None:
    with pytest.raises(ValueError, match="sample_duration_seconds must be positive"):
        estimate_from_sample(100, 10, sample_duration, 120, 5)
