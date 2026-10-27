# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from __future__ import annotations

import math
import subprocess
import tempfile
import threading
from itertools import pairwise
from pathlib import Path

import psutil
import pytest

from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.pipeline import PipelineError
from reduvid.core.plan import AudioDecision, EncodePlan, PlanOptions, VideoDecision, build_plan
from reduvid.core.probe import AudioStream, MediaInfo, probe_media
from reduvid.core.sample import (
    SampleEstimate,
    SampleLevelsRunner,
    SampleRunner,
    SampleSegment,
    audio_bytes_for_plan,
    build_sample_command,
    estimate_levels,
    estimate_total,
    run_sample,
    sample_segments,
)

# "/videos/x.mkv" is not absolute on Windows (no drive), so build paths from the cwd's root.
_ROOT = Path(Path.cwd().anchor)


def _video(
    *,
    stream_index: int = 0,
    filters: tuple[str, ...] = (),
    target_height: int | None = None,
    profile: str | None = "high",
) -> VideoDecision:
    return VideoDecision(
        stream_index,
        "encode",
        "libx264",
        23,
        "medium",
        profile,
        "4.1",
        "yuv420p",
        filters,
        target_height,
    )


def _plan(*videos: VideoDecision) -> EncodePlan:
    return EncodePlan("jellyfin", "balanced", "mkv", videos, (), (), ())


def _media(duration: float = 600.0, size: int = 1_000_000_000) -> MediaInfo:
    return MediaInfo(Path("/media/movie.mkv"), "matroska", duration, size, [], [], [], [])


def _starts(segments: tuple[SampleSegment, ...]) -> list[float]:
    return [segment.start for segment in segments]


def test_long_video_is_sampled_near_twenty_fifty_and_eighty_percent() -> None:
    segments = sample_segments(600.0)

    assert _starts(segments) == pytest.approx([110.0, 290.0, 470.0])
    assert [segment.length for segment in segments] == [20.0, 20.0, 20.0]


def test_eighty_nine_seconds_use_a_single_chunk_from_the_start() -> None:
    assert sample_segments(89.0) == (SampleSegment(0.0, 60.0),)


def test_ninety_seconds_are_split_into_three_chunks() -> None:
    segments = sample_segments(90.0)

    assert _starts(segments) == pytest.approx([8.0, 35.0, 62.0])
    assert [segment.length for segment in segments] == [20.0, 20.0, 20.0]


def test_short_video_uses_its_whole_duration() -> None:
    assert sample_segments(10.0) == (SampleSegment(0.0, 10.0),)


@pytest.mark.parametrize("duration", [0.0, -5.0, math.inf, math.nan])
def test_invalid_duration_is_rejected(duration: float) -> None:
    with pytest.raises(ValueError, match="duration must be positive and finite"):
        sample_segments(duration)


@pytest.mark.parametrize("duration", [90.0, 95.5, 120.0, 600.0, 7200.0])
def test_chunks_never_overlap_or_pass_the_end(duration: float) -> None:
    segments = sample_segments(duration)

    assert len(segments) == 3
    for previous, following in pairwise(segments):
        assert following.start >= previous.start + previous.length
    for segment in segments:
        assert segment.start >= 0
        assert segment.start + segment.length <= duration


def test_build_sample_command_encodes_only_video_with_the_plan_adjustments() -> None:
    input_path = _ROOT / "videos" / "input.mkv"
    output_path = _ROOT / "temporaries" / "segment-0.mkv"

    arguments = build_sample_command(
        _plan(_video()), input_path, output_path, SampleSegment(8.0, 20.0)
    )

    assert arguments == [
        "-nostdin",
        "-hide_banner",
        "-y",
        "-ss",
        "8",
        "-t",
        "20",
        "-i",
        str(input_path),
        "-map",
        "0:0",
        "-c:v:0",
        "libx264",
        "-crf:v:0",
        "23",
        "-preset:v:0",
        "medium",
        "-profile:v:0",
        "high",
        "-level:v:0",
        "4.1",
        "-pix_fmt:v:0",
        "yuv420p",
        "-map_metadata",
        "-1",
        "-map_chapters",
        "-1",
        "-an",
        "-sn",
        "-f",
        "matroska",
        str(output_path),
    ]


def test_build_sample_command_shares_the_scale_and_filter_arguments() -> None:
    arguments = build_sample_command(
        _plan(_video(filters=("zscale", "tonemap"), target_height=720)),
        _ROOT / "videos" / "input.mkv",
        _ROOT / "temporaries" / "segment-0.mkv",
        SampleSegment(0.0, 20.0),
    )

    assert arguments[arguments.index("-filter:v:0") + 1] == "zscale,tonemap,scale=-2:720"


def test_build_sample_command_maps_only_the_first_video_of_the_plan() -> None:
    arguments = build_sample_command(
        _plan(_video(stream_index=0, profile=None), _video(stream_index=2)),
        _ROOT / "videos" / "input.mkv",
        _ROOT / "temporaries" / "segment-0.mkv",
        SampleSegment(0.0, 20.0),
    )

    assert arguments.count("-map") == 1
    assert arguments[arguments.index("-map") + 1] == "0:0"
    assert "0:2" not in arguments
    assert "-c:v:1" not in arguments
    assert "-profile:v:0" not in arguments
    assert "-level:v:0" in arguments


def test_build_sample_command_keeps_paths_as_independent_items() -> None:
    input_path = Path.cwd() / "vídeo áéñ 😀" / "-raro.mkv"
    output_path = Path.cwd() / "temporales con espacios" / "ñ 😀.mkv"

    arguments = build_sample_command(
        _plan(_video()), input_path, output_path, SampleSegment(0.0, 20.0)
    )

    assert arguments[arguments.index("-i") + 1] == str(input_path)
    assert arguments[-1] == str(output_path)
    assert "-raro.mkv" not in arguments


@pytest.mark.parametrize(
    ("input_path", "output_path"),
    [
        (Path("relative.mkv"), _ROOT / "temporaries" / "segment-0.mkv"),
        (_ROOT / "videos" / "input.mkv", Path("relative.mkv")),
    ],
)
def test_build_sample_command_rejects_relative_paths(input_path: Path, output_path: Path) -> None:
    with pytest.raises(ValueError, match="must be absolute"):
        build_sample_command(_plan(_video()), input_path, output_path, SampleSegment(0.0, 20.0))


def test_build_sample_command_requires_a_video_stream() -> None:
    with pytest.raises(ValueError, match="plan has no video streams"):
        build_sample_command(
            _plan(),
            _ROOT / "videos" / "input.mkv",
            _ROOT / "temporaries" / "segment-0.mkv",
            SampleSegment(0.0, 20.0),
        )


def test_estimate_total_scales_video_and_adds_the_other_tracks() -> None:
    sample = SampleEstimate(video_bytes=2_000_000, sampled_seconds=60.0, elapsed_seconds=30.0)

    total = estimate_total(sample, _media(), audio_bytes=10_000_000, subtitle_bytes=1_000)

    assert total.video_bytes == 20_000_000
    assert total.audio_bytes == 10_000_000
    assert total.subtitle_bytes == 1_000
    assert total.total_bytes == 30_001_000
    assert total.ratio_vs_original == pytest.approx(0.030001)
    assert total.encode_seconds == pytest.approx(300.0)


def test_estimate_total_without_audio_leaves_the_total_unknown() -> None:
    sample = SampleEstimate(video_bytes=2_000_000, sampled_seconds=60.0, elapsed_seconds=30.0)

    total = estimate_total(sample, _media(), audio_bytes=None)

    assert total.video_bytes == 20_000_000
    assert total.audio_bytes is None
    assert total.subtitle_bytes == 0
    assert total.total_bytes is None
    assert total.ratio_vs_original is None
    assert total.encode_seconds == pytest.approx(300.0)


def test_estimate_total_omits_the_ratio_when_the_original_size_is_unknown() -> None:
    sample = SampleEstimate(video_bytes=2_000_000, sampled_seconds=60.0, elapsed_seconds=30.0)

    total = estimate_total(sample, _media(size=0), audio_bytes=1_000_000)

    assert total.total_bytes == 21_000_000
    assert total.ratio_vs_original is None


@pytest.mark.parametrize("duration", [0.0, math.inf])
def test_estimate_total_rejects_an_invalid_video_duration(duration: float) -> None:
    sample = SampleEstimate(video_bytes=2_000_000, sampled_seconds=60.0, elapsed_seconds=30.0)

    with pytest.raises(ValueError, match=r"media\.duration must be positive and finite"):
        estimate_total(sample, _media(duration=duration), audio_bytes=1_000_000)


def test_estimate_total_requires_a_measured_length() -> None:
    sample = SampleEstimate(video_bytes=2_000_000, sampled_seconds=0.0, elapsed_seconds=30.0)

    with pytest.raises(ValueError, match="sampled_seconds must be positive"):
        estimate_total(sample, _media(), audio_bytes=1_000_000)


def test_video_bytes_per_second_divides_the_measured_output() -> None:
    sample = SampleEstimate(video_bytes=1_500_000, sampled_seconds=60.0, elapsed_seconds=30.0)

    assert sample.video_bytes_per_second == pytest.approx(25_000.0)


def _audio_media(*bitrates: int | None) -> MediaInfo:
    return MediaInfo(
        Path("/media/movie.mkv"),
        "matroska",
        100.0,
        1_000_000,
        [],
        [
            AudioStream(index + 1, "eac3", 6, "eng", index == 0, bitrate=bitrate)
            for index, bitrate in enumerate(bitrates)
        ],
        [],
        [],
    )


def test_audio_bytes_for_plan_sums_current_and_final_tracks() -> None:
    media = _audio_media(640_000, 500_000)
    plan = EncodePlan(
        "jellyfin",
        "balanced",
        "mkv",
        (),
        (AudioDecision(1, "copy"), AudioDecision(2, "encode", "aac", "128k")),
        (),
        (),
    )

    current, final = audio_bytes_for_plan(media, plan)

    assert current == 8_000_000 + 6_250_000
    assert final == 8_000_000 + 1_600_000


def test_audio_bytes_for_plan_is_unknown_when_a_bitrate_is_missing() -> None:
    media = _audio_media(640_000, None)
    plan = EncodePlan(
        "jellyfin",
        "balanced",
        "mkv",
        (),
        (AudioDecision(1, "copy"), AudioDecision(2, "copy")),
        (),
        (),
    )

    assert audio_bytes_for_plan(media, plan) == (None, None)


def test_audio_bytes_for_plan_without_audio_tracks_is_zero() -> None:
    plan = EncodePlan("jellyfin", "balanced", "mkv", (), (), (), ())

    assert audio_bytes_for_plan(_audio_media(), plan) == (0, 0)


def _sample_destination(ffmpeg_info: FFmpegInfo) -> str:
    if ffmpeg_info.has_libx264:
        return "jellyfin"
    if ffmpeg_info.has_libx265:
        return "modern"
    pytest.skip("FFmpeg H.264/H.265 encoder not available")


@pytest.fixture
def hundred_second_video(ffmpeg_info: FFmpegInfo, tmp_path: Path) -> Path:
    """Build a ~100 s source so the three default chunks fit without overlapping."""
    output_path = tmp_path / "sample-source.mkv"
    subprocess.run(
        [
            str(ffmpeg_info.ffmpeg_path),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=duration=100:size=320x180:rate=25",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "35",
            "-an",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return output_path.resolve()


def _temporaries() -> set[Path]:
    return set(Path(tempfile.gettempdir()).glob("reduvid-sample-*"))


def _sample_processes(video: Path) -> list[psutil.Process]:
    processes: list[psutil.Process] = []
    for process in psutil.process_iter(["cmdline"]):
        command = process.info["cmdline"] or []
        if str(video) in command:
            processes.append(process)
    return processes


@pytest.mark.ffmpeg
def test_sample_measures_a_positive_rate_and_removes_temporaries(
    ffmpeg_info: FFmpegInfo, hundred_second_video: Path
) -> None:
    before = _temporaries()
    media = probe_media(ffmpeg_info.ffprobe_path, hundred_second_video)
    plan = build_plan(media, ffmpeg_info, PlanOptions(destination=_sample_destination(ffmpeg_info)))
    progress: list[float] = []

    sample = run_sample(
        ffmpeg_info.ffmpeg_path,
        media,
        plan,
        hundred_second_video,
        on_progress=progress.append,
        threads=2,
    )

    assert sample.video_bytes > 0
    assert sample.sampled_seconds == pytest.approx(60.0, abs=1.0)
    assert sample.elapsed_seconds > 0
    assert sample.video_bytes_per_second > 0
    assert progress
    assert all(0.0 <= value <= 1.0 for value in progress)
    assert progress[-1] > 0.9
    total = estimate_total(sample, media, audio_bytes=1_000_000)
    assert total.video_bytes > 0
    assert total.total_bytes is not None and total.total_bytes > total.video_bytes
    assert total.encode_seconds > 0
    assert _temporaries() == before


@pytest.mark.ffmpeg
def test_cancel_stops_the_sample_without_leftover_processes_or_temporaries(
    ffmpeg_info: FFmpegInfo, hundred_second_video: Path
) -> None:
    before = _temporaries()
    assert _sample_processes(hundred_second_video) == []
    media = probe_media(ffmpeg_info.ffprobe_path, hundred_second_video)
    plan = build_plan(media, ffmpeg_info, PlanOptions(destination=_sample_destination(ffmpeg_info)))
    started = threading.Event()
    runner = SampleRunner(
        ffmpeg_info.ffmpeg_path,
        media,
        plan,
        hundred_second_video,
        on_progress=lambda value: started.set() if value > 0 else None,
        threads=2,
    )
    errors: list[BaseException] = []

    def run() -> None:
        try:
            runner.run()
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(target=run)
    thread.start()
    assert started.wait(timeout=15)
    runner.cancel()
    thread.join(timeout=20)

    assert not thread.is_alive()
    assert len(errors) == 1
    error = errors[0]
    assert isinstance(error, PipelineError)
    assert error.code == "cancelled"
    assert _temporaries() == before
    assert _sample_processes(hundred_second_video) == []


def _ffmpeg_info() -> FFmpegInfo:
    return FFmpegInfo(
        Path("/usr/bin/ffmpeg"),
        Path("/usr/bin/ffprobe"),
        "test",
        frozenset(),
        frozenset(),
        (),
    )


def _levels_runner(*qualities: str) -> SampleLevelsRunner:
    return SampleLevelsRunner(
        Path("/usr/bin/ffmpeg"),
        _media(),
        Path("/media/movie.mkv"),
        PlanOptions(),
        _ffmpeg_info(),
        qualities,
    )


def test_estimate_levels_requires_at_least_one_quality() -> None:
    with pytest.raises(ValueError, match="qualities must not be empty"):
        estimate_levels(
            Path("/usr/bin/ffmpeg"),
            _media(),
            Path("/media/movie.mkv"),
            PlanOptions(),
            _ffmpeg_info(),
            qualities=(),
        )


def test_estimate_levels_returns_estimates_in_the_requested_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, int, float]] = []

    class FakeRunner:
        def __init__(
            self,
            ffmpeg_path: object,
            media: object,
            plan: EncodePlan,
            input_path: object,
            on_progress: object = None,
            threads: object = None,
            segments: int = 3,
            length: float = 20.0,
        ) -> None:
            seen.append((plan.quality, segments, length))
            self.on_progress = on_progress

        def run(self) -> SampleEstimate:
            return SampleEstimate(1_000_000, 20.0, 10.0)

    monkeypatch.setattr("reduvid.core.sample.SampleRunner", FakeRunner)

    estimates = estimate_levels(
        Path("/usr/bin/ffmpeg"),
        _media(),
        Path("/media/movie.mkv"),
        PlanOptions(),
        _ffmpeg_info(),
        qualities=("max_savings", "high"),
        segments=1,
        length=20.0,
    )

    assert list(estimates) == ["max_savings", "high"]
    assert seen == [("max_savings", 1, 20.0), ("high", 1, 20.0)]
    assert estimates["high"].video_bytes == 30_000_000


def test_estimate_levels_reports_monotonic_aggregated_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeRunner:
        def __init__(self, *args: object, on_progress: object = None, **kwargs: object) -> None:
            self.on_progress = on_progress

        def run(self) -> SampleEstimate:
            if callable(self.on_progress):
                self.on_progress(0.25)
                self.on_progress(1.0)
            return SampleEstimate(1_000_000, 20.0, 10.0)

    monkeypatch.setattr("reduvid.core.sample.SampleRunner", FakeRunner)
    progress: list[float] = []

    estimate_levels(
        Path("/usr/bin/ffmpeg"),
        _media(),
        Path("/media/movie.mkv"),
        PlanOptions(),
        _ffmpeg_info(),
        qualities=("high", "balanced"),
        on_progress=progress.append,
    )

    assert progress == sorted(progress)
    assert progress[0] == pytest.approx(0.125)
    assert progress[-1] == pytest.approx(1.0)


def test_cancelled_levels_runner_raises_before_starting_the_next_level() -> None:
    runner = _levels_runner("high", "balanced")
    runner.cancel()

    with pytest.raises(PipelineError) as error:
        runner.run()

    assert error.value.code == "cancelled"


@pytest.mark.ffmpeg
def test_estimate_levels_orders_video_bytes_from_high_to_max_savings(
    ffmpeg_info: FFmpegInfo, hundred_second_video: Path
) -> None:
    media = probe_media(ffmpeg_info.ffprobe_path, hundred_second_video)
    options = PlanOptions(destination=_sample_destination(ffmpeg_info))

    estimates = estimate_levels(
        ffmpeg_info.ffmpeg_path,
        media,
        hundred_second_video,
        options,
        ffmpeg_info,
        qualities=("high", "balanced", "max_savings"),
        threads=2,
        segments=1,
        length=20.0,
    )

    assert list(estimates) == ["high", "balanced", "max_savings"]
    assert estimates["high"].video_bytes >= estimates["balanced"].video_bytes
    assert estimates["balanced"].video_bytes >= estimates["max_savings"].video_bytes
    assert estimates["high"].video_bytes > 0
