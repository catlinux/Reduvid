# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

import json
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from reduvid.core import probe

DATA = Path(__file__).parent / "data"


def _mock_probe(monkeypatch: pytest.MonkeyPatch, fixture: str) -> None:
    output = (DATA / fixture).read_text(encoding="utf-8")

    def run(args: list[str], **kwargs: object) -> CompletedProcess[str]:
        return CompletedProcess(args, 0, stdout=output, stderr="")

    monkeypatch.setattr(probe.subprocess, "run", run)


def test_parses_streams_format_and_chapters(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_probe(monkeypatch, "simple.json")
    info = probe.probe_media(Path("C:/bin/ffprobe"), Path("C:/movie.mkv"))

    assert info.format == "matroska,webm"
    assert info.duration == 120.5 and info.size == 9000
    assert info.video_streams[0].codec == "h264"
    assert info.video_streams[0].fps == pytest.approx(24000 / 1001)
    assert info.video_streams[0].is_default
    assert info.audio_streams[0].language == "eng"
    assert info.audio_streams[0].sample_rate == 48000
    assert info.subtitle_streams[0].is_image is False
    assert info.chapters[0].title == "Part one"
    assert info.chapters[0].end == 60


def test_parses_attachment_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_probe(monkeypatch, "attachment.json")
    info = probe.probe_media(Path("C:/bin/ffprobe"), Path("C:/movie.mkv"))

    assert info.attachments == [probe.AttachmentStream(2, "cover.jpg", "image/jpeg")]


def test_detects_hdr10_and_hlg(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_probe(monkeypatch, "hdr10.json")
    info = probe.probe_media(Path("ffprobe"), Path("C:/movie.mkv"))
    assert info.video_streams[0].hdr_variant == "hdr10"

    payload = {"streams": [{"codec_type": "video", "color_transfer": "arib-std-b67"}]}
    monkeypatch.setattr(
        probe.subprocess,
        "run",
        lambda args, **kwargs: CompletedProcess(args, 0, stdout=json.dumps(payload), stderr=""),
    )
    video = probe.probe_media(Path("ffprobe"), Path("C:/movie.mkv")).video_streams[0]
    assert video.hdr and video.hdr_variant == "hlg"


def test_detects_image_and_text_subtitles(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_probe(monkeypatch, "pgs.json")
    subtitles = probe.probe_media(Path("ffprobe"), Path("C:/movie.mkv")).subtitle_streams
    assert [item.is_image for item in subtitles] == [True, False]
    assert subtitles[0].forced


def test_missing_fields_use_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"streams": [{"codec_type": "video"}]}
    monkeypatch.setattr(
        probe.subprocess,
        "run",
        lambda args, **kwargs: CompletedProcess(args, 0, stdout=json.dumps(payload), stderr=""),
    )
    video = probe.probe_media(Path("ffprobe"), Path("C:/movie.mkv")).video_streams[0]
    assert video.codec == "unknown" and video.bit_depth == 8 and not video.hdr


def test_ffprobe_failure_is_probe_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        probe.subprocess,
        "run",
        lambda args, **kwargs: CompletedProcess(args, 1, stdout="", stderr="bad input"),
    )
    with pytest.raises(probe.ProbeError, match="bad input"):
        probe.probe_media(Path("ffprobe"), Path("C:/movie.mkv"))


def test_invalid_json_is_probe_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        probe.subprocess,
        "run",
        lambda args, **kwargs: CompletedProcess(args, 0, stdout="{", stderr=""),
    )
    with pytest.raises(probe.ProbeError, match="invalid JSON"):
        probe.probe_media(Path("ffprobe"), Path("C:/movie.mkv"))


def test_probe_reads_audio_bitrate_from_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "format": {"format_name": "matroska", "duration": "10.0", "size": "1000"},
        "streams": [
            {
                "index": 0,
                "codec_name": "aac",
                "codec_type": "audio",
                "channels": 2,
                "bit_rate": "320000",
            }
        ],
    }
    monkeypatch.setattr(
        probe.subprocess,
        "run",
        lambda args, **kwargs: CompletedProcess(args, 0, stdout=json.dumps(payload), stderr=""),
    )
    info = probe.probe_media(Path("ffprobe"), Path("C:/movie.mkv"))
    assert info.audio_streams[0].bitrate == 320000


def test_probe_audio_without_bitrate(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "format": {"format_name": "matroska", "duration": "10.0", "size": "1000"},
        "streams": [
            {
                "index": 0,
                "codec_name": "aac",
                "codec_type": "audio",
                "channels": 2,
            }
        ],
    }
    monkeypatch.setattr(
        probe.subprocess,
        "run",
        lambda args, **kwargs: CompletedProcess(args, 0, stdout=json.dumps(payload), stderr=""),
    )
    info = probe.probe_media(Path("ffprobe"), Path("C:/movie.mkv"))
    assert info.audio_streams[0].bitrate is None


def test_probe_reads_audio_bitrate_from_bps_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "format": {"format_name": "matroska", "duration": "10.0", "size": "1000"},
        "streams": [
            {
                "index": 0,
                "codec_name": "eac3",
                "codec_type": "audio",
                "channels": 6,
                "bit_rate": "N/A",
                "tags": {"BPS": "640000"},
            },
            {
                "index": 1,
                "codec_name": "ac3",
                "codec_type": "audio",
                "channels": 6,
                "tags": {"BPS-eng": "448000"},
            },
            {
                "index": 2,
                "codec_name": "aac",
                "codec_type": "audio",
                "channels": 2,
                "tags": {"bps": "128000"},
            },
        ],
    }
    monkeypatch.setattr(
        probe.subprocess,
        "run",
        lambda args, **kwargs: CompletedProcess(args, 0, stdout=json.dumps(payload), stderr=""),
    )
    info = probe.probe_media(Path("ffprobe"), Path("C:/movie.mkv"))
    assert info.audio_streams[0].bitrate == 640000
    assert info.audio_streams[1].bitrate == 448000
    assert info.audio_streams[2].bitrate == 128000
