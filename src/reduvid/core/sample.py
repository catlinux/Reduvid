# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Estimate the final size and time of an encode from a short video sample."""

from __future__ import annotations

import math
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from reduvid.core.command import build_video_arguments
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.pipeline import PipelineError
from reduvid.core.plan import AudioDecision, EncodePlan, PlanOptions, build_plan
from reduvid.core.probe import MediaInfo, estimate_stream_bytes, parse_bitrate
from reduvid.core.runner import EncodeHandle, ProgressEvent

_TEMP_PREFIX = "reduvid-sample-"
_CANCELLED_DETAIL = "Sampling was cancelled."


@dataclass(frozen=True)
class SampleSegment:
    """One chunk of the source used to measure the encoder output rate."""

    start: float
    length: float


@dataclass(frozen=True)
class SampleEstimate:
    """Measured output of the sample chunks and the time they took."""

    video_bytes: int
    sampled_seconds: float
    elapsed_seconds: float

    @property
    def video_bytes_per_second(self) -> float:
        """Output video bytes produced per second of source video measured."""
        if self.sampled_seconds <= 0:
            return 0.0
        return self.video_bytes / self.sampled_seconds


@dataclass(frozen=True)
class TotalEstimate:
    """Estimated size and time for the whole file, from a :class:`SampleEstimate`."""

    video_bytes: int
    audio_bytes: int | None
    subtitle_bytes: int
    total_bytes: int | None
    ratio_vs_original: float | None
    encode_seconds: float


def sample_segments(
    duration: float,
    count: int = 3,
    length: float = 20.0,
    fractions: tuple[float, ...] = (0.2, 0.5, 0.8),
) -> tuple[SampleSegment, ...]:
    """Return non-overlapping chunks spread over ``duration``.

    Short files get one chunk from the start: splitting them would sample most of
    the file and cost almost as much as the full encode.
    """
    if count < 1 or length <= 0:
        raise ValueError("count and length must be positive")
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("duration must be positive and finite")

    # At 90 s with the defaults the chunks already cover two thirds of the file;
    # below that, splitting costs almost as much as encoding everything once.
    if duration < count * length * 1.5:
        return (SampleSegment(0.0, min(duration, count * length)),)

    segments: list[SampleSegment] = []
    for fraction in fractions[:count]:
        start = max(0.0, min(duration * fraction - length / 2, duration - length))
        if segments:
            start = max(start, segments[-1].start + length)
        if start + length > duration:
            break
        segments.append(SampleSegment(start, length))
    return tuple(segments)


def build_sample_command(
    plan: EncodePlan, input_path: Path, output_path: Path, segment: SampleSegment
) -> list[str]:
    """Return FFmpeg arguments that encode one sample chunk as Matroska.

    Measure what the plan will produce, so the first video stream keeps its
    adjustments while audio and subtitles are left out.
    """
    if not input_path.is_absolute():
        raise ValueError("input_path must be absolute")
    if not output_path.is_absolute():
        raise ValueError("output_path must be absolute")
    if not plan.videos:
        raise ValueError("plan has no video streams")

    arguments = [
        "-nostdin",
        "-hide_banner",
        "-y",
        "-ss",
        _seconds(segment.start),
        "-t",
        _seconds(segment.length),
        "-i",
        str(input_path),
    ]
    arguments.extend(build_video_arguments(plan.videos[0], 0))
    arguments.extend(
        [
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
    )
    return arguments


class SampleRunner:
    """Run the sample chunks in series, exposing pause, resume and cancel.

    Controls may be called from other threads; the temporaries live in their own
    directory and are removed even when the sample is cancelled.
    """

    def __init__(
        self,
        ffmpeg_path: str | Path,
        media: MediaInfo,
        plan: EncodePlan,
        input_path: Path,
        on_progress: Callable[[float], None] | None = None,
        threads: int | None = None,
        segments: int = 3,
        length: float = 20.0,
    ) -> None:
        self.ffmpeg_path = ffmpeg_path
        self.media = media
        self.plan = plan
        self.input_path = input_path
        self.on_progress = on_progress
        self.threads = threads
        self.segments = segments
        self.length = length
        self._lock = threading.Lock()
        self._handle: EncodeHandle | None = None
        self._cancelled = False

    def run(self) -> SampleEstimate:
        """Measure the sample chunks and return the result or raise ``PipelineError``."""
        if not self.input_path.is_absolute():
            raise ValueError("input_path must be absolute")
        if not self.plan.videos:
            raise ValueError("plan has no video streams")

        segments = sample_segments(self.media.duration, self.segments, self.length)
        started = time.monotonic()
        video_bytes = 0
        sampled_seconds = 0.0
        with tempfile.TemporaryDirectory(prefix=_TEMP_PREFIX) as temp_directory:
            directory = Path(temp_directory)
            for position, segment in enumerate(segments):
                if self._is_cancelled():
                    raise PipelineError("cancelled", _CANCELLED_DETAIL)
                output_path = directory / f"segment-{position}.mkv"
                handle = EncodeHandle(
                    build_sample_command(self.plan, self.input_path, output_path, segment),
                    segment.length,
                    output_path,
                    on_progress=self._progress_reporter(position, len(segments), segment.length),
                    threads=self.threads,
                    ffmpeg_path=self.ffmpeg_path,
                )
                with self._lock:
                    cancelled_early = self._cancelled
                    self._handle = handle
                if cancelled_early:
                    handle.cancel()
                try:
                    result = handle.run()
                finally:
                    with self._lock:
                        self._handle = None
                if result.cancelled:
                    raise PipelineError("cancelled", _CANCELLED_DETAIL)
                video_bytes += output_path.stat().st_size
                sampled_seconds += _sampled_length(result.last_progress, segment.length)

        return SampleEstimate(video_bytes, sampled_seconds, time.monotonic() - started)

    def pause(self) -> None:
        """Suspend the running chunk, if any."""
        handle = self._current_handle()
        if handle is not None:
            handle.pause()

    def resume(self) -> None:
        """Resume a paused chunk, if any."""
        handle = self._current_handle()
        if handle is not None:
            handle.resume()

    def cancel(self) -> None:
        """Stop the running chunk and prevent the next one from starting."""
        with self._lock:
            self._cancelled = True
            handle = self._handle
        if handle is not None:
            handle.cancel()

    def _is_cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    def _current_handle(self) -> EncodeHandle | None:
        with self._lock:
            return self._handle

    def _progress_reporter(
        self, position: int, count: int, length: float
    ) -> Callable[[ProgressEvent], None]:
        def report(event: ProgressEvent) -> None:
            if self.on_progress is None:
                return
            fraction = min(max(event.tiempo_procesado_segundos / length, 0.0), 1.0)
            self.on_progress(min((position + fraction) / count, 1.0))

        return report


class SampleLevelsRunner:
    """Measure several quality levels in series, exposing pause, resume and cancel.

    Each level contributes the same share of the reported progress, so callers see
    one aggregate fraction instead of one jump back to zero per level.
    """

    def __init__(
        self,
        ffmpeg_path: str | Path,
        media: MediaInfo,
        input_path: Path,
        options: PlanOptions,
        ffmpeg_info: FFmpegInfo,
        qualities: tuple[str, ...] = ("high", "balanced", "max_savings"),
        on_progress: Callable[[float], None] | None = None,
        threads: int | None = None,
        segments: int = 1,
        length: float = 20.0,
    ) -> None:
        self.ffmpeg_path = ffmpeg_path
        self.media = media
        self.input_path = input_path
        self.options = options
        self.ffmpeg_info = ffmpeg_info
        self.qualities = qualities
        self.on_progress = on_progress
        self.threads = threads
        self.segments = segments
        self.length = length
        self._lock = threading.Lock()
        self._runner: SampleRunner | None = None
        self._cancelled = False

    def run(self) -> dict[str, TotalEstimate]:
        """Measure every quality level and return one estimate per level."""
        if not self.qualities:
            raise ValueError("qualities must not be empty")

        estimates: dict[str, TotalEstimate] = {}
        count = len(self.qualities)
        for position, quality in enumerate(self.qualities):
            if self._is_cancelled():
                raise PipelineError("cancelled", _CANCELLED_DETAIL)
            plan = build_plan(self.media, self.ffmpeg_info, replace(self.options, quality=quality))
            runner = SampleRunner(
                self.ffmpeg_path,
                self.media,
                plan,
                self.input_path,
                on_progress=self._progress_reporter(position, count),
                threads=self.threads,
                segments=self.segments,
                length=self.length,
            )
            with self._lock:
                cancelled_early = self._cancelled
                self._runner = runner
            if cancelled_early:
                runner.cancel()
            try:
                sample = runner.run()
            finally:
                with self._lock:
                    self._runner = None
            if self._is_cancelled():
                raise PipelineError("cancelled", _CANCELLED_DETAIL)
            audio_bytes = audio_bytes_for_plan(self.media, plan)[1]
            estimates[quality] = estimate_total(sample, self.media, audio_bytes)
            if self.on_progress is not None:
                self.on_progress((position + 1) / count)
        return estimates

    def pause(self) -> None:
        """Suspend the running level, if any."""
        runner = self._current_runner()
        if runner is not None:
            runner.pause()

    def resume(self) -> None:
        """Resume a paused level, if any."""
        runner = self._current_runner()
        if runner is not None:
            runner.resume()

    def cancel(self) -> None:
        """Stop the running level and prevent the next one from starting."""
        with self._lock:
            self._cancelled = True
            runner = self._runner
        if runner is not None:
            runner.cancel()

    def _is_cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    def _current_runner(self) -> SampleRunner | None:
        with self._lock:
            return self._runner

    def _progress_reporter(self, position: int, count: int) -> Callable[[float], None]:
        def report(value: float) -> None:
            if self.on_progress is None:
                return
            fraction = min(max(value, 0.0), 1.0)
            self.on_progress((position + fraction) / count)

        return report


def run_sample(
    ffmpeg_path: str | Path,
    media: MediaInfo,
    plan: EncodePlan,
    input_path: Path,
    on_progress: Callable[[float], None] | None = None,
    threads: int | None = None,
    segments: int = 3,
    length: float = 20.0,
) -> SampleEstimate:
    """Run the sample chunks in series and return the measured rate."""
    return SampleRunner(
        ffmpeg_path, media, plan, input_path, on_progress, threads, segments, length
    ).run()


def estimate_total(
    sample: SampleEstimate,
    media: MediaInfo,
    audio_bytes: int | None,
    subtitle_bytes: int | None = None,
) -> TotalEstimate:
    """Scale the sample to the whole file, adding separately estimated tracks.

    ``total_bytes`` and ``ratio_vs_original`` stay ``None`` when the audio size is
    unknown, because a partial total would mislead; the ratio is the estimate
    divided by the original file size.
    """
    if not math.isfinite(media.duration) or media.duration <= 0:
        raise ValueError("media.duration must be positive and finite")
    if sample.sampled_seconds <= 0:
        raise ValueError("sampled_seconds must be positive")

    video_bytes = round(sample.video_bytes_per_second * media.duration)
    subtitles = subtitle_bytes or 0
    total_bytes = None if audio_bytes is None else video_bytes + audio_bytes + subtitles
    ratio = total_bytes / media.size if total_bytes is not None and media.size > 0 else None
    encode_seconds = sample.elapsed_seconds / sample.sampled_seconds * media.duration
    return TotalEstimate(
        video_bytes,
        audio_bytes,
        subtitles,
        total_bytes,
        ratio,
        encode_seconds,
    )


def audio_bytes_for_plan(media: MediaInfo, plan: EncodePlan) -> tuple[int | None, int | None]:
    """Estimate the audio bytes kept now and after applying *plan*.

    Both values are ``None`` when any kept track has no known bitrate, because a
    partial audio total would make the final estimate look smaller than it is.
    """
    streams = {stream.index: stream for stream in media.audio_streams}
    current_parts: list[int | None] = []
    final_parts: list[int | None] = []
    for decision in plan.audios:
        stream = streams.get(decision.stream_index)
        if stream is None:
            current_parts.append(None)
            final_parts.append(None)
            continue
        current = estimate_stream_bytes(stream.bitrate, media.duration)
        current_parts.append(current)
        final_parts.append(_decision_bytes(decision, current, media.duration))
    return _sum_or_none(current_parts), _sum_or_none(final_parts)


def estimate_levels(
    ffmpeg_path: str | Path,
    media: MediaInfo,
    input_path: Path,
    options: PlanOptions,
    ffmpeg_info: FFmpegInfo,
    qualities: tuple[str, ...] = ("high", "balanced", "max_savings"),
    on_progress: Callable[[float], None] | None = None,
    threads: int | None = None,
    segments: int = 1,
    length: float = 20.0,
) -> dict[str, TotalEstimate]:
    """Measure one short sample per quality level and return an estimate for each."""
    return SampleLevelsRunner(
        ffmpeg_path,
        media,
        input_path,
        options,
        ffmpeg_info,
        qualities,
        on_progress,
        threads,
        segments,
        length,
    ).run()


def _seconds(value: float) -> str:
    """Format a decimal number of seconds for FFmpeg without exponent notation."""
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _sampled_length(progress: ProgressEvent | None, fallback: float) -> float:
    """Return the encoded duration; the last chunk may end before its length.

    ``out_time_us`` of the final progress block reports what FFmpeg actually
    wrote, which avoids a second ffprobe run per chunk.
    """
    if progress is None or progress.tiempo_procesado_segundos <= 0:
        return fallback
    return progress.tiempo_procesado_segundos


def _decision_bytes(
    decision: AudioDecision, copied_bytes: int | None, duration: float
) -> int | None:
    if decision.action == "copy":
        return copied_bytes
    bitrate = parse_bitrate(decision.bitrate)
    return estimate_stream_bytes(bitrate, duration)


def _sum_or_none(parts: list[int | None]) -> int | None:
    total = 0
    for part in parts:
        if part is None:
            return None
        total += part
    return total
