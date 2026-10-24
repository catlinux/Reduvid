# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from pathlib import Path

import pytest

from reduvid.core import verify
from reduvid.core.probe import MediaInfo, ProbeError


def _media(path: Path, duration: float, size: int) -> MediaInfo:
    return MediaInfo(path, "matroska", duration, size, [], [], [], [])


def _verify() -> verify.VerificationResult:
    return verify.verify_output(
        Path("ffprobe"), Path("original.mkv"), 100.0, 1000, Path("output.mkv")
    )


def test_verify_accepts_duration_within_tolerance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(verify, "probe_media", lambda _probe, path: _media(path, 100.5, 999))

    assert _verify() == verify.VerificationResult(True, "ok", 100.5, 999)


def test_verify_rejects_duration_outside_tolerance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(verify, "probe_media", lambda _probe, path: _media(path, 101.01, 999))

    result = _verify()

    assert not result.passed
    assert result.reason == "duration_mismatch"


def test_verify_rejects_probe_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_probe(_probe: Path, _path: Path) -> MediaInfo:
        raise ProbeError("invalid output")

    monkeypatch.setattr(verify, "probe_media", fail_probe)

    result = _verify()

    assert not result.passed
    assert result.reason == "probe_failed"


@pytest.mark.parametrize("output_size", [1000, 1001])
def test_verify_rejects_output_at_least_original_size(
    monkeypatch: pytest.MonkeyPatch, output_size: int
) -> None:
    monkeypatch.setattr(
        verify, "probe_media", lambda _probe, path: _media(path, 100.0, output_size)
    )

    result = _verify()

    assert not result.passed
    assert result.reason == "output_too_large"


def test_verify_respects_exact_duration_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(verify, "probe_media", lambda _probe, path: _media(path, 101.0, 999))
    assert _verify().passed

    monkeypatch.setattr(verify, "probe_media", lambda _probe, path: _media(path, 101.0001, 999))
    assert _verify().reason == "duration_mismatch"
