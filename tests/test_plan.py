# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from pathlib import Path

import pytest

from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.plan import (
    HDR_TO_SDR_FILTERS,
    PlanOptions,
    build_plan,
    estimate_stream_bytes,
    rank_audio,
    resolve_container,
)
from reduvid.core.probe import AudioStream, MediaInfo, SubtitleStream, VideoStream


def media(
    *,
    videos: list[VideoStream] | None = None,
    audios: list[AudioStream] | None = None,
    subtitles: list[SubtitleStream] | None = None,
) -> MediaInfo:
    return MediaInfo(
        Path("input.mkv"), "matroska", 60, 1, videos or [], audios or [], subtitles or [], []
    )


def ffmpeg(*filters: str) -> FFmpegInfo:
    return FFmpegInfo(Path("ffmpeg"), Path("ffprobe"), "test", frozenset(), frozenset(filters), ())


def test_cinecat_defaults_and_resolution() -> None:
    video = VideoStream(0, "hevc", 3840, 2160, 24)
    audio = AudioStream(1, "aac", 2, None, False)
    plan = build_plan(media(videos=[video], audios=[audio]), ffmpeg())

    assert PlanOptions().destination == "cinecat"
    assert PlanOptions().container is None
    assert plan.destination == "cinecat"
    assert plan.container == "mp4"
    assert plan.videos[0].codec == "libx264"
    assert plan.videos[0].pixel_format == "yuv420p"
    assert plan.videos[0].target_height == 1080
    assert [(item.action, item.codec) for item in plan.audios] == [("copy", None)]


def test_container_automatic_and_explicit() -> None:
    video = VideoStream(0, "h264", 1920, 1080, 24)

    assert resolve_container(PlanOptions()) == "mp4"
    assert resolve_container(PlanOptions(destination="modern")) == "mkv"
    assert resolve_container(PlanOptions(container="mkv")) == "mkv"
    assert resolve_container(PlanOptions(destination="modern", container="mp4")) == "mp4"
    plan = build_plan(media(videos=[video]), ffmpeg(), PlanOptions(destination="modern"))
    assert plan.container == "mkv"
    plan = build_plan(media(videos=[video]), ffmpeg(), PlanOptions(container="mkv"))
    assert plan.container == "mkv"


def test_cinecat_crfs_and_resolution() -> None:
    video = VideoStream(0, "hevc", 3840, 2160, 24)
    for quality, expected in (("high", 19), ("balanced", 22), ("max_savings", 25)):
        plan = build_plan(media(videos=[video]), ffmpeg(), PlanOptions(quality=quality))
        assert plan.videos[0].crf == expected
        assert plan.videos[0].target_height == 1080
        assert any(item.code == "resolution_reduced" for item in plan.warnings)


def test_resolution_warning_reports_both_heights() -> None:
    video = VideoStream(0, "hevc", 3840, 2160, 24)
    plan = build_plan(media(videos=[video]), ffmpeg())

    warning = next(item for item in plan.warnings if item.code == "resolution_reduced")
    assert warning.params == {"stream_index": 0, "from_height": 2160, "to_height": 1080}


def test_cinecat_explicit_max_height() -> None:
    video = VideoStream(0, "hevc", 1920, 1080, 24)
    plan = build_plan(media(videos=[video]), ffmpeg(), PlanOptions(max_height=720))

    assert plan.videos[0].target_height == 720
    assert any(item.code == "resolution_reduced" for item in plan.warnings)


@pytest.mark.parametrize("destination", ["cinecat", "modern", "archive"])
def test_video_below_max_height_is_not_reduced(destination: str) -> None:
    video = VideoStream(0, "hevc", 1280, 720, 24)
    plan = build_plan(
        media(videos=[video]), ffmpeg(), PlanOptions(destination=destination, max_height=1080)
    )

    assert plan.videos[0].target_height is None
    assert not plan.warnings


@pytest.mark.parametrize("destination", ["modern", "archive"])
def test_other_profiles_reduce_only_with_max_height(destination: str) -> None:
    video = VideoStream(0, "hevc", 3840, 2160, 24)
    plan = build_plan(media(videos=[video]), ffmpeg(), PlanOptions(destination=destination))

    assert plan.videos[0].target_height is None
    assert not any(item.code == "resolution_reduced" for item in plan.warnings)


@pytest.mark.parametrize("destination", ["modern", "archive"])
def test_other_profiles_apply_max_height(destination: str) -> None:
    video = VideoStream(0, "hevc", 3840, 2160, 24)
    plan = build_plan(
        media(videos=[video]), ffmpeg(), PlanOptions(destination=destination, max_height=1080)
    )

    assert plan.videos[0].target_height == 1080
    assert any(item.code == "resolution_reduced" for item in plan.warnings)


def test_odd_max_height_rounds_down_to_even() -> None:
    video = VideoStream(0, "hevc", 1920, 1080, 24)
    plan = build_plan(media(videos=[video]), ffmpeg(), PlanOptions(max_height=721))

    assert plan.videos[0].target_height == 720


def test_hdr_cinecat_and_modern() -> None:
    video = VideoStream(0, "hevc", 1920, 1080, 24, hdr=True, hdr_variant="hdr10")
    supported = build_plan(media(videos=[video]), ffmpeg("zscale", "tonemap"))
    assert supported.videos[0].filters == HDR_TO_SDR_FILTERS
    assert "hdr_tonemap_unavailable" not in {item.code for item in supported.warnings}
    unavailable = build_plan(media(videos=[video]), ffmpeg())
    assert any(item.code == "hdr_tonemap_unavailable" for item in unavailable.warnings)
    modern = build_plan(media(videos=[video]), ffmpeg(), PlanOptions(destination="modern"))
    assert modern.videos[0].filters == ()
    assert modern.videos[0].pixel_format == "yuv420p10le"


def test_cinecat_audio_rules() -> None:
    audios = [
        AudioStream(1, "ac3", 6, None, False),
        AudioStream(2, "dts", 2, None, False),
        AudioStream(3, "aac", 2, None, False),
        AudioStream(4, "mp3", 2, None, False),
    ]
    plan = build_plan(media(audios=audios), ffmpeg())
    assert [(item.action, item.codec, item.bitrate) for item in plan.audios] == [
        ("encode", "aac", "384k"),
        ("encode", "aac", "192k"),
        ("copy", None, None),
        ("copy", None, None),
    ]
    assert [warning.code for warning in plan.warnings] == ["audio_recoded", "audio_recoded"]


def test_modern_audio_rules_keep_the_previous_behaviour() -> None:
    audios = [
        AudioStream(1, "ac3", 6, None, False),
        AudioStream(2, "dts", 6, None, False),
        AudioStream(3, "dts", 2, None, False),
        AudioStream(4, "aac", 2, None, False),
    ]
    plan = build_plan(media(audios=audios), ffmpeg(), PlanOptions(destination="modern"))
    assert [(item.action, item.codec, item.bitrate) for item in plan.audios] == [
        ("copy", None, None),
        ("encode", "ac3", "640k"),
        ("encode", "aac", "192k"),
        ("copy", None, None),
    ]


def test_cinecat_caps_more_than_six_channels() -> None:
    audio = AudioStream(1, "eac3", 8, None, False)
    plan = build_plan(media(audios=[audio]), ffmpeg())

    assert plan.audios[0].action == "encode"
    assert plan.audios[0].codec == "aac"
    assert plan.audios[0].channels == 6


def test_subtitle_rules_by_container() -> None:
    subtitles = [
        SubtitleStream(1, "hdmv_pgs_subtitle", None, True, False, False),
        SubtitleStream(2, "subrip", None, False, False, False),
    ]
    mkv = build_plan(media(subtitles=subtitles), ffmpeg(), PlanOptions(container="mkv"))
    assert [item.action for item in mkv.subtitles] == ["copy", "copy"]
    assert any(item.code == "image_subtitle_burn_in" for item in mkv.warnings)
    mp4 = build_plan(media(subtitles=subtitles), ffmpeg(), PlanOptions(container="mp4"))
    assert [(item.action, item.codec) for item in mp4.subtitles] == [
        ("drop", None),
        ("convert", "mov_text"),
    ]
    assert any(item.code == "image_subtitle_dropped_mp4" for item in mp4.warnings)


@pytest.mark.parametrize(
    ("destination", "expected_codec", "crfs", "preset"),
    [
        ("cinecat", "libx264", (19, 22, 25), "medium"),
        ("modern", "libx265", (21, 24, 27), "medium"),
        ("archive", "libx265", (21, 24, 27), "slow"),
    ],
)
def test_codec_quality_and_preset(
    destination: str, expected_codec: str, crfs: tuple[int, int, int], preset: str
) -> None:
    video = VideoStream(0, "h264", 1920, 1080, 24)
    for quality, expected_crf in zip(("high", "balanced", "max_savings"), crfs, strict=True):
        plan = build_plan(media(videos=[video]), ffmpeg(), PlanOptions(destination, quality))
        assert plan.videos[0].codec == expected_codec
        assert plan.videos[0].crf == expected_crf
        assert plan.videos[0].preset == preset


def test_audio_language_filter_keeps_only_matching_tracks() -> None:
    audios = [
        AudioStream(1, "aac", 2, "eng", True),
        AudioStream(2, "aac", 2, "spa", False),
        AudioStream(3, "aac", 2, "cat", False),
    ]
    plan = build_plan(
        media(audios=audios), ffmpeg(), PlanOptions(audio_languages=frozenset({"spa"}))
    )

    assert [item.stream_index for item in plan.audios] == [2]


def test_language_filter_is_case_insensitive_and_und_matches_missing() -> None:
    audios = [
        AudioStream(1, "aac", 2, None, False),
        AudioStream(2, "aac", 2, "", False),
        AudioStream(3, "aac", 2, "UND", False),
        AudioStream(4, "aac", 2, "SPA", False),
    ]
    without_language = build_plan(
        media(audios=audios), ffmpeg(), PlanOptions(audio_languages=frozenset({"und"}))
    )
    uppercase = build_plan(
        media(audios=audios), ffmpeg(), PlanOptions(audio_languages=frozenset({"spa"}))
    )

    assert [item.stream_index for item in without_language.audios] == [1, 2, 3]
    assert [item.stream_index for item in uppercase.audios] == [4]


def test_no_language_filter_keeps_every_track() -> None:
    audios = [AudioStream(1, "aac", 2, "eng", False), AudioStream(2, "aac", 2, "spa", False)]
    subtitles = [
        SubtitleStream(3, "subrip", "eng", False, False, False),
        SubtitleStream(4, "subrip", "spa", False, False, False),
    ]

    plan = build_plan(media(audios=audios, subtitles=subtitles), ffmpeg(), PlanOptions())

    assert [item.stream_index for item in plan.audios] == [1, 2]
    assert [item.stream_index for item in plan.subtitles] == [3, 4]
    assert not plan.warnings


def test_audio_filter_falls_back_to_all_when_nothing_matches() -> None:
    audios = [AudioStream(1, "aac", 2, "eng", False), AudioStream(2, "aac", 2, "spa", False)]
    plan = build_plan(
        media(audios=audios), ffmpeg(), PlanOptions(audio_languages=frozenset({"fra"}))
    )

    assert [item.stream_index for item in plan.audios] == [1, 2]
    assert [warning.code for warning in plan.warnings] == ["audio_filter_kept_all"]


def test_excluded_tracks_do_not_generate_warnings() -> None:
    audios = [
        AudioStream(1, "dts", 6, "eng", False),
        AudioStream(2, "aac", 2, "spa", False),
    ]
    subtitles = [
        SubtitleStream(3, "hdmv_pgs_subtitle", "eng", True, False, False),
        SubtitleStream(4, "subrip", "spa", False, False, False),
    ]
    plan = build_plan(
        media(audios=audios, subtitles=subtitles),
        ffmpeg(),
        PlanOptions(audio_languages=frozenset({"spa"}), subtitle_languages=frozenset({"spa"})),
    )

    assert [item.stream_index for item in plan.audios] == [2]
    assert [item.stream_index for item in plan.subtitles] == [4]
    assert not plan.warnings


def test_subtitle_filter_can_remove_every_subtitle() -> None:
    subtitles = [SubtitleStream(1, "subrip", "eng", False, False, False)]
    plan = build_plan(
        media(subtitles=subtitles),
        ffmpeg(),
        PlanOptions(subtitle_languages=frozenset({"fra"})),
    )

    assert plan.subtitles == ()
    assert not plan.warnings


def test_estimate_stream_bytes() -> None:
    # Con datos: 640 kbps durante 8700 s (~696 MB)
    assert estimate_stream_bytes(640_000, 8700.0) == 696_000_000
    assert estimate_stream_bytes(128_000, 60.0) == 960_000
    # Sin datos: o falta bitrate, o falta duration, o ambos
    assert estimate_stream_bytes(None, 60.0) is None
    assert estimate_stream_bytes(128_000, None) is None
    assert estimate_stream_bytes(None, None) is None


def test_audio_tracks_selection() -> None:
    audios = [
        AudioStream(1, "aac", 2, "eng", False),
        AudioStream(2, "ac3", 6, "spa", False),
        AudioStream(3, "dts", 6, "spa", False),
    ]
    # audio_tracks selecciona las pistas exactas por índice ffprobe
    plan = build_plan(media(audios=audios), ffmpeg(), PlanOptions(audio_tracks=frozenset({2, 3})))
    assert [item.stream_index for item in plan.audios] == [2, 3]

    # audio_tracks prevalece sobre audio_languages
    plan_override = build_plan(
        media(audios=audios),
        ffmpeg(),
        PlanOptions(audio_tracks=frozenset({1}), audio_languages=frozenset({"spa"})),
    )
    assert [item.stream_index for item in plan_override.audios] == [1]


def test_audio_tracks_empty_or_nonmatching_keeps_all_and_warns() -> None:
    audios = [
        AudioStream(1, "aac", 2, "eng", False),
        AudioStream(2, "ac3", 6, "spa", False),
    ]
    # Ninguna pista coincide con los índices dados
    plan_no_match = build_plan(
        media(audios=audios), ffmpeg(), PlanOptions(audio_tracks=frozenset({99}))
    )
    assert [item.stream_index for item in plan_no_match.audios] == [1, 2]
    assert any(warning.code == "audio_filter_kept_all" for warning in plan_no_match.warnings)

    # Conjunto vacío
    plan_empty = build_plan(media(audios=audios), ffmpeg(), PlanOptions(audio_tracks=frozenset()))
    assert [item.stream_index for item in plan_empty.audios] == [1, 2]
    assert any(warning.code == "audio_filter_kept_all" for warning in plan_empty.warnings)


def test_one_audio_per_language_chooses_best_track() -> None:
    # Caso real: MKV con 2 pistas en español + 1 en inglés
    # Pista 1: español estéreo 2.0 E-AC3 224k
    # Pista 2: español 5.1 AC3 640k (más canales y mayor bitrate)
    # Pista 3: inglés estéreo 2.0 AAC 128k
    audios = [
        AudioStream(1, "eac3", 2, "spa", False, bitrate=224_000),
        AudioStream(2, "ac3", 6, "spa", False, bitrate=640_000),
        AudioStream(3, "aac", 2, "eng", True, bitrate=128_000),
    ]
    plan = build_plan(media(audios=audios), ffmpeg(), PlanOptions(one_audio_per_language=True))
    # Se queda la pista 2 (mejor en spa) y la pista 3 (única en eng)
    assert [item.stream_index for item in plan.audios] == [2, 3]


def test_one_audio_per_language_tie_breaking_order() -> None:
    # Mismos canales: mayor bitrate gana
    spa_low = AudioStream(1, "ac3", 6, "spa", False, bitrate=448_000)
    spa_high = AudioStream(2, "ac3", 6, "spa", False, bitrate=640_000)
    plan_bitrate = build_plan(
        media(audios=[spa_low, spa_high]), ffmpeg(), PlanOptions(one_audio_per_language=True)
    )
    assert [item.stream_index for item in plan_bitrate.audios] == [2]

    # Mismos canales y bitrate: is_default gana
    spa_nodef = AudioStream(1, "ac3", 6, "spa", False, bitrate=640_000)
    spa_def = AudioStream(2, "ac3", 6, "spa", True, bitrate=640_000)
    plan_default = build_plan(
        media(audios=[spa_nodef, spa_def]), ffmpeg(), PlanOptions(one_audio_per_language=True)
    )
    assert [item.stream_index for item in plan_default.audios] == [2]

    # Mismos canales, bitrate e is_default: menor índice gana
    spa_first = AudioStream(1, "ac3", 6, "spa", False, bitrate=640_000)
    spa_second = AudioStream(3, "ac3", 6, "spa", False, bitrate=640_000)
    plan_index = build_plan(
        media(audios=[spa_first, spa_second]), ffmpeg(), PlanOptions(one_audio_per_language=True)
    )
    assert [item.stream_index for item in plan_index.audios] == [1]

    # Preserva el orden original de las pistas en el contenedor
    spa_worse = AudioStream(0, "ac3", 2, "spa", False, bitrate=192_000)
    eng = AudioStream(1, "aac", 2, "eng", False, bitrate=128_000)
    spa_better = AudioStream(2, "ac3", 6, "spa", False, bitrate=640_000)
    plan_order = build_plan(
        media(audios=[spa_worse, eng, spa_better]),
        ffmpeg(),
        PlanOptions(one_audio_per_language=True),
    )
    assert [item.stream_index for item in plan_order.audios] == [1, 2]

    # Sin idioma (None y "") agrupan bajo "und"
    und_stereo = AudioStream(0, "aac", 2, None, False, bitrate=128_000)
    und_surround = AudioStream(1, "ac3", 6, "", False, bitrate=640_000)
    plan_und = build_plan(
        media(audios=[und_stereo, und_surround]), ffmpeg(), PlanOptions(one_audio_per_language=True)
    )
    assert [item.stream_index for item in plan_und.audios] == [1]


def test_reduce_audio() -> None:
    audios = [
        # 5.1 no-aac -> aac 256k con aviso
        AudioStream(1, "ac3", 6, "spa", False, bitrate=640_000),
        # Estéreo no-aac -> aac 128k con aviso
        AudioStream(2, "ac3", 2, "spa", False, bitrate=192_000),
        # AAC estéreo ya bajo (128k) -> se copia, sin aviso
        AudioStream(3, "aac", 2, "eng", False, bitrate=128_000),
        # AAC 5.1 ya bajo (256k) -> se copia, sin aviso
        AudioStream(4, "aac", 6, "eng", False, bitrate=256_000),
        # AAC estéreo con bitrate superior al objetivo (320k) -> se recodifica a 128k con aviso
        AudioStream(5, "aac", 2, "fra", False, bitrate=320_000),
    ]
    plan = build_plan(media(audios=audios), ffmpeg(), PlanOptions(reduce_audio=True))
    assert [(item.action, item.codec, item.bitrate) for item in plan.audios] == [
        ("encode", "aac", "256k"),
        ("encode", "aac", "128k"),
        ("copy", None, None),
        ("copy", None, None),
        ("encode", "aac", "128k"),
    ]
    warnings = [w for w in plan.warnings if w.code == "audio_reduced"]
    assert len(warnings) == 3
    assert warnings[0].params == {"stream_index": 1, "bitrate": "256k"}
    assert warnings[1].params == {"stream_index": 2, "bitrate": "128k"}
    assert warnings[2].params == {"stream_index": 5, "bitrate": "128k"}


def test_rank_audio_utility() -> None:
    s1 = AudioStream(1, "aac", 2, "spa", False, bitrate=128_000)
    s2 = AudioStream(2, "ac3", 6, "spa", False, bitrate=640_000)
    assert rank_audio([s1, s2]) == [s2, s1]
