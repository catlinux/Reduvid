# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Command-line interface for probing and converting media."""

from __future__ import annotations

import argparse
import sys
import threading
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from reduvid import __version__
from reduvid.core.config import Config, load_config
from reduvid.core.ffmpeg import FFmpegInfo, detect_ffmpeg
from reduvid.core.naming import build_output_path
from reduvid.core.pipeline import FileProcessor
from reduvid.core.plan import EncodePlan, PlanOptions, build_plan
from reduvid.core.probe import (
    MediaInfo,
    ProbeError,
    estimate_stream_bytes,
    format_duration,
    format_size,
    parse_bitrate,
    probe_media,
)
from reduvid.core.queue import ConversionQueue, QueueProgressEvent
from reduvid.core.report import FileReport, QueueReport
from reduvid.core.runner import EncodeError
from reduvid.core.sample import (
    SampleEstimate,
    SampleRunner,
    TotalEstimate,
    audio_bytes_for_plan,
    estimate_total,
)
from reduvid.i18n import _, setup_language
from reduvid.messages import error_text, warning_text


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(_("must be a positive integer")) from error
    if parsed < 1:
        raise argparse.ArgumentTypeError(_("must be a positive integer"))
    return parsed


def _language_set(value: str) -> frozenset[str]:
    languages = frozenset(code.strip().lower() for code in value.split(",") if code.strip())
    if not languages:
        raise argparse.ArgumentTypeError(_("must be a comma-separated list of language codes"))
    return languages


def _track_set(value: str) -> frozenset[int]:
    raw_tokens = [token.strip() for token in value.split(",")]
    if not raw_tokens or any(not token for token in raw_tokens):
        raise argparse.ArgumentTypeError(
            _("must be a comma-separated list of non-negative integers")
        )
    tracks: set[int] = set()
    for token in raw_tokens:
        try:
            track = int(token)
        except ValueError as error:
            raise argparse.ArgumentTypeError(
                _("must be a comma-separated list of non-negative integers")
            ) from error
        if track < 0:
            raise argparse.ArgumentTypeError(
                _("must be a comma-separated list of non-negative integers")
            )
        tracks.add(track)
    return frozenset(tracks)


def _load_config() -> Config:
    try:
        config, _invalid_keys = load_config()
    except (OSError, tomllib.TOMLDecodeError) as error:
        print(
            _("Warning: Could not read config file: {error}").format(error=error),
            file=sys.stderr,
        )
        return Config()
    return config


def _configured_ffmpeg_path(config: Config) -> Path | None:
    if config.ffmpeg_path is None:
        return None
    return config.ffmpeg_path.expanduser().resolve()


def _language_option(arguments: Sequence[str]) -> str | None:
    """Find ``--lang`` before argparse runs, so help texts use that language."""
    for index, argument in enumerate(arguments):
        if argument.startswith("--lang="):
            return argument.partition("=")[2]
        if argument == "--lang" and index + 1 < len(arguments):
            return arguments[index + 1]
    return None


def _resolve_inputs(
    raw_paths: Sequence[Path],
    *,
    allow_directories: bool,
    directory_message: str | None = None,
) -> list[Path] | None:
    paths: list[Path] = []
    valid = True
    for raw_path in raw_paths:
        try:
            path = raw_path.expanduser().resolve()
        except OSError as error:
            print(
                _("Error: Could not resolve input {path}: {error}").format(
                    path=raw_path, error=error
                ),
                file=sys.stderr,
            )
            valid = False
            continue
        if not path.exists():
            print(_("Error: Input does not exist: {path}").format(path=path), file=sys.stderr)
            valid = False
        elif path.is_file() or (allow_directories and path.is_dir()):
            paths.append(path)
        else:
            message = (
                directory_message
                if path.is_dir() and directory_message is not None
                else _("Error: Input is not a supported file or folder: {path}")
            )
            print(message.format(path=path), file=sys.stderr)
            valid = False
    return paths if valid else None


def _find_ffmpeg(config: Config) -> FFmpegInfo | None:
    try:
        info = detect_ffmpeg(_configured_ffmpeg_path(config))
    except OSError as error:
        print(_("Error: Could not inspect FFmpeg: {error}").format(error=error), file=sys.stderr)
        return None
    if info is None:
        print(_("Error: FFmpeg and ffprobe were not found."), file=sys.stderr)
    return info


def _action_text(action: str) -> str:
    texts = {
        "encode": _("encode"),
        "copy": _("copy"),
        "convert": _("convert"),
        "drop": _("drop"),
    }
    return texts.get(action, action)


def _show_media(media: MediaInfo) -> None:
    print(_("File: {path}").format(path=media.path))
    print(_("Format: {format}").format(format=media.format))
    print(_("Duration: {duration}").format(duration=format_duration(media.duration)))
    print(_("Size: {size:.2f} MB").format(size=media.size / 1_000_000))
    for position, video_stream in enumerate(media.video_streams, start=1):
        if video_stream.hdr:
            hdr = _("yes ({variant})").format(variant=video_stream.hdr_variant or _("unknown"))
        else:
            hdr = _("no")
        print(
            _(
                "Video {position}: {codec}, {width}x{height}, {fps:g} fps, {depth}-bit, HDR {hdr}"
            ).format(
                position=position,
                codec=video_stream.codec,
                width=video_stream.width,
                height=video_stream.height,
                fps=video_stream.fps,
                depth=video_stream.bit_depth,
                hdr=hdr,
            )
        )
    for position, audio_stream in enumerate(media.audio_streams, start=1):
        language = (
            _(", {language}").format(language=audio_stream.language)
            if audio_stream.language
            else ""
        )
        bytes_est = (
            estimate_stream_bytes(audio_stream.bitrate, media.duration)
            if media.duration > 0
            else None
        )
        if bytes_est is None:
            size_str = "—"
        else:
            size_str = _("~{size} estimated").format(size=format_size(bytes_est))
        print(
            _("Audio {position}: {codec}, {channels} channels{language}, {size}").format(
                position=position,
                codec=audio_stream.codec,
                channels=audio_stream.channels,
                language=language,
                size=size_str,
            )
        )
    for position, subtitle_stream in enumerate(media.subtitle_streams, start=1):
        language = (
            _(", {language}").format(language=subtitle_stream.language)
            if subtitle_stream.language
            else ""
        )
        image = _("yes") if subtitle_stream.is_image else _("no")
        print(
            _("Subtitle {position}: {codec}{language}, image: {image}").format(
                position=position,
                codec=subtitle_stream.codec,
                language=language,
                image=image,
            )
        )


def _show_plan(plan: EncodePlan, media: MediaInfo | None = None) -> None:
    print(
        _("Plan: {destination}, {quality}, {container}").format(
            destination=plan.destination, quality=plan.quality, container=plan.container
        )
    )
    for video_decision in plan.videos:
        details = _("{codec}, CRF {crf}, {preset} preset").format(
            codec=video_decision.codec,
            crf=video_decision.crf,
            preset=video_decision.preset,
        )
        if video_decision.target_height is not None:
            details += _(", scale to {height}p").format(height=video_decision.target_height)
        print(
            "  "
            + _("Video stream {index}: {action}, {details}").format(
                index=video_decision.stream_index,
                action=_action_text(video_decision.action),
                details=details,
            )
        )
    audio_by_index = {stream.index: stream for stream in media.audio_streams} if media else {}
    for audio_decision in plan.audios:
        details = _action_text(audio_decision.action)
        if audio_decision.codec is not None:
            details += _(" as {codec}").format(codec=audio_decision.codec)
        if audio_decision.bitrate is not None:
            details += _(" at {bitrate}").format(bitrate=audio_decision.bitrate)
        if media is not None:
            stream = audio_by_index.get(audio_decision.stream_index)
            bitrate: int | None = None
            if audio_decision.bitrate is not None:
                bitrate = parse_bitrate(audio_decision.bitrate)
            elif stream is not None:
                bitrate = stream.bitrate
            bytes_est = (
                estimate_stream_bytes(bitrate, media.duration) if media.duration > 0 else None
            )
            if bytes_est is not None:
                size_str = _("~{size} estimated").format(size=format_size(bytes_est))
                details += f", {size_str}"
            else:
                details += ", —"
        print(
            "  "
            + _("Audio stream {index}: {details}").format(
                index=audio_decision.stream_index, details=details
            )
        )
    for subtitle_decision in plan.subtitles:
        details = _action_text(subtitle_decision.action)
        if subtitle_decision.codec is not None:
            details += _(" as {codec}").format(codec=subtitle_decision.codec)
        print(
            "  "
            + _("Subtitle stream {index}: {details}").format(
                index=subtitle_decision.stream_index, details=details
            )
        )
    for warning in plan.warnings:
        print("  " + _("Warning: {text}").format(text=warning_text(warning)))


def _show_probe(paths: list[Path], ffmpeg_info: FFmpegInfo) -> int:
    failed = False
    for path in paths:
        try:
            media = probe_media(ffmpeg_info.ffprobe_path, path)
        except ProbeError as error:
            print(
                _("Error: Could not probe {path}: {error}").format(path=path, error=error),
                file=sys.stderr,
            )
            failed = True
            continue
        _show_media(media)
    return 2 if failed else 0


def _show_file_start(path: Path, index: int, total: int) -> None:
    print(_("Converting [{index}/{total}]: {path}").format(index=index, total=total, path=path))


def _show_progress(event: QueueProgressEvent) -> None:
    progress = event.file_progress
    if progress is not None:
        percent = event.fraction_completed * 100
        print(
            "  "
            + _("Progress: {percent:.0f}% ({state})").format(percent=percent, state=progress.estado)
        )


def _show_file_complete(report: FileReport) -> None:
    print("  " + _("Finished: {name}").format(name=report.path.name))


def _show_file_failed(report: FileReport) -> None:
    details = report.reason or (error_text(report.error_code) if report.error_code else "")
    suffix = f": {details}" if details else ""
    print(_("Error: {path}{details}").format(path=report.path, details=suffix), file=sys.stderr)


def _show_queue_report(report: QueueReport) -> None:
    print(
        _("Files: {succeeded} succeeded, {failed} failed, {skipped} skipped").format(
            succeeded=report.succeeded, failed=report.failed, skipped=report.skipped
        )
    )
    savings_mb = report.savings_bytes / 1_000_000
    print(
        _("Total savings: {savings:.2f} MB ({percent:.1f}%)").format(
            savings=savings_mb, percent=report.savings_percent
        )
    )


def _dry_run(
    queue: ConversionQueue,
    ffmpeg_info: FFmpegInfo,
    options: PlanOptions,
    output_dir: Path | None,
) -> None:
    print(_("Dry run: {count} file(s)").format(count=len(queue.files)))
    for path in queue.files:
        try:
            media = probe_media(ffmpeg_info.ffprobe_path, path)
        except ProbeError as error:
            print(
                _("Error: Could not probe {path}: {error}").format(path=path, error=error),
                file=sys.stderr,
            )
            continue
        plan = build_plan(media, ffmpeg_info, options)
        destination_dir = output_dir or media.path.parent
        output_path = build_output_path(media.path, destination_dir, options.container)
        print(_("Would convert: {path}").format(path=path))
        print(_("Output: {path}").format(path=output_path))
        _show_plan(plan, media)


def _convert(
    paths: list[Path],
    ffmpeg_info: FFmpegInfo,
    options: PlanOptions,
    *,
    recursive: bool,
    output_dir: Path | None,
    threads: int | None,
    replace_original: bool,
    dry_run: bool,
    hw_decode: bool,
) -> int:
    processor = FileProcessor(
        ffmpeg_info,
        options,
        output_dir=output_dir,
        threads=threads,
        replace_original=replace_original,
        hw_decode=hw_decode,
    )

    def show_file_complete(report: FileReport) -> None:
        output_path = processor.last_output_path
        if output_path is not None:
            print(_("Output: {path}").format(path=output_path))
        _show_file_complete(report)

    queue = ConversionQueue(
        processor,
        ffprobe_path=ffmpeg_info.ffprobe_path,
        on_progress=_show_progress,
        on_file_start=_show_file_start,
        on_file_complete=show_file_complete,
        on_file_failed=_show_file_failed,
        probe=probe_media,
    )
    for path in paths:
        if path.is_dir():
            queue.add_folder(path, recursive=recursive)
        else:
            queue.add_files([path])

    if dry_run:
        _dry_run(queue, ffmpeg_info, options, output_dir)
        print(_("Dry run complete."))
        return 0

    report = queue.run()
    _show_queue_report(report)
    return 2 if report.failed else 0


class _TextProgress:
    """Rewrite one progress line, but only when stdout is a terminal."""

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream
        self._interactive = stream.isatty()
        self._last_percent: int | None = None

    def __call__(self, fraction: float) -> None:
        if not self._interactive:
            return
        percent = min(max(round(fraction * 100), 0), 100)
        if percent == self._last_percent:
            return
        self._last_percent = percent
        print(
            "\r" + _("Estimating: {percent}%").format(percent=percent),
            end="",
            file=self._stream,
            flush=True,
        )

    def finish(self) -> None:
        if self._interactive and self._last_percent is not None:
            print(file=self._stream)


def _wait_for_sample(done: threading.Event) -> None:
    """Block until the sampling thread ends; Ctrl+C interrupts this wait."""
    done.wait()


def _run_interruptible_sample(runner: SampleRunner) -> SampleEstimate:
    """Run *runner* in a worker thread so Ctrl+C can cancel it and clean up.

    Cancelling from the main thread lets ``SampleRunner`` terminate FFmpeg and
    remove its temporaries before the interpreter unwinds.
    """
    results: list[SampleEstimate] = []
    errors: list[Exception] = []
    done = threading.Event()

    def run() -> None:
        try:
            results.append(runner.run())
        except Exception as error:
            errors.append(error)
        finally:
            done.set()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        _wait_for_sample(done)
    except KeyboardInterrupt:
        runner.cancel()
        thread.join()
        raise
    if errors:
        raise errors[0]
    return results[0]


def _show_estimate(media: MediaInfo, sample: SampleEstimate, total: TotalEstimate) -> None:
    print(
        _("Estimate from a {seconds}-second sample; sizes and time are approximate.").format(
            seconds=f"{sample.sampled_seconds:.0f}"
        )
    )
    print("  " + _("Video: ~{size}").format(size=format_size(total.video_bytes)))
    if total.audio_bytes is None:
        print("  " + _("Audio: unknown (the file does not report its bitrate)"))
        print(
            "  "
            + _(
                "Estimated size: cannot be calculated without the audio size; video only: ~{size}"
            ).format(size=format_size(total.video_bytes))
        )
    else:
        print("  " + _("Audio: ~{size}").format(size=format_size(total.audio_bytes)))
        total_bytes = total.total_bytes if total.total_bytes is not None else 0
        print("  " + _("Estimated size: ~{size}").format(size=format_size(total_bytes)))
    print("  " + _("Original size: {size}").format(size=format_size(media.size)))
    ratio = total.ratio_vs_original
    if ratio is not None and total.total_bytes is not None:
        if total.total_bytes <= media.size:
            print(
                "  "
                + _("Savings: {percent}% ({size} smaller)").format(
                    percent=f"{(1 - ratio) * 100:.0f}",
                    size=format_size(media.size - total.total_bytes),
                )
            )
        else:
            print(
                "  "
                + _("Increase: {percent}% ({size} larger)").format(
                    percent=f"{(ratio - 1) * 100:.0f}",
                    size=format_size(total.total_bytes - media.size),
                )
            )
    print(
        "  "
        + _("Approximate conversion time: {duration}").format(
            duration=format_duration(total.encode_seconds)
        )
    )


def _estimate(
    paths: list[Path],
    ffmpeg_info: FFmpegInfo,
    options: PlanOptions,
    *,
    threads: int | None,
    hw_decode: bool,
) -> int:
    failed = False
    for index, path in enumerate(paths, start=1):
        if index > 1:
            print()
        print(
            _("Estimating [{index}/{total}]: {path}").format(
                index=index, total=len(paths), path=path
            )
        )
        try:
            media = probe_media(ffmpeg_info.ffprobe_path, path)
        except ProbeError as error:
            print(
                _("Error: Could not probe {path}: {error}").format(path=path, error=error),
                file=sys.stderr,
            )
            failed = True
            continue
        plan = build_plan(media, ffmpeg_info, options)
        if not plan.videos:
            print(
                _("Error: {path} has no video streams to estimate.").format(path=path),
                file=sys.stderr,
            )
            failed = True
            continue
        progress = _TextProgress(sys.stdout)
        runner = SampleRunner(
            ffmpeg_info.ffmpeg_path,
            media,
            plan,
            path,
            on_progress=progress,
            threads=threads,
            hw_decode=hw_decode,
        )
        try:
            sample = _run_interruptible_sample(runner)
        except EncodeError as error:
            print(
                _("Error: Could not estimate {path}: {error}").format(
                    path=path, error=error_text(error.code)
                ),
                file=sys.stderr,
            )
            failed = True
            continue
        except ValueError as error:
            print(
                _("Error: Could not estimate {path}: {error}").format(path=path, error=error),
                file=sys.stderr,
            )
            failed = True
            continue
        finally:
            progress.finish()
        final_audio = audio_bytes_for_plan(media, plan)[1]
        total = estimate_total(sample, media, audio_bytes=final_audio)
        _show_estimate(media, sample, total)
    return 2 if failed else 0


def _add_plan_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the encoding options shared by ``convert`` and ``estimate``."""
    parser.add_argument("--target", choices=("jellyfin", "modern", "archive"), default="jellyfin")
    parser.add_argument(
        "--quality", choices=("high", "balanced", "max_savings"), default="balanced"
    )
    parser.add_argument("--container", choices=("mkv", "mp4"), default="mkv")
    parser.add_argument(
        "--keep-audio",
        type=_language_set,
        metavar="LANGS",
        help=_("Keep only these audio languages (comma-separated, 'und' for no language)"),
    )
    parser.add_argument(
        "--audio-tracks",
        type=_track_set,
        metavar="TRACKS",
        help=_("Keep only these audio track indices (comma-separated, overrides --keep-audio)"),
    )
    parser.add_argument(
        "--one-audio-per-language",
        action="store_true",
        help=_("Keep only the highest-quality audio track for each language"),
    )
    parser.add_argument(
        "--reduce-audio",
        action="store_true",
        help=_("Re-encode audio tracks to AAC to save space"),
    )
    parser.add_argument(
        "--keep-subs",
        type=_language_set,
        metavar="LANGS",
        help=_("Keep only these subtitle languages (comma-separated, 'und' for no language)"),
    )
    parser.add_argument("--max-height", type=_positive_int)
    parser.add_argument("--threads", type=_positive_int)
    parser.add_argument(
        "--no-hw-decode",
        action="store_true",
        help=_("Do not use the graphics card to read the videos"),
    )


def _plan_options(parsed: argparse.Namespace) -> PlanOptions:
    return PlanOptions(
        destination=parsed.target,
        quality=parsed.quality,
        container=parsed.container,
        max_height=parsed.max_height,
        audio_languages=parsed.keep_audio,
        subtitle_languages=parsed.keep_subs,
        audio_tracks=parsed.audio_tracks,
        one_audio_per_language=parsed.one_audio_per_language,
        reduce_audio=parsed.reduce_audio,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Return 0 on success, 1 if FFmpeg is unavailable, or 2 on file errors."""
    arguments = list(argv) if argv is not None else sys.argv[1:]
    config = _load_config()
    setup_language(_language_option(arguments) or config.language)

    parser = argparse.ArgumentParser(prog="reduvid-cli")
    parser.add_argument("--version", action="version", version=f"reduvid {__version__}")
    parser.add_argument(
        "--lang",
        choices=("ca", "es", "en"),
        help=_("Language for messages"),
    )
    subparsers = parser.add_subparsers(dest="command")
    probe_parser = subparsers.add_parser("probe", help=_("Show media details"))
    probe_parser.add_argument("files", nargs="+", type=Path)
    convert_parser = subparsers.add_parser("convert", help=_("Convert media files"))
    convert_parser.add_argument("paths", nargs="+", type=Path)
    _add_plan_arguments(convert_parser)
    convert_parser.add_argument("--output-dir", type=Path)
    convert_parser.add_argument("--recursive", action="store_true")
    convert_parser.add_argument("--replace-original", action="store_true")
    convert_parser.add_argument("--dry-run", action="store_true")
    estimate_parser = subparsers.add_parser(
        "estimate", help=_("Estimate the final size and time from a short sample")
    )
    estimate_parser.add_argument("files", nargs="+", type=Path)
    _add_plan_arguments(estimate_parser)

    if not arguments:
        parser.print_help()
        return 0
    parsed = parser.parse_args(arguments)
    if parsed.command is None:
        parser.print_help()
        return 0

    is_probe = parsed.command == "probe"
    is_convert = parsed.command == "convert"
    raw_paths = parsed.files if parsed.command in ("probe", "estimate") else parsed.paths
    paths = _resolve_inputs(
        raw_paths,
        allow_directories=is_convert,
        directory_message=(
            _("Error: Input is a folder; estimate works on files only: {path}")
            if parsed.command == "estimate"
            else None
        ),
    )
    if paths is None:
        return 2
    if is_probe and any(not path.is_file() for path in paths):
        for path in paths:
            if not path.is_file():
                print(
                    _("Error: Probe input is not a file: {path}").format(path=path),
                    file=sys.stderr,
                )
        return 2

    output_dir = (
        parsed.output_dir.expanduser().resolve() if is_convert and parsed.output_dir else None
    )
    if output_dir is not None and output_dir.exists() and not output_dir.is_dir():
        print(
            _("Error: Output path is not a folder: {path}").format(path=output_dir),
            file=sys.stderr,
        )
        return 2

    ffmpeg_info = _find_ffmpeg(config)
    if ffmpeg_info is None:
        return 1
    if is_probe:
        return _show_probe(paths, ffmpeg_info)

    options = _plan_options(parsed)
    hw_decode = False if parsed.no_hw_decode else config.hw_decode
    if not is_convert:
        try:
            return _estimate(
                paths,
                ffmpeg_info,
                options,
                threads=parsed.threads,
                hw_decode=hw_decode,
            )
        except KeyboardInterrupt:
            print(_("Estimate cancelled."), file=sys.stderr)
            return 130

    return _convert(
        paths,
        ffmpeg_info,
        options,
        recursive=parsed.recursive,
        output_dir=output_dir,
        threads=parsed.threads,
        replace_original=parsed.replace_original,
        dry_run=parsed.dry_run,
        hw_decode=hw_decode,
    )
