# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Steps 4-6: languages, destination, summary, blocking dialogs and start."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QLabel, QSizePolicy

from reduvid.core.config import Config
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.plan import Warning
from reduvid.core.probe import AudioStream, MediaInfo, SubtitleStream, VideoStream
from reduvid.core.report import build_file_report, build_queue_report
from reduvid.gui.main_window import MainWindow
from reduvid.gui.theme.manager import ThemeManager
from reduvid.gui.theme.qss import build_qss
from reduvid.gui.theme.tokens import THEMES
from reduvid.gui.wizard.step_destination import StepDestination
from reduvid.gui.wizard.step_keep import StepKeep
from reduvid.gui.wizard.step_summary import StepSummary
from reduvid.gui.wizard_state import WizardState
from reduvid.messages import error_text, warning_text


def media(
    path: Path,
    *,
    video: VideoStream | None = None,
    audios: list[AudioStream] | None = None,
    subtitles: list[SubtitleStream] | None = None,
    size: int = 1000,
    duration: float = 60.0,
) -> MediaInfo:
    return MediaInfo(
        path,
        "matroska",
        duration,
        size,
        [video] if video is not None else [],
        audios or [],
        subtitles or [],
        [],
    )


def ffmpeg(*filters: str) -> FFmpegInfo:
    return FFmpegInfo(Path("ffmpeg"), Path("ffprobe"), "test", frozenset(), frozenset(filters), ())


def add_video(state: WizardState, tmp_path: Path, name: str, info: MediaInfo) -> Path:
    path = tmp_path / name
    path.touch()
    state.add_paths([path])
    state.set_media(path, info)
    return path.resolve()


def languages_state(tmp_path: Path) -> WizardState:
    state = WizardState(Config())
    add_video(
        state,
        tmp_path,
        "video.mkv",
        media(
            tmp_path / "video.mkv",
            video=VideoStream(0, "h264", 1920, 1080, 24),
            audios=[
                AudioStream(1, "aac", 2, "eng", True),
                AudioStream(2, "aac", 2, "spa", False),
            ],
            subtitles=[
                SubtitleStream(3, "subrip", "eng", False, False, False),
                SubtitleStream(4, "subrip", "", False, False, False),
            ],
        ),
    )
    return state


class FakePrompt:
    def __init__(self, keep: bool) -> None:
        self.keep = keep
        self.asked: list[Path] = []

    def ask(self, summary) -> bool:
        self.asked.append(summary.path)
        return self.keep


class FakeWorker(QObject):
    finished = Signal(object)


def summary_state(tmp_path: Path) -> WizardState:
    state = WizardState(Config())
    direct = VideoStream(0, "h264", 1920, 1080, 24)
    hdr = VideoStream(0, "hevc", 1920, 1080, 24, hdr=True, hdr_variant="hdr10")
    add_video(
        state,
        tmp_path,
        "direct.mkv",
        media(
            tmp_path / "direct.mkv",
            video=direct,
            audios=[AudioStream(1, "aac", 2, "eng", True)],
        ),
    )
    add_video(
        state,
        tmp_path,
        "image-subs.mkv",
        media(
            tmp_path / "image-subs.mkv",
            video=direct,
            subtitles=[SubtitleStream(1, "hdmv_pgs_subtitle", "eng", True, False, False)],
        ),
    )
    add_video(state, tmp_path, "hdr.mkv", media(tmp_path / "hdr.mkv", video=hdr))
    return state


def test_step_keep_checks_every_language_and_reports_subsets(tmp_path: Path, qapp) -> None:
    state = languages_state(tmp_path)
    step = StepKeep(state)

    assert set(step.audio_checks) == {"eng", "spa"}
    assert set(step.subtitle_checks) == {"eng", "und"}
    assert all(checkbox.isChecked() for checkbox in step.audio_checks.values())
    assert state.options().audio_languages is None
    assert state.options().subtitle_languages is None

    step.audio_checks["spa"].setChecked(False)

    assert state.options().audio_languages == frozenset({"eng"})
    assert step.audio_warning.isHidden()

    step.audio_checks["eng"].setChecked(False)

    assert state.options().audio_languages == frozenset()
    assert not step.audio_warning.isHidden()
    assert state.selected_audio_languages() == frozenset()

    step.audio_checks["eng"].setChecked(True)
    step.audio_checks["spa"].setChecked(True)

    assert state.options().audio_languages is None


def test_step_destination_controls_container_folder_and_4k(tmp_path: Path, qapp) -> None:
    state = WizardState(Config())
    add_video(
        state,
        tmp_path,
        "uhd.mkv",
        media(
            tmp_path / "uhd.mkv",
            video=VideoStream(0, "hevc", 3840, 2160, 24),
        ),
    )
    step = StepDestination(state)

    assert state.container == "mkv"
    step.container_cards["mp4"].click()
    assert state.container == "mp4"

    assert step.same_folder_radio.isChecked()
    step.other_folder_radio.click()
    step.folder_edit.setText(str(tmp_path / "converted"))
    step.folder_edit.editingFinished.emit()
    assert state.output_dir == tmp_path / "converted"
    step.same_folder_radio.click()
    assert state.output_dir is None

    step.replace_original.click()
    assert state.replace_original is True

    assert not step.reduce_4k.isHidden()
    step.reduce_4k.click()
    assert state.reduce_4k is False
    assert state.options().max_height == 2160

    state.set_destination("modern")
    assert step.reduce_4k.isHidden()


def test_summary_traffic_lights_warnings_and_skip_decisions(tmp_path: Path, qapp) -> None:
    state = summary_state(tmp_path)
    summary = StepSummary(state, ffmpeg())
    prompt = FakePrompt(keep=False)
    summary.blocking_prompt = prompt

    summary.refresh()

    assert len(prompt.asked) == 1
    levels = {path.name: label.property("level") for path, label in summary.status_labels.items()}
    assert levels == {
        "direct.mkv": "direct",
        "image-subs.mkv": "partial",
        "hdr.mkv": "blocked",
    }
    assert any(path.name == "hdr.mkv" for path in summary.skipped)
    assert [path.name for path in summary.remaining_paths()] == [
        "direct.mkv",
        "image-subs.mkv",
    ]


def test_summary_rows_are_coloured_cards(tmp_path: Path, qapp) -> None:
    state = summary_state(tmp_path)
    summary = StepSummary(state, ffmpeg())
    summary.blocking_prompt = FakePrompt(keep=False)

    summary.refresh()

    cards = [
        summary.items_layout.itemAt(index).widget() for index in range(summary.items_layout.count())
    ]
    assert all(card is not None for card in cards)
    cards = [card for card in cards if card is not None]
    levels = {card.property("level") for card in cards}
    assert len(cards) == 3
    assert levels == {"direct", "partial", "blocked"}
    assert all(card.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Preferred for card in cards)
    layout = summary.layout()
    assert layout is not None
    assert layout.itemAt(3).spacerItem() is not None


def test_summary_keeps_blocking_videos_when_converting_anyway(tmp_path: Path, qapp) -> None:
    state = summary_state(tmp_path)
    summary = StepSummary(state, ffmpeg())
    summary.blocking_prompt = FakePrompt(keep=True)

    summary.refresh()

    assert summary.skipped == set()
    assert len(summary.remaining_paths()) == 3


def test_summary_start_disabled_without_videos_and_on_last_step(tmp_path: Path, qapp) -> None:
    window = MainWindow(Config(), ffmpeg(), ThemeManager(qapp))
    window.show()
    try:
        window.set_current_step(5)
        assert window.current_step == 5
        assert not window.step_summary.start_button.isEnabled()
        assert not window.wizard_nav.next_button.isEnabled()
    finally:
        window.close()


def test_start_calls_start_queue_with_the_expected_arguments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp
) -> None:
    window = MainWindow(Config(), ffmpeg(), ThemeManager(qapp))
    state = window.wizard_state
    path = add_video(
        state,
        tmp_path,
        "direct.mkv",
        media(
            tmp_path / "direct.mkv",
            video=VideoStream(0, "h264", 1920, 1080, 24),
        ),
    )
    window.step_summary.refresh()
    captured: dict[str, object] = {}

    def fake_start(paths, options, **kwargs):
        worker = FakeWorker()
        captured.update(paths=list(paths), options=options, kwargs=kwargs, worker=worker)
        return worker

    monkeypatch.setattr(window, "start_queue", fake_start)

    window.step_summary.start_button.click()

    assert captured["paths"] == [path]
    assert captured["options"] == state.options()
    assert captured["kwargs"] == {
        "output_dir": state.output_dir,
        "threads": None,
        "replace_original": False,
    }
    assert not window.step_summary.start_button.isEnabled()


def test_summary_shows_the_final_report_and_errors(tmp_path: Path, qapp) -> None:
    state = summary_state(tmp_path)
    summary = StepSummary(state, ffmpeg())
    success = build_file_report(Path("direct.mkv"), "success", 1000, 600)
    failed = build_file_report(
        Path("hdr.mkv"), "failed", 2000, reason="encoder exploded", error_code="no_space"
    )

    summary.show_report(build_queue_report([success, failed]))

    text = summary.report_label.text()
    assert "Total savings" in text
    assert "1 failed" in text
    assert len(summary.error_views) == 1
    assert summary.error_views[0].message_label.text() == error_text("no_space")
    assert summary.error_views[0].details.toPlainText() == "encoder exploded"


def test_theme_has_traffic_light_levels() -> None:
    qss = build_qss(THEMES[("plegat", "light")])

    for level in ("direct", "partial", "blocked"):
        assert f'#compatLight[level="{level}"]' in qss


def test_warning_text_is_used_in_the_summary(tmp_path: Path, qapp) -> None:
    state = summary_state(tmp_path)
    summary = StepSummary(state, ffmpeg())
    summary.blocking_prompt = FakePrompt(keep=False)
    summary.refresh()

    labels = [label.text() for label in summary.findChildren(QLabel, "compatWarning")]
    expected = warning_text(Warning("image_subtitle_burn_in", {"stream_index": 1}))
    assert expected in labels
