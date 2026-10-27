# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from pathlib import Path

import pytest

from reduvid.core.command import build_command
from reduvid.core.plan import AudioDecision, EncodePlan, SubtitleDecision, VideoDecision
from reduvid.core.probe import AttachmentStream, MediaInfo


def _media(attachments: list[AttachmentStream] | None = None) -> MediaInfo:
    return MediaInfo(Path("/input.mkv"), "matroska", 10, 100, [], [], [], [], attachments or [])


def _plan(
    *,
    videos: tuple[VideoDecision, ...] = (),
    audios: tuple[AudioDecision, ...] = (),
    subtitles: tuple[SubtitleDecision, ...] = (),
    container: str = "mkv",
) -> EncodePlan:
    return EncodePlan("jellyfin", "balanced", container, videos, audios, subtitles, ())


def _video(*, filters: tuple[str, ...] = (), target_height: int | None = None) -> VideoDecision:
    return VideoDecision(
        0, "encode", "libx264", 23, "medium", "high", "4.1", "yuv420p", filters, target_height
    )


def test_builds_video_encode_arguments() -> None:
    arguments = build_command(
        _media(), _plan(videos=(_video(),)), Path.cwd() / "in.mkv", Path.cwd() / "out.mkv"
    )

    assert arguments[arguments.index("-map") + 1] == "0:0"
    assert arguments[arguments.index("-c:v:0") + 1] == "libx264"
    assert arguments[arguments.index("-crf:v:0") + 1] == "23"
    assert arguments[arguments.index("-preset:v:0") + 1] == "medium"


def test_builds_video_filter_argument_as_one_item() -> None:
    arguments = build_command(
        _media(),
        _plan(videos=(_video(filters=("zscale", "tonemap")),)),
        Path.cwd() / "in.mkv",
        Path.cwd() / "out.mkv",
    )

    assert arguments[arguments.index("-filter:v:0") + 1] == "zscale,tonemap"


def test_builds_video_scale_filter_for_target_height() -> None:
    arguments = build_command(
        _media(),
        _plan(videos=(_video(target_height=720),)),
        Path.cwd() / "in.mkv",
        Path.cwd() / "out.mkv",
    )

    assert arguments[arguments.index("-filter:v:0") + 1] == "scale=-2:720"


def test_builds_audio_copy_and_encode_in_order() -> None:
    plan = _plan(audios=(AudioDecision(1, "copy"), AudioDecision(2, "encode", "aac", "192k")))
    arguments = build_command(_media(), plan, Path.cwd() / "in.mkv", Path.cwd() / "out.mkv")

    assert arguments[arguments.index("-c:a:0") + 1] == "copy"
    assert arguments[arguments.index("-c:a:1") + 1] == "aac"
    assert arguments[arguments.index("-b:a:1") + 1] == "192k"


def test_maps_attachments_for_mkv() -> None:
    media = _media([AttachmentStream(2, "cover.jpg", "image/jpeg")])
    arguments = build_command(media, _plan(), Path.cwd() / "in.mkv", Path.cwd() / "out.mkv")

    assert arguments[arguments.index("-map") : arguments.index("-map") + 4] == [
        "-map",
        "0:2",
        "-c:t",
        "copy",
    ]


def test_does_not_map_attachments_for_mp4() -> None:
    media = _media([AttachmentStream(2, "cover.jpg", "image/jpeg")])
    arguments = build_command(
        media, _plan(container="mp4"), Path.cwd() / "in.mkv", Path.cwd() / "out.mp4"
    )

    assert "0:2" not in arguments
    assert "-c:t" not in arguments


def test_dropped_subtitle_is_not_mapped_and_metadata_is_kept() -> None:
    plan = _plan(subtitles=(SubtitleDecision(3, "drop"), SubtitleDecision(4, "copy")))
    arguments = build_command(_media(), plan, Path.cwd() / "in.mkv", Path.cwd() / "out.mkv")

    assert "0:3" not in arguments
    assert arguments[arguments.index("-map") + 1] == "0:4"
    assert "-map_metadata" in arguments and arguments[arguments.index("-map_metadata") + 1] == "0"
    assert "-map_chapters" in arguments and arguments[arguments.index("-map_chapters") + 1] == "0"


def test_hw_decode_inserts_hwaccel_auto_immediately_before_input() -> None:
    input_path = Path.cwd() / "in.mkv"

    arguments = build_command(
        _media(), _plan(videos=(_video(),)), input_path, Path.cwd() / "out.mkv", hw_decode=True
    )

    input_index = arguments.index("-i")
    assert arguments[input_index - 2 : input_index + 2] == [
        "-hwaccel",
        "auto",
        "-i",
        str(input_path),
    ]


def test_hw_decode_is_absent_by_default() -> None:
    arguments = build_command(
        _media(), _plan(videos=(_video(),)), Path.cwd() / "in.mkv", Path.cwd() / "out.mkv"
    )

    assert "-hwaccel" not in arguments


def test_paths_are_independent_argument_items() -> None:
    input_path = Path.cwd() / "vídeo áéñ 😀" / "-raro.mkv"
    output_path = Path.cwd() / "salida con espacios" / "ñ 😀.mkv"
    arguments = build_command(_media(), _plan(), input_path, output_path)

    assert arguments[arguments.index("-i") + 1] == str(input_path)
    assert arguments[-1] == str(output_path)
    assert "-raro.mkv" not in arguments


@pytest.mark.parametrize("input_path", [Path("relative.mkv")])
def test_relative_input_path_is_rejected(input_path: Path) -> None:
    with pytest.raises(ValueError, match="input_path must be absolute"):
        build_command(_media(), _plan(), input_path, Path.cwd() / "out.mkv")


def test_relative_output_path_is_rejected() -> None:
    with pytest.raises(ValueError, match="output_path must be absolute"):
        build_command(_media(), _plan(), Path.cwd() / "in.mkv", Path("relative.mkv"))
