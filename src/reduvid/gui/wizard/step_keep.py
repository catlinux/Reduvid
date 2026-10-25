# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Step 4: choose which audio and subtitle languages to keep."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from reduvid.gui.widgets.what_is_this import WhatIsThis
from reduvid.gui.wizard_logic import language_name
from reduvid.gui.wizard_state import WizardState
from reduvid.i18n import _


class StepKeep(QWidget):
    """Checkboxes for the languages found in the probed videos."""

    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._audio_codes: tuple[str, ...] = ()
        self._subtitle_codes: tuple[str, ...] = ()
        self.audio_checks: dict[str, QCheckBox] = {}
        self.subtitle_checks: dict[str, QCheckBox] = {}
        self._build_ui()
        state.changed.connect(self.refresh)
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        heading = QLabel(_("What to keep"), self)
        heading.setProperty("role", "heading")
        heading.setWordWrap(True)
        lead = QLabel(_("Choose the audio and subtitle languages you understand."), self)
        lead.setProperty("role", "muted")
        lead.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(lead)

        self.audio_group = QGroupBox(_("Audio languages"), self)
        self.audio_layout = QVBoxLayout(self.audio_group)
        self.audio_warning = QLabel(
            _("With no audio language selected, every video keeps all its audio tracks."),
            self,
        )
        self.audio_warning.setObjectName("audioLanguageWarning")
        self.audio_warning.setProperty("role", "muted")
        self.audio_warning.setWordWrap(True)
        self.audio_warning.setVisible(False)
        layout.addWidget(self.audio_group)
        layout.addWidget(self.audio_warning)

        self.subtitle_group = QGroupBox(_("Subtitle languages"), self)
        self.subtitle_layout = QVBoxLayout(self.subtitle_group)
        layout.addWidget(self.subtitle_group)

        layout.addWidget(
            WhatIsThis(
                _(
                    "Audio and subtitle tracks carry a language tag. Keep the ones you "
                    "understand; a track without a tag is shown as no language "
                    "indicated."
                ),
                self,
            )
        )
        layout.addStretch(1)

    def refresh(self) -> None:
        audio = self._state.available_audio_languages()
        subtitles = self._state.available_subtitle_languages()
        self._rebuild_audio(audio)
        self._rebuild_subtitles(subtitles)
        self.audio_warning.setVisible(bool(audio) and not self._state.selected_audio_languages())

    def _rebuild_audio(self, codes: tuple[str, ...]) -> None:
        if codes == self._audio_codes:
            self._apply_checks(self.audio_checks, self._state.selected_audio_languages())
            return
        self._audio_codes = codes
        self.audio_checks.clear()
        self._clear_layout(self.audio_layout)
        for code in codes:
            checkbox = QCheckBox(language_name(code), self.audio_group)
            checkbox.setProperty("languageCode", code)
            checkbox.setAccessibleName(language_name(code))
            checkbox.toggled.connect(self._audio_toggled)
            self.audio_layout.addWidget(checkbox)
            self.audio_checks[code] = checkbox
        if not codes:
            self.audio_layout.addWidget(
                QLabel(_("Add videos to see their audio languages."), self.audio_group)
            )
        self._apply_checks(self.audio_checks, self._state.selected_audio_languages())

    def _rebuild_subtitles(self, codes: tuple[str, ...]) -> None:
        if codes == self._subtitle_codes:
            self._apply_checks(self.subtitle_checks, self._state.selected_subtitle_languages())
            return
        self._subtitle_codes = codes
        self.subtitle_checks.clear()
        self._clear_layout(self.subtitle_layout)
        for code in codes:
            checkbox = QCheckBox(language_name(code), self.subtitle_group)
            checkbox.setProperty("languageCode", code)
            checkbox.setAccessibleName(language_name(code))
            checkbox.toggled.connect(self._subtitle_toggled)
            self.subtitle_layout.addWidget(checkbox)
            self.subtitle_checks[code] = checkbox
        if not codes:
            self.subtitle_layout.addWidget(
                QLabel(_("Add videos to see their subtitle languages."), self.subtitle_group)
            )
        self._apply_checks(self.subtitle_checks, self._state.selected_subtitle_languages())

    def _apply_checks(self, checks: dict[str, QCheckBox], selected: frozenset[str]) -> None:
        for code, checkbox in checks.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(code in selected)
            checkbox.blockSignals(False)

    def _audio_toggled(self, _checked: bool) -> None:
        self._state.set_audio_languages(
            [code for code, checkbox in self.audio_checks.items() if checkbox.isChecked()]
        )

    def _subtitle_toggled(self, _checked: bool) -> None:
        self._state.set_subtitle_languages(
            [code for code, checkbox in self.subtitle_checks.items() if checkbox.isChecked()]
        )

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            entry = layout.takeAt(0)
            if entry is None:
                continue
            widget = entry.widget()
            if widget is not None:
                widget.deleteLater()
