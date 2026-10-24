# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Command-line interface for probing and converting media."""

from __future__ import annotations

import argparse
import math
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path

from reduvid import __version__
from reduvid.core.config import load_config
from reduvid.core.ffmpeg import FFmpegInfo, detect_ffmpeg
from reduvid.core.naming import build_output_path
from reduvid.core.pipeline import FileProcessor
from reduvid.core.plan import EncodePlan, PlanOptions, build_plan
from reduvid.core.probe import MediaInfo, ProbeError, probe_media
from reduvid.core.queue import ConversionQueue, QueueProgressEvent
from reduvid.core.report import FileReport, QueueReport


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive integer") from error
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _configured_ffmpeg_path() -> Path | None:
    try:
        config, _invalid_keys = load_config()
    except (OSError, tomllib.TOMLDecodeError) as error:
        print(f"Warning: Could not read config file: {error}", file=sys.stderr)
        return None
    if config.ffmpeg_path is None:
        return None
    return config.ffmpeg_path.expanduser().resolve()


def _resolve_inputs(raw_paths: Sequence[Path], *, allow_directories: bool) -> list[Path] | None:
    paths: list[Path] = []
    valid = True
    for raw_path in raw_paths:
        try:
            path = raw_path.expanduser().resolve()
        except OSError as error:
            print(f"Error: Could not resolve input {raw_path}: {error}", file=sys.stderr)
            valid = False
            continue
        if not path.exists():
            print(f"Error: Input does not exist: {path}", file=sys.stderr)
            valid = False
        elif path.is_file() or (allow_directories and path.is_dir()):
            paths.append(path)
        else:
            print(f"Error: Input is not a supported file or folder: {path}", file=sys.stderr)
            valid = False
    return paths if valid else None


def _find_ffmpeg() -> FFmpegInfo | None:
    try:
        info = detect_ffmpeg(_configured_ffmpeg_path())
    except OSError as error:
        print(f"Error: Could not inspect FFmpeg: {error}", file=sys.stderr)
        return None
    if info is None:
        print("Error: FFmpeg and ffprobe were not found.", file=sys.stderr)
    return info


def _format_duration(duration: float) -> str:
    seconds = int(duration) if math.isfinite(duration) and duration > 0 else 0
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02}:{seconds:02}"
    return f"{minutes}:{seconds:02}"


def _show_media(media: MediaInfo) -> None:
    print(f"File: {media.path}")
    print(f"Format: {media.format}")
    print(f"Duration: {_format_duration(media.duration)}")
    print(f"Size: {media.size / 1_000_000:.2f} MB")
    for position, video_stream in enumerate(media.video_streams, start=1):
        hdr = f"yes ({video_stream.hdr_variant or 'unknown'})" if video_stream.hdr else "no"
        print(
            f"Video {position}: {video_stream.codec}, "
            f"{video_stream.width}x{video_stream.height}, "
            f"{video_stream.fps:g} fps, {video_stream.bit_depth}-bit, HDR {hdr}"
        )
    for position, audio_stream in enumerate(media.audio_streams, start=1):
        language = f", {audio_stream.language}" if audio_stream.language else ""
        print(f"Audio {position}: {audio_stream.codec}, {audio_stream.channels} channels{language}")
    for position, subtitle_stream in enumerate(media.subtitle_streams, start=1):
        language = f", {subtitle_stream.language}" if subtitle_stream.language else ""
        image = "yes" if subtitle_stream.is_image else "no"
        print(f"Subtitle {position}: {subtitle_stream.codec}{language}, image: {image}")


def _show_plan(plan: EncodePlan) -> None:
    print(f"Plan: {plan.destination}, {plan.quality}, {plan.container}")
    for video_decision in plan.videos:
        details = (
            f"{video_decision.codec}, CRF {video_decision.crf}, {video_decision.preset} preset"
        )
        if video_decision.target_height is not None:
            details += f", scale to {video_decision.target_height}p"
        print(f"  Video stream {video_decision.stream_index}: {video_decision.action}, {details}")
    for audio_decision in plan.audios:
        details = audio_decision.action
        if audio_decision.codec is not None:
            details += f" as {audio_decision.codec}"
        if audio_decision.bitrate is not None:
            details += f" at {audio_decision.bitrate}"
        print(f"  Audio stream {audio_decision.stream_index}: {details}")
    for subtitle_decision in plan.subtitles:
        details = subtitle_decision.action
        if subtitle_decision.codec is not None:
            details += f" as {subtitle_decision.codec}"
        print(f"  Subtitle stream {subtitle_decision.stream_index}: {details}")
    for warning in plan.warnings:
        print(f"  Warning: {warning.code} {warning.params}")


def _show_probe(paths: list[Path], ffmpeg_info: FFmpegInfo) -> int:
    failed = False
    for path in paths:
        try:
            media = probe_media(ffmpeg_info.ffprobe_path, path)
        except ProbeError as error:
            print(f"Error: Could not probe {path}: {error}", file=sys.stderr)
            failed = True
            continue
        _show_media(media)
    return 2 if failed else 0


def _show_file_start(path: Path, index: int, total: int) -> None:
    print(f"Converting [{index}/{total}]: {path}")


def _show_progress(event: QueueProgressEvent) -> None:
    progress = event.file_progress
    if progress is not None:
        percent = event.fraction_completed * 100
        print(f"  Progress: {percent:.0f}% ({progress.estado})")


def _show_file_complete(report: FileReport) -> None:
    print(f"  Finished: {report.path.name}")


def _show_file_failed(report: FileReport) -> None:
    reason = f": {report.reason}" if report.reason else ""
    print(f"Error: {report.path}{reason}", file=sys.stderr)


def _show_queue_report(report: QueueReport) -> None:
    print(f"Files: {report.succeeded} succeeded, {report.failed} failed, {report.skipped} skipped")
    savings_mb = report.savings_bytes / 1_000_000
    print(f"Total savings: {savings_mb:.2f} MB ({report.savings_percent:.1f}%)")


def _dry_run(
    queue: ConversionQueue,
    ffmpeg_info: FFmpegInfo,
    options: PlanOptions,
    output_dir: Path | None,
) -> None:
    print(f"Dry run: {len(queue.files)} file(s)")
    for path in queue.files:
        try:
            media = probe_media(ffmpeg_info.ffprobe_path, path)
        except ProbeError as error:
            print(f"Error: Could not probe {path}: {error}", file=sys.stderr)
            continue
        plan = build_plan(media, ffmpeg_info, options)
        destination_dir = output_dir or media.path.parent
        output_path = build_output_path(media.path, destination_dir, options.container)
        print(f"Would convert: {path}")
        print(f"Output: {output_path}")
        _show_plan(plan)


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
) -> int:
    processor = FileProcessor(
        ffmpeg_info,
        options,
        output_dir=output_dir,
        threads=threads,
        replace_original=replace_original,
    )

    def show_file_complete(report: FileReport) -> None:
        output_path = processor.last_output_path
        if output_path is not None:
            print(f"Output: {output_path}")
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
        print("Dry run complete.")
        return 0

    report = queue.run()
    _show_queue_report(report)
    return 2 if report.failed else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Return 0 on success, 1 if FFmpeg is unavailable, or 2 on file errors."""
    parser = argparse.ArgumentParser(prog="reduvid")
    parser.add_argument("--version", action="version", version=f"reduvid {__version__}")
    subparsers = parser.add_subparsers(dest="command")
    probe_parser = subparsers.add_parser("probe", help="Show media details")
    probe_parser.add_argument("files", nargs="+", type=Path)
    convert_parser = subparsers.add_parser("convert", help="Convert media files")
    convert_parser.add_argument("paths", nargs="+", type=Path)
    convert_parser.add_argument(
        "--target", choices=("jellyfin", "modern", "archive"), default="jellyfin"
    )
    convert_parser.add_argument(
        "--quality", choices=("high", "balanced", "max_savings"), default="balanced"
    )
    convert_parser.add_argument("--container", choices=("mkv", "mp4"), default="mkv")
    convert_parser.add_argument("--max-height", type=_positive_int)
    convert_parser.add_argument("--output-dir", type=Path)
    convert_parser.add_argument("--recursive", action="store_true")
    convert_parser.add_argument("--threads", type=_positive_int)
    convert_parser.add_argument("--replace-original", action="store_true")
    convert_parser.add_argument("--dry-run", action="store_true")

    arguments = list(argv) if argv is not None else sys.argv[1:]
    if not arguments:
        parser.print_help()
        return 0
    parsed = parser.parse_args(arguments)
    if parsed.command is None:
        parser.print_help()
        return 0

    is_convert = parsed.command == "convert"
    paths = _resolve_inputs(
        parsed.paths if is_convert else parsed.files, allow_directories=is_convert
    )
    if paths is None:
        return 2
    if not is_convert and any(not path.is_file() for path in paths):
        for path in paths:
            if not path.is_file():
                print(f"Error: Probe input is not a file: {path}", file=sys.stderr)
        return 2

    output_dir = (
        parsed.output_dir.expanduser().resolve() if is_convert and parsed.output_dir else None
    )
    if output_dir is not None and output_dir.exists() and not output_dir.is_dir():
        print(f"Error: Output path is not a folder: {output_dir}", file=sys.stderr)
        return 2

    ffmpeg_info = _find_ffmpeg()
    if ffmpeg_info is None:
        return 1
    if not is_convert:
        return _show_probe(paths, ffmpeg_info)

    options = PlanOptions(parsed.target, parsed.quality, parsed.container, parsed.max_height)
    return _convert(
        paths,
        ffmpeg_info,
        options,
        recursive=parsed.recursive,
        output_dir=output_dir,
        threads=parsed.threads,
        replace_original=parsed.replace_original,
        dry_run=parsed.dry_run,
    )
