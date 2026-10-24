# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from pathlib import Path

from reduvid.core.plan import Warning
from reduvid.core.report import build_file_report, build_queue_report


def test_file_savings_and_queue_aggregation() -> None:
    warning = Warning("audio_recoded")
    success = build_file_report(Path("one.mkv"), "success", 1000, 600, (warning,))
    failed = build_file_report(Path("two.mkv"), "failed", 500, 100, reason="bad input")
    skipped = build_file_report(Path("three.mkv"), "skipped", 250, reason="cancelled")

    report = build_queue_report([success, failed, skipped])

    assert success.savings_bytes == 400
    assert success.savings_percent == 40.0
    assert report.original_size == 1750
    assert report.final_size == 600
    assert report.savings_bytes == 400
    assert report.savings_percent == 400 / 1750 * 100
    assert (report.succeeded, report.failed, report.skipped) == (1, 1, 1)
    assert failed.savings_bytes == 0
    assert success.warnings == (warning,)
