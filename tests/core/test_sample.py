# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from pathlib import Path

import pytest

from reduvid.core.command import build_command
from reduvid.core.plan import AudioDecision, EncodePlan, SubtitleDecision, VideoDecision
from reduvid.core.probe import AttachmentStream, MediaInfo
from reduvid.core.sample import build_sample_command, extract_frame_command, sample_window


def media(attachments: list[AttachmentStream] | None = None) -> MediaInfo:
    return MediaInfo(Path("/input.mkv"), "matroska", 120, 100, [], [], [], [], attachments or [])


def plan() -> EncodePlan:
    video = VideoDecision(0, "encode", "libx264", 22, "medium", "high", "4.1", "yuv420p", (), None)
    return EncodePlan(
        "jellyfin",
        "balanced",
        "mkv",
        (video,),
        (AudioDecision(1, "copy"),),
        (SubtitleDecision(2, "copy"),),
        (),
    )


def test_sample_command_seeks_before_input_and_limits_after_it() -> None:
    input_path = Path.cwd() / "vídeo con espacios ñ 😀" / "entrada.mkv"
    output_path = Path.cwd() / "salida temporal" / "muestra.mkv"

    arguments = build_sample_command(media(), plan(), input_path, output_path, 48.0, 30.0)

    input_index = arguments.index("-i")
    assert arguments[input_index - 2] == "-ss"
    assert arguments[input_index - 1] == "48"
    assert arguments[input_index + 1] == str(input_path)
    assert arguments[input_index + 2] == "-t"
    assert arguments[input_index + 3] == "30"
    assert arguments[-1] == str(output_path)


def test_sample_command_reuses_the_encoding_arguments() -> None:
    input_path = Path.cwd() / "entrada.mkv"
    output_path = Path.cwd() / "muestra.mkv"
    base = build_command(media(), plan(), input_path, output_path)

    arguments = build_sample_command(media(), plan(), input_path, output_path, 12.5, 30.0)

    stripped = list(arguments)
    seek_index = stripped.index("-ss")
    del stripped[seek_index : seek_index + 2]
    limit_index = stripped.index("-t")
    del stripped[limit_index : limit_index + 2]
    assert stripped == base


def test_sample_command_keeps_fractional_seconds() -> None:
    arguments = build_sample_command(
        media(), plan(), Path.cwd() / "in.mkv", Path.cwd() / "out.mkv", 29.6, 29.5
    )

    assert arguments[arguments.index("-ss") + 1] == "29.6"
    assert arguments[arguments.index("-t") + 1] == "29.5"


@pytest.mark.parametrize(
    ("total", "duration", "expected"),
    [
        (120.0, 30.0, (48.0, 30.0)),
        (75.0, 30.0, (30.0, 30.0)),
        (74.0, 30.0, (29.6, 30.0)),
        (60.0, 30.0, (24.0, 30.0)),
        (40.0, 30.0, (16.0, 24.0)),
        (20.0, 30.0, (0.0, 20.0)),
        (30.0, 30.0, (12.0, 18.0)),
        (0.0, 30.0, (0.0, 0.0)),
        (-5.0, 30.0, (0.0, 0.0)),
        (100.0, 0.0, (0.0, 0.0)),
    ],
)
def test_sample_window_stays_inside_the_video(
    total: float, duration: float, expected: tuple[float, float]
) -> None:
    start, length = sample_window(total, duration)

    assert start == pytest.approx(expected[0])
    assert length == pytest.approx(expected[1])
    assert start >= 0
    assert length >= 0
    assert start + length <= max(total, 0)


def test_extract_frame_command_is_a_minimal_png_command() -> None:
    input_path = Path.cwd() / "vídeo ñ 😀" / "entrada.mkv"
    output_path = Path.cwd() / "temporal" / "fotograma.png"

    arguments = extract_frame_command(input_path, 12.5, output_path)

    assert arguments.index("-ss") < arguments.index("-i")
    assert arguments[arguments.index("-ss") + 1] == "12.5"
    assert arguments[arguments.index("-i") + 1] == str(input_path)
    assert arguments[arguments.index("-frames:v") + 1] == "1"
    assert "-an" in arguments
    assert "-t" not in arguments
    assert arguments[-1] == str(output_path)


def test_sample_and_frame_commands_reject_relative_paths() -> None:
    with pytest.raises(ValueError, match="input_path must be absolute"):
        build_sample_command(media(), plan(), Path("relative.mkv"), Path.cwd() / "out.mkv", 0, 30)
    with pytest.raises(ValueError, match="output_path must be absolute"):
        build_sample_command(media(), plan(), Path.cwd() / "in.mkv", Path("relative.mkv"), 0, 30)
    with pytest.raises(ValueError, match="input_path must be absolute"):
        extract_frame_command(Path("relative.mkv"), 0, Path.cwd() / "frame.png")
    with pytest.raises(ValueError, match="output_path must be absolute"):
        extract_frame_command(Path.cwd() / "in.mkv", 0, Path("frame.png"))
