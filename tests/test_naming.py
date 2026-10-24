# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

from pathlib import Path

import pytest

from reduvid.core.naming import build_output_path, build_temp_path, finalize_output


def test_build_output_path_uses_expected_name(tmp_path: Path) -> None:
    source = tmp_path / "Vídeo de prueba.mov"

    assert build_output_path(source, tmp_path, ".mkv") == tmp_path / "Vídeo de prueba_reduvid.mkv"


def test_build_output_path_increments_collisions(tmp_path: Path) -> None:
    source = tmp_path / "clip.mp4"
    (tmp_path / "clip_reduvid.mkv").touch()
    (tmp_path / "clip_reduvid (2).mkv").touch()

    assert build_output_path(source, tmp_path, "mkv") == tmp_path / "clip_reduvid (3).mkv"


def test_build_temp_path_uses_hidden_name_and_avoids_collision(tmp_path: Path) -> None:
    output = tmp_path / "clip_reduvid (2).mkv"
    temp = tmp_path / ".clip.reduvid-tmp.mkv"
    temp.touch()

    assert build_temp_path(output) == tmp_path / ".clip.reduvid-tmp (2).mkv"


def test_finalize_output_moves_file(tmp_path: Path) -> None:
    temp = tmp_path / ".clip.reduvid-tmp.mkv"
    output = tmp_path / "clip_reduvid.mkv"
    temp.write_bytes(b"converted")

    finalize_output(temp, output)

    assert output.read_bytes() == b"converted"
    assert not temp.exists()


def test_finalize_output_does_not_overwrite(tmp_path: Path) -> None:
    temp = tmp_path / ".clip.reduvid-tmp.mkv"
    output = tmp_path / "clip_reduvid.mkv"
    temp.write_bytes(b"converted")
    output.write_bytes(b"original")

    with pytest.raises(FileExistsError):
        finalize_output(temp, output)

    assert output.read_bytes() == b"original"
    assert temp.read_bytes() == b"converted"
