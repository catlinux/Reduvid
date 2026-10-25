# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Step 3: choose how much quality to keep."""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_cache_dir
from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from reduvid.core.estimate import estimate_from_sample
from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.plan import EncodePlan, Warning, build_plan
from reduvid.core.probe import MediaInfo
from reduvid.core.profile_store import list_profiles, load_profile, save_profile
from reduvid.core.sample import sample_window
from reduvid.gui.widgets.option_card import OptionCard
from reduvid.gui.widgets.what_is_this import WhatIsThis
from reduvid.gui.wizard_logic import format_size, summarize
from reduvid.gui.wizard_state import WizardState
from reduvid.gui.workers import SampleResult, SampleWorker, start_worker_thread
from reduvid.i18n import _
from reduvid.messages import warning_text


def _options() -> tuple[tuple[str, str, str], ...]:
    return (
        (
            "high",
            _("Almost identical"),
            _("You won't notice the difference, even on a big TV."),
        ),
        (
            "balanced",
            _("Balanced"),
            _("You can only see the difference if you look closely. The best trade-off."),
        ),
        (
            "max_savings",
            _("Maximum savings"),
            _(
                "You will notice it in dark scenes or with lots of movement. "
                "For phones or archiving."
            ),
        ),
    )


_RECOMMENDED = {"jellyfin": "balanced", "modern": "balanced", "archive": "max_savings"}


def _recommendation(destination: str) -> str:
    if destination == "archive":
        return _(
            "Why Maximum savings? When archiving, the priority is saving space and a "
            "slower encode does not matter."
        )
    if destination == "modern":
        return _(
            "Why Balanced? Modern devices play H.265: you save more space while keeping "
            "very good quality."
        )
    return _(
        "Why Balanced? You will watch them on Jellyfin: it saves a lot of space and "
        "plays directly, without the server converting anything."
    )


def _crf_explanation() -> str:
    return _(
        "A video stores each frame of the picture. Reduvid decides how much detail to "
        "keep in each one, like when a phone saves a photo at a higher or lower "
        "quality. Internally this is called CRF: a lower number keeps more detail and "
        "takes more space."
    )


class StepQuality(QWidget):
    """Exclusive quality cards with a recommendation for the chosen destination."""

    def __init__(
        self,
        state: WizardState,
        ffmpeg_info: FFmpegInfo,
        parent: QWidget | None = None,
        *,
        profiles_dir: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._ffmpeg_info = ffmpeg_info
        self._profiles_dir = profiles_dir
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self.cards: dict[str, OptionCard] = {}
        self._quality_keys: list[str] = []
        self._sample_thread: QThread | None = None
        self._sample_worker: SampleWorker | None = None
        self._sample_running = False
        self._sample_quality: str | None = None
        self._result_quality: str | None = None
        self._build_ui()
        state.changed.connect(self._sync)
        self._sync()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        heading = QLabel(_("More quality or more space?"), self)
        heading.setProperty("role", "heading")
        heading.setWordWrap(True)
        lead = QLabel(_("Choose how much you want to shrink. You can change this later."), self)
        lead.setProperty("role", "muted")
        lead.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(lead)

        for identifier, (quality, name, description) in enumerate(_options()):
            card = OptionCard(name, "", description, self)
            self._group.addButton(card, identifier)
            layout.addWidget(card)
            self.cards[quality] = card
            self._quality_keys.append(quality)

        self.recommendation_label = QLabel(self)
        self.recommendation_label.setObjectName("recommendation")
        self.recommendation_label.setProperty("role", "muted")
        self.recommendation_label.setWordWrap(True)
        layout.addWidget(self.recommendation_label)
        layout.addWidget(WhatIsThis(_crf_explanation(), self))

        self.warnings_container = QWidget(self)
        self.warnings_container.setObjectName("qualityWarnings")
        self.warnings_layout = QVBoxLayout(self.warnings_container)
        self.warnings_layout.setContentsMargins(0, 0, 0, 0)
        self.warnings_layout.setSpacing(4)
        layout.addWidget(self.warnings_container)

        self.sample_button = QPushButton(_("&Try a 30-second sample"), self)
        self.sample_button.setObjectName("trySampleButton")
        self.sample_button.setAccessibleName(_("&Try a 30-second sample"))
        self.sample_button.clicked.connect(self._on_sample_clicked)
        self.sample_status = QLabel(self)
        self.sample_status.setObjectName("sampleStatus")
        self.sample_status.setProperty("role", "muted")
        self.sample_status.setWordWrap(True)
        self.sample_result = self._build_sample_result()
        layout.addWidget(self.sample_button)
        layout.addWidget(self.sample_status)
        layout.addWidget(self.sample_result)

        profile_row = QHBoxLayout()
        self.profile_combo = QComboBox(self)
        self.profile_combo.setObjectName("profileCombo")
        self.profile_combo.setAccessibleName(_("Saved profiles"))
        self.profile_combo.setMinimumWidth(0)
        self.profile_combo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.apply_profile_button = QPushButton(_("Apply profile"), self)
        self.apply_profile_button.setObjectName("applyProfileButton")
        self.apply_profile_button.setAccessibleName(_("Apply profile"))
        self.apply_profile_button.setMinimumWidth(0)
        self.apply_profile_button.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        self.apply_profile_button.clicked.connect(self.apply_selected_profile)
        self.save_profile_button = QPushButton(_("Save as profile…"), self)
        self.save_profile_button.setObjectName("saveProfileButton")
        self.save_profile_button.setAccessibleName(_("Save as profile…"))
        self.save_profile_button.setMinimumWidth(0)
        self.save_profile_button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.save_profile_button.clicked.connect(self.save_current_profile)
        profile_row.addWidget(self.profile_combo, 1)
        profile_buttons = QHBoxLayout()
        profile_buttons.addWidget(self.apply_profile_button, 1)
        profile_buttons.addWidget(self.save_profile_button, 1)
        self.profile_status = QLabel(self)
        self.profile_status.setObjectName("profileStatus")
        self.profile_status.setProperty("role", "muted")
        self.profile_status.setWordWrap(True)
        layout.addLayout(profile_row)
        layout.addLayout(profile_buttons)
        layout.addWidget(self.profile_status)
        layout.addStretch(1)
        self._group.idClicked.connect(self._on_selected)
        self.reload_profiles()

    def reload_profiles(self) -> None:
        names = list_profiles(self._profiles_dir)
        current = self.profile_combo.currentData()
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for name in names:
            self.profile_combo.addItem(name, name)
        if current in names:
            self.profile_combo.setCurrentIndex(self.profile_combo.findData(current))
        self.profile_combo.blockSignals(False)
        enabled = bool(names)
        self.profile_combo.setEnabled(enabled)
        self.apply_profile_button.setEnabled(enabled)

    def apply_selected_profile(self) -> None:
        name = self.profile_combo.currentData()
        if not isinstance(name, str):
            return
        try:
            options = load_profile(name, self._profiles_dir)
        except (OSError, ValueError) as error:
            self.profile_status.setText(
                _("Could not load the profile: {error}").format(error=error)
            )
            return
        try:
            self._state.apply_options(options)
        except ValueError as error:
            self.profile_status.setText(
                _("Could not apply the profile: {error}").format(error=error)
            )
            return
        self.profile_status.setText(_("Profile applied."))

    def save_current_profile(self) -> None:
        name, accepted = QInputDialog.getText(self, _("Save profile"), _("Profile name"))
        if not accepted:
            return
        if not name.strip():
            self.profile_status.setText(_("The profile name cannot be empty."))
            return
        try:
            save_profile(name, self._state.options(), self._profiles_dir)
        except (OSError, ValueError) as error:
            self.profile_status.setText(
                _("Could not save the profile: {error}").format(error=error)
            )
            return
        self.reload_profiles()
        index = self.profile_combo.findData(name)
        if index >= 0:
            self.profile_combo.setCurrentIndex(index)
        self.profile_status.setText(_("Profile saved."))

    def _build_sample_result(self) -> QWidget:
        panel = QWidget(self)
        panel.setObjectName("sampleResult")
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        panel.setVisible(False)
        column = QVBoxLayout(panel)
        column.setContentsMargins(12, 10, 12, 10)
        column.setSpacing(6)

        images = QHBoxLayout()
        self.before_frame = self._build_frame(images, _("Original frame"), _("Before"))
        self.after_frame = self._build_frame(images, _("Encoded frame"), _("After"))
        column.addLayout(images)

        self.estimate_label = QLabel(panel)
        self.estimate_label.setWordWrap(True)
        self.savings_label = QLabel(panel)
        self.savings_label.setProperty("role", "muted")
        self.savings_label.setWordWrap(True)
        column.addWidget(self.estimate_label)
        column.addWidget(self.savings_label)
        return panel

    def _build_frame(self, row: QHBoxLayout, accessible: str, caption: str) -> QLabel:
        box = QVBoxLayout()
        title = QLabel(caption, self)
        title.setProperty("role", "muted")
        frame = QLabel(self)
        frame.setObjectName("sampleFrame")
        frame.setAccessibleName(accessible)
        frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame.setMinimumSize(160, 90)
        box.addWidget(title)
        box.addWidget(frame)
        row.addLayout(box)
        return frame

    def _on_selected(self, identifier: int) -> None:
        self._state.set_quality(self._quality_keys[identifier])

    def _sync(self) -> None:
        recommended = _RECOMMENDED.get(self._state.destination, "balanced")
        for quality, option_card in self.cards.items():
            is_recommended = quality == recommended
            option_card.set_label(_("Recommended") if is_recommended else "")
            option_card.set_recommended(is_recommended)
        selected_card = self.cards.get(self._state.quality)
        if selected_card is not None:
            selected_card.setChecked(True)
        self.recommendation_label.setText(_recommendation(self._state.destination))
        self._show_quality_warnings()
        self._update_sample_button()
        if self._result_quality is not None and self._state.quality != self._result_quality:
            self._clear_sample_result()
            self.sample_status.setText(_("Quality changed. Run the sample again."))

    def _show_quality_warnings(self) -> None:
        while self.warnings_layout.count():
            entry = self.warnings_layout.takeAt(0)
            if entry is None:
                continue
            widget = entry.widget()
            if widget is not None:
                widget.deleteLater()
        video_entry = next(
            (item for item in self._state.videos if item.media is not None),
            None,
        )
        warnings: tuple[Warning, ...] = ()
        if video_entry is not None:
            summary = summarize(video_entry, self._ffmpeg_info, self._state.options())
            if summary is not None:
                warnings = summary.warnings
        for warning in warnings:
            label = QLabel(warning_text(warning), self.warnings_container)
            label.setObjectName("compatWarning")
            label.setWordWrap(True)
            self.warnings_layout.addWidget(label)
        self.warnings_container.setVisible(bool(warnings))

    def _first_media(self) -> MediaInfo | None:
        return next(
            (entry.media for entry in self._state.videos if entry.media is not None),
            None,
        )

    def _update_sample_button(self) -> None:
        self.sample_button.setEnabled(self._first_media() is not None and not self._sample_running)

    def _on_sample_clicked(self) -> None:
        if self._sample_running:
            return
        media = self._first_media()
        if media is None:
            return
        plan = build_plan(media, self._ffmpeg_info, self._state.options())
        start, duration = sample_window(media.duration)
        if duration <= 0:
            self.sample_status.setText(_("This video is too short to try a sample."))
            return
        self._clear_sample_result()
        self._sample_quality = self._state.quality
        self._sample_running = True
        self._update_sample_button()
        self.sample_status.setText(_("Encoding a 30-second sample…"))
        worker = self.create_sample_worker(media, plan, start, duration)
        worker.finished.connect(self._on_sample_finished)
        worker.failed.connect(self._on_sample_failed)
        self._sample_worker = worker
        self._sample_thread = start_worker_thread(worker)

    def create_sample_worker(
        self,
        media: MediaInfo,
        plan: EncodePlan,
        start_seconds: float,
        duration_seconds: float,
    ) -> SampleWorker:
        return SampleWorker(
            media,
            plan,
            self._ffmpeg_info,
            media.path,
            start_seconds,
            duration_seconds,
            Path(user_cache_dir("reduvid")) / "sample",
        )

    def _on_sample_finished(self, result: object) -> None:
        self._sample_running = False
        self._sample_worker = None
        self._sample_thread = None
        self._update_sample_button()
        if not isinstance(result, SampleResult):
            return
        if self._sample_quality != self._state.quality:
            self._sample_quality = None
            self._clear_sample_result()
            self.sample_status.setText(_("Quality changed. Run the sample again."))
            return
        self._show_sample_result(result)

    def _on_sample_failed(self, message: str) -> None:
        self._sample_running = False
        self._sample_worker = None
        self._sample_thread = None
        self._update_sample_button()
        self.sample_status.setText(
            _("Could not generate the sample: {error}").format(error=message)
        )

    def _show_sample_result(self, result: SampleResult) -> None:
        original_sample = 0
        if result.total_duration_seconds > 0:
            original_sample = round(
                result.original_total_bytes
                * result.sample_duration_seconds
                / result.total_duration_seconds
            )
        estimate = estimate_from_sample(
            original_sample_bytes=original_sample,
            encoded_sample_bytes=result.encoded_sample_bytes,
            sample_duration_seconds=result.sample_duration_seconds,
            total_duration_seconds=result.total_duration_seconds,
            elapsed_encode_seconds=result.encode_seconds,
        )
        savings = 0.0
        if result.original_total_bytes > 0:
            savings = (1 - estimate.estimated_total_bytes / result.original_total_bytes) * 100
        self._load_frame(self.before_frame, result.original_frame_path)
        self._load_frame(self.after_frame, result.encoded_frame_path)
        self.estimate_label.setText(
            _("Estimated total size: {size}").format(
                size=format_size(estimate.estimated_total_bytes)
            )
        )
        self.savings_label.setText(_("Estimated savings: {percent:.0f}%").format(percent=savings))
        self.sample_result.setVisible(True)
        self._result_quality = self._sample_quality
        self._sample_quality = None
        self._state.set_sample_result(result)
        self.sample_status.setText(_("Sample ready."))

    def _load_frame(self, label: QLabel, path: Path) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            label.setText(_("Frame unavailable"))
            label.setPixmap(QPixmap())
            return
        label.setText("")
        label.setPixmap(
            pixmap.scaled(
                240,
                135,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _clear_sample_result(self) -> None:
        self.sample_result.setVisible(False)
        for label in (self.before_frame, self.after_frame):
            label.clear()
            label.setText("")
        self.estimate_label.clear()
        self.savings_label.clear()
        self._result_quality = None
        self._state.clear_sample_result()
