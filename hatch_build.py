# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Hatch build hook that compiles gettext catalogs into the built wheel."""

from __future__ import annotations

from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po
from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict[str, object]) -> None:
        locale_dir = Path(self.root) / "src" / "reduvid" / "locale"
        compiled: list[str] = []
        for po_path in sorted(locale_dir.glob("*/LC_MESSAGES/*.po")):
            mo_path = po_path.with_suffix(".mo")
            with po_path.open("rb") as po_file:
                catalog = read_po(po_file)
            with mo_path.open("wb") as mo_file:
                write_mo(mo_file, catalog)
            compiled.append(mo_path.relative_to(self.root).as_posix())

        if self.target_name == "wheel":
            artifacts = build_data.setdefault("artifacts", [])
            if isinstance(artifacts, list):
                artifacts.extend(compiled)
