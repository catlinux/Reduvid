# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Steps 4-6: languages, destination, summary, blocking dialogs and start."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QLabel, QProgressBar, QPushButton, QScrollArea, QWidget

from reduvid.core.config import Config
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.pipeline import PipelineError
from reduvid.core.plan import Warning
from reduvid.core.probe import AudioStream, MediaInfo, SubtitleStream, VideoStream
from reduvid.core.report import build_file_report, build_queue_report
from reduvid.core.sample import SampleEstimate
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


def three_audio_state(tmp_path: Path) -> WizardState:
    state = WizardState(Config())
    add_video(
        state,
        tmp_path,
        "video.mkv",
        media(
            tmp_path / "video.mkv",
            video=VideoStream(0, "h264", 1920, 1080, 24),
            audios=[
                AudioStream(1, "eac3", 6, "spa", True, bitrate=640_000),
                AudioStream(2, "ac3", 6, "spa", False),
                AudioStream(3, "aac", 2, "eng", False, bitrate=128_000),
            ],
            subtitles=[SubtitleStream(4, "subrip", "eng", False, False, False)],
            duration=100.0,
        ),
    )
    return state


def test_step_keep_lists_every_track_of_a_single_video(tmp_path: Path, qapp) -> None:
    state = three_audio_state(tmp_path)
    step = StepKeep(state, ffmpeg())

    assert step.audio_group.title() == "Audio"
    assert list(step.audio_track_checks) == [1, 2, 3]
    assert all(checkbox.isChecked() for checkbox in step.audio_track_checks.values())
    assert step.audio_track_checks[1].text() == "Spanish · eac3 · 5.1 · ~8 MB"
    assert step.audio_track_checks[2].text() == "Spanish · ac3 · 5.1 · —"
    assert step.audio_track_checks[3].text() == "English · aac · Stereo · ~2 MB"
    assert [index for index in step.audio_default_tags] == [1]
    assert step.subtitle_checks["eng"].text() == "English · subrip (text)"
    assert not step.one_audio_per_language.isHidden()
    assert state.options().audio_tracks is None

    step.audio_track_checks[2].setChecked(False)

    assert state.options().audio_tracks == frozenset({1, 3})
    assert step.audio_warning.isHidden()

    step.audio_track_checks[1].setChecked(False)
    step.audio_track_checks[3].setChecked(False)

    assert state.options().audio_tracks == frozenset()
    assert not step.audio_warning.isHidden()
    assert step.audio_warning.text() == (
        "If you do not tick any audio track, all of them are kept."
    )

    step.audio_track_checks[1].setChecked(True)
    step.audio_track_checks[2].setChecked(True)
    step.audio_track_checks[3].setChecked(True)

    assert state.options().audio_tracks is None
    assert step.audio_warning.isHidden()


def test_step_keep_shows_subtitle_track_sizes(tmp_path: Path, qapp) -> None:
    state = WizardState(Config())
    add_video(
        state,
        tmp_path,
        "subtitles.mkv",
        media(
            tmp_path / "subtitles.mkv",
            video=VideoStream(0, "h264", 1920, 1080, 24),
            subtitles=[
                SubtitleStream(1, "subrip", "spa", False, False, False, size_bytes=42_000),
                SubtitleStream(
                    2,
                    "hdmv_pgs_subtitle",
                    "eng",
                    True,
                    False,
                    False,
                    size_bytes=1_200_000,
                ),
                SubtitleStream(3, "subrip", "fra", False, False, False),
            ],
        ),
    )
    step = StepKeep(state, ffmpeg())

    assert step.subtitle_checks["spa"].text() == "Spanish · subrip (text) · ~42 KB"
    assert step.subtitle_checks["eng"].text() == ("English · hdmv_pgs_subtitle (image) · ~1 MB")
    assert step.subtitle_checks["fra"].text() == "French · subrip (text)"


def test_step_keep_goes_back_to_languages_with_two_videos(tmp_path: Path, qapp) -> None:
    state = three_audio_state(tmp_path)
    step = StepKeep(state, ffmpeg())

    assert set(step.audio_track_checks) == {1, 2, 3}

    add_video(
        state,
        tmp_path,
        "second.mkv",
        media(
            tmp_path / "second.mkv",
            video=VideoStream(0, "h264", 1920, 1080, 24),
            audios=[
                AudioStream(1, "aac", 2, "eng", True),
                AudioStream(2, "aac", 2, "spa", False),
            ],
            subtitles=[SubtitleStream(3, "subrip", "eng", False, False, False)],
        ),
    )

    assert step.audio_group.title() == "Audio languages"
    assert step.audio_track_checks == {}
    assert set(step.audio_checks) == {"eng", "spa"}
    assert state.options().audio_tracks is None
    assert state.options().audio_languages is None

    step.audio_checks["spa"].setChecked(False)

    assert state.options().audio_languages == frozenset({"eng"})
    assert step.audio_warning.isHidden()

    step.audio_checks["eng"].setChecked(False)

    assert state.options().audio_languages == frozenset()
    assert not step.audio_warning.isHidden()

    step.one_audio_per_language.click()

    assert state.one_audio_per_language is True
    assert state.options().one_audio_per_language is True

    step.audio_checks["spa"].setChecked(True)

    # Picking languages is compatible with one track per language, so it stays on.
    assert state.one_audio_per_language is True
    assert state.options().audio_languages == frozenset({"spa"})


def test_one_audio_per_language_updates_tracks_and_restores_the_selection(
    tmp_path: Path, qapp
) -> None:
    state = WizardState(Config())
    add_video(
        state,
        tmp_path,
        "video.mkv",
        media(
            tmp_path / "video.mkv",
            video=VideoStream(0, "h264", 1920, 1080, 24),
            audios=[
                AudioStream(1, "eac3", 6, "spa", True, bitrate=640_000),
                AudioStream(2, "ac3", 6, "spa", False, bitrate=384_000),
                AudioStream(3, "aac", 2, "eng", False, bitrate=128_000),
            ],
            duration=100.0,
        ),
    )
    step = StepKeep(state, ffmpeg())
    initial_size = step.audio_size_summary.text()

    assert initial_size == "The audio goes from ~14 MB to ~11 MB"

    step.one_audio_per_language.click()

    assert state.one_audio_per_language is True
    assert [
        index for index, checkbox in step.audio_track_checks.items() if checkbox.isChecked()
    ] == [1, 3]
    assert state.options().audio_tracks == frozenset({1, 3})
    assert step.audio_size_summary.text() == "The audio goes from ~10 MB to ~6 MB"

    step.one_audio_per_language.click()

    assert state.one_audio_per_language is False
    assert all(checkbox.isChecked() for checkbox in step.audio_track_checks.values())
    assert state.options().audio_tracks is None
    assert step.audio_size_summary.text() == initial_size

    step.one_audio_per_language.click()
    step.audio_track_checks[3].setChecked(False)

    assert state.one_audio_per_language is False
    assert [
        index for index, checkbox in step.audio_track_checks.items() if checkbox.isChecked()
    ] == [1]
    assert state.options().audio_tracks == frozenset({1})

    step.one_audio_per_language.click()
    step.one_audio_per_language.click()

    assert state.options().audio_tracks == frozenset({1})
    assert [
        index for index, checkbox in step.audio_track_checks.items() if checkbox.isChecked()
    ] == [1]


def test_step_keep_reduces_the_audio_and_shows_both_sizes(tmp_path: Path, qapp) -> None:
    state = WizardState(Config())
    add_video(
        state,
        tmp_path,
        "video.mkv",
        media(
            tmp_path / "video.mkv",
            video=VideoStream(0, "h264", 1920, 1080, 24),
            audios=[
                AudioStream(1, "eac3", 6, "spa", True, bitrate=640_000),
                AudioStream(2, "ac3", 6, "eng", False, bitrate=640_000),
            ],
            duration=100.0,
        ),
    )
    step = StepKeep(state, ffmpeg())

    assert not step.audio_weight_group.isHidden()
    assert step.audio_size_summary.text() == "The audio goes from ~16 MB to ~10 MB"
    assert not step.reduce_audio.isChecked()

    step.reduce_audio.click()

    assert state.reduce_audio is True
    assert state.options().reduce_audio is True
    assert step.audio_size_summary.text() == "The audio goes from ~16 MB to ~6 MB"


def test_step_keep_explains_when_the_audio_size_is_unknown(tmp_path: Path, qapp) -> None:
    state = WizardState(Config())
    add_video(
        state,
        tmp_path,
        "video.mkv",
        media(
            tmp_path / "video.mkv",
            video=VideoStream(0, "h264", 1920, 1080, 24),
            audios=[AudioStream(1, "aac", 6, "spa", True)],
            duration=100.0,
        ),
    )
    step = StepKeep(state, ffmpeg())

    assert step.audio_size_summary.text() == ("The audio size of this video cannot be estimated.")


def test_step_keep_explains_the_container_and_groups_subtitles(tmp_path: Path, qapp) -> None:
    state = WizardState(Config())
    add_video(
        state,
        tmp_path,
        "video.mkv",
        media(
            tmp_path / "video.mkv",
            video=VideoStream(0, "h264", 1920, 1080, 24),
            subtitles=[
                SubtitleStream(4, "subrip", "spa", False, False, False),
                SubtitleStream(5, "hdmv_pgs_subtitle", "spa", True, False, False),
            ],
        ),
    )
    step = StepKeep(state, ffmpeg())

    assert step.subtitle_checks["spa"].text() == (
        "Spanish · subrip (text), hdmv_pgs_subtitle (image)"
    )
    assert not step.subtitle_container_note.isHidden()
    assert step.subtitle_container_note.text() == (
        "Image subtitles do not fit in MP4 and will be dropped. Text ones are kept."
    )

    state.set_container("mkv")

    assert step.subtitle_container_note.text() == (
        "Image subtitles are kept in MKV, but Cinecat cannot show them."
    )

    state.set_container("mp4")

    assert step.subtitle_container_note.text() == (
        "Image subtitles do not fit in MP4 and will be dropped. Text ones are kept."
    )

    text_only = WizardState(Config())
    add_video(
        text_only,
        tmp_path,
        "text.mkv",
        media(
            tmp_path / "text.mkv",
            video=VideoStream(0, "h264", 1920, 1080, 24),
            subtitles=[SubtitleStream(4, "subrip", "eng", False, False, False)],
        ),
    )
    text_step = StepKeep(text_only, ffmpeg())

    assert text_step.subtitle_container_note.isHidden()


def test_step_keep_without_videos_keeps_the_empty_texts(tmp_path: Path, qapp) -> None:
    step = StepKeep(WizardState(Config()), ffmpeg())

    texts = [label.text() for label in step.findChildren(QLabel)]
    assert "Add videos to see their audio languages." in texts
    assert "Add videos to see their subtitle languages." in texts
    assert step.audio_track_checks == {}
    assert step.subtitle_checks == {}
    assert step.audio_weight_group.isHidden()
    assert step.subtitle_container_note.isHidden()


@pytest.mark.parametrize(("theme", "mode"), sorted(THEMES))
def test_step_keep_builds_with_every_theme(theme: str, mode: str, tmp_path: Path, qapp) -> None:
    ThemeManager(qapp).apply(theme, mode)
    state = three_audio_state(tmp_path)

    step = StepKeep(state, ffmpeg())

    assert step.findChild(QLabel, "audioSizeSummary") is not None
    assert step.findChild(QLabel, "subtitleContainerNote") is not None


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

    assert state.container is None
    assert step.container_cards["mp4"].isChecked()
    assert step.container_cards["mp4"].tag_label.text() == "Recommended"
    assert step.container_cards["mp4"].description_label.text() == "Plays directly in Cinecat"
    assert step.container_cards["mkv"].tag_label.text() == ""
    assert "Cinecat will convert it" in step.container_cards["mkv"].description_label.text()

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
    assert step.container_cards["mkv"].isChecked()
    assert step.container_cards["mkv"].tag_label.text() == "Recommended"
    assert step.container_cards["mp4"].tag_label.text() == "More compatible"
    step.container_cards["mp4"].click()
    assert state.container == "mp4"


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
    expected = warning_text(Warning("image_subtitle_dropped_mp4", {"stream_index": 1}))
    assert expected in labels


def wait_for(predicate, qapp, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            pytest.fail("condition not met before the timeout")
        qapp.processEvents()
        time.sleep(0.01)


def estimate_state(
    tmp_path: Path,
    *,
    bitrate: int | None = 640_000,
    size: int = 6_700_000_000,
    count: int = 1,
) -> WizardState:
    state = WizardState(Config())
    for index in range(count):
        name = f"movie{index}.mkv"
        add_video(
            state,
            tmp_path,
            name,
            media(
                tmp_path / name,
                video=VideoStream(0, "h264", 1920, 1080, 24),
                audios=[AudioStream(1, "aac", 2, "eng", True, bitrate=bitrate)],
                size=size,
                duration=100.0,
            ),
        )
    return state


def install_sample_runner(
    monkeypatch: pytest.MonkeyPatch,
    *,
    video_bytes: int = 350_000_000,
    paused: bool = False,
) -> list:
    instances: list = []

    class Runner:
        def __init__(
            self,
            _ffmpeg,
            _media,
            _plan,
            _input,
            *,
            on_progress=None,
            threads=None,
            hw_decode=False,
        ):
            self.on_progress = on_progress
            self.hw_decode = hw_decode
            self.started = threading.Event()
            self.release = threading.Event()
            self.cancelled = False
            instances.append(self)

        def run(self) -> SampleEstimate:
            if self.on_progress is not None:
                self.on_progress(0.5)
            if paused:
                self.started.set()
                self.release.wait(timeout=10)
            for value in (0.75, 1.0):
                if self.on_progress is not None:
                    self.on_progress(value)
            if self.cancelled:
                raise PipelineError("cancelled", "Sampling was cancelled.")
            return SampleEstimate(video_bytes, 10.0, 5.0)

        def cancel(self) -> None:
            self.cancelled = True
            self.release.set()

    monkeypatch.setattr("reduvid.gui.workers.SampleRunner", Runner)
    return instances


def test_summary_estimates_the_final_size_from_a_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp
) -> None:
    state = estimate_state(tmp_path)
    summary = StepSummary(state, ffmpeg())
    path = state.videos[0].path
    button = summary.estimate_buttons[path]
    bar = summary.estimate_progress_bars[path]
    cancel = summary.estimate_cancel_buttons[path]
    result = summary.estimate_results[path]
    assert button.text() == "Estimate the final size (1-minute test)"
    assert bar.isHidden()
    assert cancel.isHidden()
    assert result.isHidden()
    instances = install_sample_runner(monkeypatch, paused=True)

    button.click()

    assert not bar.isHidden()
    wait_for(lambda: instances and instances[0].started.is_set(), qapp)
    wait_for(lambda: bar.value() == 50, qapp)
    instances[0].release.set()
    wait_for(lambda: not result.isHidden(), qapp)

    assert result.text() == (
        "Estimated size: ~3.5 GB (from 6.7 GB: −48 %) · Approx. time: 0:50"  # noqa: RUF001
    )
    wait_for(lambda: summary.estimating_path is None, qapp)
    assert bar.isHidden()
    assert cancel.isHidden()
    assert button.isEnabled()
    assert summary.start_button.isEnabled()


def test_summary_cancel_returns_to_the_initial_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp
) -> None:
    state = estimate_state(tmp_path)
    summary = StepSummary(state, ffmpeg())
    path = state.videos[0].path
    instances = install_sample_runner(monkeypatch, paused=True)

    summary.estimate_buttons[path].click()
    wait_for(lambda: instances and instances[0].started.is_set(), qapp)

    summary.estimate_cancel_buttons[path].click()

    assert instances[0].cancelled
    assert summary.estimating_path is None
    assert summary.estimate_progress_bars[path].isHidden()
    assert summary.estimate_cancel_buttons[path].isHidden()
    assert summary.estimate_results[path].isHidden()
    assert summary.estimate_buttons[path].isEnabled()
    assert summary.start_button.isEnabled()
    assert summary._estimate_thread is None


def test_summary_estimate_is_invalidated_when_options_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp
) -> None:
    state = estimate_state(tmp_path)
    summary = StepSummary(state, ffmpeg())
    path = state.videos[0].path
    install_sample_runner(monkeypatch)

    summary.estimate_buttons[path].click()
    wait_for(lambda: not summary.estimate_results[path].isHidden(), qapp)
    wait_for(lambda: summary.estimating_path is None, qapp)

    summary.refresh()

    assert not summary.estimate_results[path].isHidden()

    state.set_quality("high")
    summary.refresh()

    assert summary.estimate_results[path].isHidden()
    assert summary.estimate_buttons[path].isEnabled()


def test_summary_estimate_without_the_audio_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp
) -> None:
    state = estimate_state(tmp_path, bitrate=None)
    summary = StepSummary(state, ffmpeg())
    path = state.videos[0].path
    install_sample_runner(monkeypatch)

    summary.estimate_buttons[path].click()
    wait_for(lambda: not summary.estimate_results[path].isHidden(), qapp)
    wait_for(lambda: summary.estimating_path is None, qapp)

    assert summary.estimate_results[path].text() == (
        "Estimated size: cannot be calculated without the audio size; "
        "video only: ~3.5 GB · Approx. time: 0:50"
    )


def test_summary_estimate_bigger_than_the_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp
) -> None:
    state = estimate_state(tmp_path)
    summary = StepSummary(state, ffmpeg())
    path = state.videos[0].path
    install_sample_runner(monkeypatch, video_bytes=800_000_000)

    summary.estimate_buttons[path].click()
    wait_for(lambda: not summary.estimate_results[path].isHidden(), qapp)
    wait_for(lambda: summary.estimating_path is None, qapp)

    assert summary.estimate_results[path].text() == (
        "Estimated size: ~8.0 GB (bigger than the original 6.7 GB) · Approx. time: 0:50"
    )


def test_summary_estimates_one_video_at_a_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp
) -> None:
    state = estimate_state(tmp_path, count=2)
    summary = StepSummary(state, ffmpeg())
    first, second = (entry.path for entry in state.videos)
    instances = install_sample_runner(monkeypatch, paused=True)

    summary.estimate_buttons[first].click()
    wait_for(lambda: instances and instances[0].started.is_set(), qapp)

    assert not summary.estimate_buttons[first].isEnabled()
    assert not summary.estimate_buttons[second].isEnabled()
    assert not summary.start_button.isEnabled()

    instances[0].release.set()
    wait_for(lambda: summary.estimating_path is None, qapp)

    assert summary.estimate_buttons[first].isEnabled()
    assert summary.estimate_buttons[second].isEnabled()
    assert summary.start_button.isEnabled()


def test_closing_the_window_cancels_a_running_estimate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp
) -> None:
    window = MainWindow(Config(), ffmpeg(), ThemeManager(qapp))
    state = window.wizard_state
    path = add_video(
        state,
        tmp_path,
        "movie.mkv",
        media(
            tmp_path / "movie.mkv",
            video=VideoStream(0, "h264", 1920, 1080, 24),
            audios=[AudioStream(1, "aac", 2, "eng", True, bitrate=640_000)],
            size=6_700_000_000,
            duration=100.0,
        ),
    )
    window.step_summary.refresh()
    instances = install_sample_runner(monkeypatch, paused=True)

    window.step_summary.estimate_buttons[path].click()
    wait_for(lambda: instances and instances[0].started.is_set(), qapp)

    window.close()

    assert instances[0].cancelled
    assert window.step_summary.estimating_path is None
    assert window.step_summary.estimate_progress_bars[path].isHidden()
    assert window.step_summary._estimate_thread is None


def test_starting_the_conversion_cancels_a_running_estimate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp
) -> None:
    window = MainWindow(Config(), ffmpeg(), ThemeManager(qapp))
    state = window.wizard_state
    path = add_video(
        state,
        tmp_path,
        "movie.mkv",
        media(
            tmp_path / "movie.mkv",
            video=VideoStream(0, "h264", 1920, 1080, 24),
            audios=[AudioStream(1, "aac", 2, "eng", True, bitrate=640_000)],
            size=6_700_000_000,
            duration=100.0,
        ),
    )
    window.step_summary.refresh()
    instances = install_sample_runner(monkeypatch, paused=True)

    window.step_summary.estimate_buttons[path].click()
    wait_for(lambda: instances and instances[0].started.is_set(), qapp)
    monkeypatch.setattr(window, "start_queue", lambda *_args, **_kwargs: FakeWorker())

    window._start_from_summary()

    assert instances[0].cancelled
    assert window.step_summary.estimating_path is None
    assert window.step_summary._estimate_thread is None


@pytest.mark.parametrize(("theme", "mode"), sorted(THEMES))
def test_summary_estimate_row_builds_with_every_theme(
    theme: str, mode: str, tmp_path: Path, qapp
) -> None:
    ThemeManager(qapp).apply(theme, mode)
    state = estimate_state(tmp_path)

    summary = StepSummary(state, ffmpeg())

    assert summary.findChild(QPushButton, "estimateButton") is not None
    assert summary.findChild(QProgressBar, "estimateProgress") is not None
    assert summary.findChild(QPushButton, "estimateCancel") is not None
    result = summary.findChild(QLabel, "estimateResult")
    assert result is not None
    assert result.accessibleName()


def test_summary_scrolls_instead_of_squeezing_rows(tmp_path: Path, qapp) -> None:
    state = WizardState(Config())
    stream = VideoStream(0, "h264", 1920, 1080, 24)
    for number in range(6):
        name = f"video-{number}.mkv"
        audios = [AudioStream(1, "ac3", 6, "spa", True), AudioStream(2, "ac3", 6, "eng", False)]
        add_video(state, tmp_path, name, media(tmp_path / name, video=stream, audios=audios))
    summary = StepSummary(state, ffmpeg())
    summary.resize(400, 300)
    summary.show()
    qapp.processEvents()

    scroll = summary.findChild(QScrollArea, "summaryScroll")
    assert scroll is not None
    assert scroll.widget().height() > scroll.viewport().height()
    rows = summary.items_container.findChildren(QWidget, "summaryRow")
    assert len(rows) == 6
    assert all(row.height() >= row.minimumSizeHint().height() for row in rows)
