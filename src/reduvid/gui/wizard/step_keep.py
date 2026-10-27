# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Step 4: choose which audio and subtitle tracks to keep."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.plan import build_plan, resolve_container
from reduvid.core.probe import format_size
from reduvid.gui.widgets.what_is_this import WhatIsThis
from reduvid.gui.wizard_logic import (
    TrackRow,
    audio_size_summary,
    language_name,
    subtitle_container_note,
    track_rows,
)
from reduvid.gui.wizard_state import VideoEntry, WizardState
from reduvid.i18n import _

EMPTY_SIZE = "—"


def _language_code(value: str | None) -> str:
    return (value or "").strip().lower() or "und"


def _channels_label(channels: int | None) -> str:
    if channels == 1:
        return _("Mono")
    if channels == 2:
        return _("Stereo")
    if channels == 6:
        return "5.1"
    if channels == 8:
        return "7.1"
    if channels is not None and channels > 2:
        return _("{count} channels").format(count=channels)
    return EMPTY_SIZE


def _audio_track_text(row: TrackRow) -> str:
    size = (
        EMPTY_SIZE
        if row.estimated_bytes is None
        else _("~{size}").format(size=format_size(row.estimated_bytes))
    )
    return _("{language} · {codec} · {channels} · {size}").format(
        language=language_name(row.language),
        codec=row.codec,
        channels=_channels_label(row.channels),
        size=size,
    )


def _subtitle_format(row: TrackRow) -> str:
    kind = _("image") if row.is_image else _("text")
    return _("{codec} ({kind})").format(codec=row.codec, kind=kind)


def _subtitle_groups(rows: Iterable[TrackRow]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Group subtitle formats by language; the engine filters subtitles by language."""
    groups: dict[str, list[str]] = {}
    for row in rows:
        code = _language_code(row.language)
        label = _subtitle_format(row)
        formats = groups.setdefault(code, [])
        if label not in formats:
            formats.append(label)
    return tuple((code, tuple(formats)) for code, formats in groups.items())


class StepKeep(QWidget):
    """Choose audio tracks and subtitle languages for the probed videos."""

    def __init__(
        self,
        state: WizardState,
        ffmpeg_info: FFmpegInfo,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._ffmpeg_info = ffmpeg_info
        self._audio_codes: tuple[str, ...] | None = None
        self._audio_signature: object = None
        self._subtitle_signature: object = None
        self.audio_checks: dict[str, QCheckBox] = {}
        self.subtitle_checks: dict[str, QCheckBox] = {}
        self.audio_track_checks: dict[int, QCheckBox] = {}
        self.audio_default_tags: dict[int, QLabel] = {}
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
        self.audio_track_list = QWidget(self.audio_group)
        self.audio_track_list.setObjectName("audioTrackList")
        self.audio_track_layout = QVBoxLayout(self.audio_track_list)
        self.audio_track_layout.setContentsMargins(0, 0, 0, 0)
        self.audio_track_layout.setSpacing(4)
        self.audio_language_list = QWidget(self.audio_group)
        self.audio_language_list.setObjectName("audioLanguageList")
        self.audio_language_layout = QVBoxLayout(self.audio_language_list)
        self.audio_language_layout.setContentsMargins(0, 0, 0, 0)
        self.audio_language_layout.setSpacing(4)
        self.audio_layout.addWidget(self.audio_track_list)
        self.audio_layout.addWidget(self.audio_language_list)
        self.one_audio_per_language = QCheckBox(
            _("One audio track per language (the best one is kept)"), self.audio_group
        )
        self.one_audio_per_language.setObjectName("oneAudioPerLanguageCheck")
        self.one_audio_per_language.setAccessibleName(
            _("One audio track per language (the best one is kept)")
        )
        self.one_audio_per_language.toggled.connect(self._one_audio_toggled)
        self.audio_layout.addWidget(self.one_audio_per_language)
        layout.addWidget(self.audio_group)

        self.audio_warning = QLabel(self)
        self.audio_warning.setObjectName("audioLanguageWarning")
        self.audio_warning.setProperty("role", "muted")
        self.audio_warning.setWordWrap(True)
        self.audio_warning.setVisible(False)
        layout.addWidget(self.audio_warning)

        self.audio_weight_group = QGroupBox(_("Audio size"), self)
        weight_layout = QVBoxLayout(self.audio_weight_group)
        self.reduce_audio = QCheckBox(_("Reduce the audio size"), self.audio_weight_group)
        self.reduce_audio.setObjectName("reduceAudioCheck")
        self.reduce_audio.setAccessibleName(_("Reduce the audio size"))
        self.reduce_audio.toggled.connect(self._state.set_reduce_audio)
        weight_layout.addWidget(self.reduce_audio)
        self.audio_size_summary = QLabel(self.audio_weight_group)
        self.audio_size_summary.setObjectName("audioSizeSummary")
        self.audio_size_summary.setProperty("role", "muted")
        self.audio_size_summary.setWordWrap(True)
        weight_layout.addWidget(self.audio_size_summary)
        layout.addWidget(self.audio_weight_group)

        self.subtitle_group = QGroupBox(_("Subtitle languages"), self)
        self.subtitle_layout = QVBoxLayout(self.subtitle_group)
        layout.addWidget(self.subtitle_group)

        self.subtitle_container_note = QLabel(self)
        self.subtitle_container_note.setObjectName("subtitleContainerNote")
        self.subtitle_container_note.setProperty("role", "muted")
        self.subtitle_container_note.setWordWrap(True)
        self.subtitle_container_note.setVisible(False)
        layout.addWidget(self.subtitle_container_note)

        layout.addWidget(
            WhatIsThis(
                _(
                    "An audio track is the sound of the video, and its format (such as "
                    "AC3, E-AC3 or AAC) is how that sound is stored. MP4 accepts text "
                    "subtitles but not image ones, which only fit in MKV. Reducing the "
                    "audio re-encodes it to AAC: on a normal TV the quality is almost the "
                    "same, but the original format is lost."
                ),
                self,
            )
        )
        layout.addStretch(1)

    def refresh(self) -> None:
        single = self._state.single_video
        rows = track_rows(single.media) if single is not None and single.media else ()
        audio_rows = tuple(row for row in rows if row.kind == "audio")
        self._refresh_audio(single, audio_rows)
        self._refresh_subtitles(single, rows)
        self._refresh_options()
        self._refresh_container_note()

    def _refresh_audio(self, single: VideoEntry | None, audio_rows: tuple[TrackRow, ...]) -> None:
        self.audio_group.setTitle(_("Audio") if single is not None else _("Audio languages"))
        if single is not None:
            self.audio_language_list.setVisible(False)
            if self.audio_checks:
                self._clear_language_checks(self.audio_checks, self.audio_language_layout)
                self._audio_codes = None
            self.audio_track_list.setVisible(bool(audio_rows))
            self.audio_group.setVisible(bool(audio_rows))
            self._rebuild_audio_tracks(audio_rows)
            selected_tracks = self._state.selected_audio_tracks()
            if self._state.one_audio_per_language:
                selected_tracks = self._tracks_kept_by_one_per_language(single)
            self._apply_checks(self.audio_track_checks.items(), selected_tracks)
            self.audio_warning.setText(
                _("If you do not tick any audio track, all of them are kept.")
            )
            show_warning = bool(audio_rows) and not selected_tracks
        else:
            self.audio_track_list.setVisible(False)
            self._clear_track_checks()
            codes = self._state.available_audio_languages()
            visible = bool(codes) or not self._state.videos
            self.audio_language_list.setVisible(visible)
            self.audio_group.setVisible(visible)
            self._rebuild_audio_languages(codes)
            selected = self._state.selected_audio_languages()
            self._apply_checks(self.audio_checks.items(), selected)
            self.audio_warning.setText(
                _("With no audio language selected, every video keeps all its audio tracks.")
            )
            show_warning = bool(codes) and not selected
        self.audio_warning.setVisible(show_warning)

    def _rebuild_audio_tracks(self, rows: tuple[TrackRow, ...]) -> None:
        if rows == self._audio_signature:
            return
        self._clear_track_checks()
        self._audio_signature = rows
        for row in rows:
            text = _audio_track_text(row)
            row_widget = QWidget(self.audio_track_list)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            checkbox = QCheckBox(text, row_widget)
            checkbox.setObjectName("audioTrackChecks")
            checkbox.setAccessibleName(text)
            checkbox.toggled.connect(self._audio_track_toggled)
            row_layout.addWidget(checkbox)
            if row.is_default:
                tag = QLabel(_("Default"), row_widget)
                tag.setProperty("role", "kicker")
                self.audio_default_tags[row.index] = tag
                row_layout.addWidget(tag)
            row_layout.addStretch(1)
            self.audio_track_layout.addWidget(row_widget)
            self.audio_track_checks[row.index] = checkbox
        self._apply_checks(self.audio_track_checks.items(), self._state.selected_audio_tracks())

    def _rebuild_audio_languages(self, codes: tuple[str, ...]) -> None:
        if codes == self._audio_codes:
            return
        self._audio_codes = codes
        self._clear_language_checks(self.audio_checks, self.audio_language_layout)
        for code in codes:
            checkbox = QCheckBox(language_name(code), self.audio_language_list)
            checkbox.setObjectName("audioLanguageChecks")
            checkbox.setProperty("languageCode", code)
            checkbox.setAccessibleName(language_name(code))
            checkbox.toggled.connect(self._audio_toggled)
            self.audio_language_layout.addWidget(checkbox)
            self.audio_checks[code] = checkbox
        if not codes and not self._state.videos:
            self.audio_language_layout.addWidget(
                self._empty_label(_("Add videos to see their audio languages."))
            )

    def _refresh_subtitles(self, single: VideoEntry | None, rows: tuple[TrackRow, ...]) -> None:
        subtitle_rows = tuple(row for row in rows if row.kind == "subtitle")
        if single is not None:
            groups = _subtitle_groups(subtitle_rows)
            signature: object = (True, groups)
            visible = bool(groups)
        else:
            codes = self._state.available_subtitle_languages()
            groups = tuple((code, ()) for code in codes)
            signature = (False, codes)
            visible = bool(codes) or not self._state.videos
        self.subtitle_group.setVisible(visible)
        if signature != self._subtitle_signature:
            self._subtitle_signature = signature
            self._rebuild_subtitles(groups)
        self._apply_checks(self.subtitle_checks.items(), self._state.selected_subtitle_languages())

    def _rebuild_subtitles(self, groups: tuple[tuple[str, tuple[str, ...]], ...]) -> None:
        self._clear_language_checks(self.subtitle_checks, self.subtitle_layout)
        for code, formats in groups:
            if formats:
                text = _("{language} · {formats}").format(
                    language=language_name(code), formats=", ".join(formats)
                )
            else:
                text = language_name(code)
            checkbox = QCheckBox(text, self.subtitle_group)
            checkbox.setObjectName("subtitleLanguageChecks")
            checkbox.setProperty("languageCode", code)
            checkbox.setAccessibleName(text)
            checkbox.toggled.connect(self._subtitle_toggled)
            self.subtitle_layout.addWidget(checkbox)
            self.subtitle_checks[code] = checkbox
        if not groups and not self._state.videos:
            self.subtitle_layout.addWidget(
                self._empty_label(_("Add videos to see their subtitle languages."))
            )

    def _empty_label(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setProperty("role", "muted")
        label.setWordWrap(True)
        return label

    def _refresh_options(self) -> None:
        self.one_audio_per_language.setVisible(self._state.ready)
        self.one_audio_per_language.blockSignals(True)
        self.one_audio_per_language.setChecked(self._state.one_audio_per_language)
        self.one_audio_per_language.blockSignals(False)

        has_audio = any(
            entry.media is not None and bool(entry.media.audio_streams)
            for entry in self._state.videos
        )
        self.audio_weight_group.setVisible(has_audio)
        if not has_audio:
            return
        self.reduce_audio.blockSignals(True)
        self.reduce_audio.setChecked(self._state.reduce_audio)
        self.reduce_audio.blockSignals(False)
        summary = audio_size_summary(self._state.videos, self._state.options(), self._ffmpeg_info)
        if summary.current_bytes is None or summary.final_bytes is None:
            text = _("The audio size of this video cannot be estimated.")
        else:
            text = _("The audio goes from ~{current} to ~{final}").format(
                current=format_size(summary.current_bytes),
                final=format_size(summary.final_bytes),
            )
        self.audio_size_summary.setText(text)

    def _refresh_container_note(self) -> None:
        media_list = [entry.media for entry in self._state.videos if entry.media is not None]
        note = subtitle_container_note(media_list, resolve_container(self._state.options()))
        if note == "image_dropped_mp4":
            text = _("Image subtitles do not fit in MP4 and will be dropped. Text ones are kept.")
        elif note == "image_kept_mkv":
            text = _("Image subtitles are kept in MKV, but Cinecat cannot show them.")
        else:
            text = ""
        self.subtitle_container_note.setText(text)
        self.subtitle_container_note.setVisible(note != "none")

    def _clear_language_checks(self, checks: dict[str, QCheckBox], layout: QVBoxLayout) -> None:
        if checks:
            checks.clear()
        self._clear_layout(layout)

    def _clear_track_checks(self) -> None:
        if not self.audio_track_checks and self._audio_signature is None:
            return
        self.audio_track_checks.clear()
        self.audio_default_tags.clear()
        self._audio_signature = None
        self._clear_layout(self.audio_track_layout)

    def _apply_checks(
        self,
        items: Iterable[tuple[object, QCheckBox]],
        selected: Iterable[object],
    ) -> None:
        selected_values = set(selected)
        for key, checkbox in items:
            checkbox.blockSignals(True)
            checkbox.setChecked(key in selected_values)
            checkbox.blockSignals(False)

    def _tracks_kept_by_one_per_language(self, single: VideoEntry) -> frozenset[int]:
        if single.media is None:
            return frozenset()
        options = replace(self._state.options(), one_audio_per_language=True)
        plan = build_plan(single.media, self._ffmpeg_info, options)
        return frozenset(decision.stream_index for decision in plan.audios)

    def _one_audio_toggled(self, enabled: bool) -> None:
        self._state.set_one_audio_per_language(enabled)
        single = self._state.single_video
        if enabled and single is not None and single.media is not None:
            self._state.set_audio_tracks(self._tracks_kept_by_one_per_language(single))

    def _audio_track_toggled(self, _checked: bool) -> None:
        manual = frozenset(
            index for index, checkbox in self.audio_track_checks.items() if checkbox.isChecked()
        )
        if self._state.one_audio_per_language:
            self._state.set_one_audio_per_language(False, restore=False)
        self._state.set_audio_tracks(manual)

    def _audio_toggled(self, _checked: bool) -> None:
        # Choosing languages is compatible with keeping one track per language.
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
