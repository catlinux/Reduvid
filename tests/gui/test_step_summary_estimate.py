# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Estimates in the Summary step only when a valid sample exists."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QLabel

from reduvid.core.config import Config
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.probe import AudioStream, MediaInfo, VideoStream
from reduvid.gui.wizard.step_summary import StepSummary
from reduvid.gui.wizard_state import WizardState
from reduvid.gui.workers import SampleResult


def ffmpeg_info() -> FFmpegInfo:
    return FFmpegInfo(
        Path("ffmpeg"), Path("ffprobe"), "test", frozenset({"libx264"}), frozenset(), ()
    )


def media(path: Path, duration: float) -> MediaInfo:
    return MediaInfo(
        path,
        "matroska",
        duration,
        100_000_000,
        [VideoStream(0, "h264", 1920, 1080, 24)],
        [AudioStream(1, "aac", 2, "eng", True)],
        [],
        [],
    )


def state_with_videos(tmp_path: Path) -> WizardState:
    state = WizardState(Config())
    for name, duration in (("short.mkv", 30.0), ("long.mkv", 120.0)):
        path = tmp_path / name
        path.touch()
        state.add_paths([path])
        state.set_media(path, media(path, duration))
    return state


def sample_result(tmp_path: Path) -> SampleResult:
    before = tmp_path / "before.png"
    after = tmp_path / "after.png"
    before.touch()
    after.touch()
    result = SampleResult(
        encoded_sample_bytes=10_000_000,
        sample_duration_seconds=30.0,
        total_duration_seconds=60.0,
        original_total_bytes=100_000_000,
        encode_seconds=5.0,
        original_frame_path=before,
        encoded_frame_path=after,
    )
    return result


def estimate_labels(summary: StepSummary) -> list[str]:
    labels: list[str] = []
    for index in range(summary.items_layout.count()):
        row = summary.items_layout.itemAt(index).widget()
        if row is not None:
            labels.extend(label.text() for label in row.findChildren(QLabel, "estimateInfo"))
    return labels


def test_summary_shows_proportional_estimates(tmp_path: Path, qapp) -> None:
    state = state_with_videos(tmp_path)
    state.set_quality("balanced")
    state.set_sample_result(sample_result(tmp_path))
    summary = StepSummary(state, ffmpeg_info())
    summary.refresh(prompt_blocking=False)

    labels = estimate_labels(summary)

    assert len(labels) == 2
    assert any("10 MB" in text and "0:05" in text for text in labels)
    assert any("40 MB" in text and "0:20" in text for text in labels)


def test_summary_has_no_estimates_without_a_sample(tmp_path: Path, qapp) -> None:
    state = state_with_videos(tmp_path)
    summary = StepSummary(state, ffmpeg_info())

    summary.refresh(prompt_blocking=False)

    assert estimate_labels(summary) == []


def test_changing_quality_invalidates_the_estimate(tmp_path: Path, qapp) -> None:
    state = state_with_videos(tmp_path)
    state.set_sample_result(sample_result(tmp_path))
    summary = StepSummary(state, ffmpeg_info())
    summary.refresh(prompt_blocking=False)
    assert len(estimate_labels(summary)) == 2

    state.set_quality("high")
    assert state.sample_result is None
    summary.refresh(prompt_blocking=False)

    assert estimate_labels(summary) == []
