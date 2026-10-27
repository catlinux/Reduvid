# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Step 3: choose how much quality to keep."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, QThread, Slot
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from reduvid.core.ffmpeg import FFmpegInfo
from reduvid.core.plan import EncodePlan, PlanOptions, build_plan
from reduvid.core.probe import MediaInfo, format_size
from reduvid.core.sample import TotalEstimate
from reduvid.gui.widgets.option_card import OptionCard
from reduvid.gui.widgets.what_is_this import WhatIsThis
from reduvid.gui.wizard_logic import change_notes, quality_note
from reduvid.gui.wizard_state import WizardState
from reduvid.gui.workers import LevelsWorker, start_worker_thread
from reduvid.i18n import _
from reduvid.messages import error_text

EstimateKey = tuple[PlanOptions, int, Path]
Reference = tuple[Path, MediaInfo]
_HEIGHTS = (1080, 720, 480)


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


_RECOMMENDED = {"cinecat": "balanced", "modern": "balanced", "archive": "max_savings"}


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


def _estimate_line(estimate: TotalEstimate, original_size: int) -> str:
    """Describe a level estimate against the size of the original file."""
    if estimate.total_bytes is None:
        return _("Video only: about {size}").format(size=format_size(estimate.video_bytes))
    size = format_size(estimate.total_bytes)
    if original_size > 0 and estimate.total_bytes < original_size:
        percent = f"{round((1 - estimate.total_bytes / original_size) * 100)}%"
        return _("About {size} ({percent} smaller)").format(size=size, percent=percent)
    return _("About {size} (not smaller than the original)").format(size=size)


class StepQuality(QWidget):
    """Exclusive quality cards with a recommendation for the chosen destination."""

    def __init__(
        self,
        state: WizardState,
        ffmpeg_info: FFmpegInfo,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._ffmpeg_info = ffmpeg_info
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self.cards: dict[str, OptionCard] = {}
        self._quality_keys: list[str] = []
        self._levels_worker_factory: Callable[..., LevelsWorker] = LevelsWorker
        self._levels_worker: LevelsWorker | None = None
        self._levels_thread: QThread | None = None
        self._estimating_key: EstimateKey | None = None
        self._results: dict[str, TotalEstimate] = {}
        self._results_key: EstimateKey | None = None
        self._error = ""
        self._progress = 0.0
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
        lead = QLabel(
            _(
                "Choose how much you want to shrink. Sizes are only known after "
                "estimating; you can change this later."
            ),
            self,
        )
        lead.setProperty("role", "muted")
        lead.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(lead)

        self.common_notes = QLabel(self)
        self.common_notes.setObjectName("commonNotes")
        self.common_notes.setProperty("role", "muted")
        self.common_notes.setWordWrap(True)
        self.common_notes.hide()
        layout.addWidget(self.common_notes)

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

        self.resolution_label = QLabel(_("Resolution"), self)
        self.resolution_combo = QComboBox(self)
        self.resolution_combo.setObjectName("resolutionCombo")
        self.resolution_combo.setAccessibleName(_("Resolution"))
        self.resolution_combo.currentIndexChanged.connect(self._on_resolution_changed)
        resolution_row = QHBoxLayout()
        resolution_row.setContentsMargins(0, 0, 0, 0)
        resolution_row.setSpacing(8)
        resolution_row.addWidget(self.resolution_label)
        resolution_row.addWidget(self.resolution_combo, 1)
        layout.addLayout(resolution_row)

        self.levels_button = QPushButton(_("Estimate the size of each level"), self)
        self.levels_button.setObjectName("levelsButton")
        self.levels_button.setAccessibleName(_("Estimate the size of each quality level"))
        self.levels_button.clicked.connect(self._start_levels)
        self.levels_progress = QProgressBar(self)
        self.levels_progress.setObjectName("levelsProgress")
        self.levels_progress.setRange(0, 100)
        self.levels_progress.setValue(0)
        self.levels_progress.setMinimumWidth(120)
        self.levels_progress.setAccessibleName(_("Estimate progress"))
        self.levels_progress.hide()
        self.levels_cancel_button = QPushButton(_("Cancel"), self)
        self.levels_cancel_button.setObjectName("levelsCancel")
        self.levels_cancel_button.setAccessibleName(_("Cancel the estimate"))
        self.levels_cancel_button.clicked.connect(self._cancel_clicked)
        self.levels_cancel_button.hide()
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(8)
        controls.addWidget(self.levels_button)
        controls.addWidget(self.levels_progress, 1)
        controls.addWidget(self.levels_cancel_button)
        layout.addLayout(controls)

        self.levels_hint = QLabel(
            _("It can take a couple of minutes, depending on the video and your computer."),
            self,
        )
        self.levels_hint.setObjectName("levelsHint")
        self.levels_hint.setProperty("role", "muted")
        self.levels_hint.setWordWrap(True)
        self.levels_hint.hide()
        layout.addWidget(self.levels_hint)

        self.reference_label = QLabel(self)
        self.reference_label.setObjectName("levelsReference")
        self.reference_label.setProperty("role", "muted")
        self.reference_label.setWordWrap(True)
        self.reference_label.hide()
        layout.addWidget(self.reference_label)

        self.levels_status = QLabel(self)
        self.levels_status.setObjectName("levelsStatus")
        self.levels_status.setWordWrap(True)
        self.levels_status.hide()
        layout.addWidget(self.levels_status)

        self.technical_details = WhatIsThis("", self, title=_("Technical details"))
        layout.addWidget(self.technical_details)
        layout.addStretch(1)
        self._group.idClicked.connect(self._on_selected)

    def _reference(self) -> Reference | None:
        """The video the notes and estimates describe: the longest one with media."""
        ready: list[Reference] = []
        for entry in self._state.videos:
            if entry.media is not None:
                ready.append((entry.path, entry.media))
        if not ready:
            return None
        return max(ready, key=lambda item: item[1].duration)

    def _option_heights(self) -> tuple[int, ...]:
        tallest = 0
        for entry in self._state.videos:
            if entry.media is None:
                continue
            for stream in entry.media.video_streams:
                tallest = max(tallest, stream.height)
        return tuple(height for height in _HEIGHTS if height < tallest)

    def _plan(self, media: MediaInfo, options: PlanOptions, quality: str) -> EncodePlan:
        return build_plan(media, self._ffmpeg_info, replace(options, quality=quality))

    def _technical_text(self, reference: Reference | None, options: PlanOptions) -> str:
        lines = [_crf_explanation()]
        if reference is None:
            return lines[0]
        plan = self._plan(reference[1], options, self._state.quality)
        if not plan.videos:
            return lines[0]
        decision = plan.videos[0]
        lines.append(_("Codec: {codec}").format(codec=decision.codec))
        lines.append(_("Preset: {preset}").format(preset=decision.preset))
        lines.append(_("CRF: {crf}").format(crf=decision.crf))
        if decision.profile is not None:
            lines.append(_("Profile: {profile}").format(profile=decision.profile))
        if decision.level is not None:
            lines.append(_("Level: {level}").format(level=decision.level))
        if decision.pixel_format is not None:
            lines.append(
                _("Pixel format: {pixel_format}").format(pixel_format=decision.pixel_format)
            )
        return "\n".join(lines)

    def _sync(self) -> None:
        reference = self._reference()
        options = self._state.options()
        key: EstimateKey | None = None
        if reference is not None:
            key = (
                replace(options, quality="balanced"),
                reference[1].size,
                reference[0],
            )
        if self._estimating_key is not None and self._estimating_key != key:
            self.cancel_estimate()
        if self._results_key is not None and self._results_key != key:
            self._results = {}
            self._results_key = None
        recommended = _RECOMMENDED.get(self._state.destination, "balanced")
        if reference is None:
            self.common_notes.clear()
            self.common_notes.hide()
        else:
            common = change_notes(
                reference[1], self._plan(reference[1], options, self._state.quality)
            )
            self.common_notes.setText("\n".join(f"• {line}" for line in common))
            self.common_notes.setVisible(bool(common))
        for quality, card in self.cards.items():
            card.set_label(_("Recommended") if quality == recommended else "")
            card.set_notes((quality_note(quality),) if reference is not None else ())
        selected_card = self.cards.get(self._state.quality)
        if selected_card is not None:
            selected_card.setChecked(True)
        self.recommendation_label.setText(_recommendation(self._state.destination))
        self._sync_resolution()
        ready_count = sum(1 for entry in self._state.videos if entry.media is not None)
        if reference is not None and ready_count > 1:
            self.reference_label.setText(
                _("The estimate is for the reference video: {name}.").format(name=reference[0].name)
            )
            self.reference_label.show()
        else:
            self.reference_label.clear()
            self.reference_label.hide()
        self.technical_details.set_text(self._technical_text(reference, options))
        self._apply_levels_widgets()

    def _sync_resolution(self) -> None:
        heights = self._option_heights()
        current = self._state.max_height
        combo = self.resolution_combo
        blocker = QSignalBlocker(combo)
        combo.clear()
        combo.addItem(_("Automatic"), None)
        for height in heights:
            combo.addItem(f"{height}p", height)
        if current is not None and current not in heights:
            combo.addItem(f"{current}p", current)
        index = 0 if current is None else combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.setVisible(bool(heights))
        self.resolution_label.setVisible(bool(heights))
        del blocker

    def _on_selected(self, identifier: int) -> None:
        self._state.set_quality(self._quality_keys[identifier])

    @Slot(int)
    def _on_resolution_changed(self, index: int) -> None:
        data = self.resolution_combo.itemData(index)
        self._state.set_max_height(None if data is None else int(data))

    def _start_levels(self) -> None:
        reference = self._reference()
        if reference is None or self._estimating_key is not None:
            return
        path, media = reference
        options = replace(self._state.options(), quality="balanced")
        worker = self._levels_worker_factory(
            self._ffmpeg_info,
            media,
            options,
            path,
            threads=self._state.threads,
            hw_decode=self._state.hw_decode,
        )
        worker.progress.connect(self._on_levels_progress)
        worker.done.connect(self._on_levels_done)
        worker.failed.connect(self._on_levels_failed)
        worker.finished.connect(self._on_levels_finished)
        self._results = {}
        self._results_key = None
        self._error = ""
        self._estimating_key = (options, media.size, path)
        self._levels_worker = worker
        self._progress = 0.0
        self._apply_levels_widgets()
        self._levels_thread = start_worker_thread(worker)

    def _cancel_clicked(self, _checked: bool = False) -> None:
        self.cancel_estimate()

    def cancel_estimate(self, *, wait: bool = True) -> None:
        """Stop a running estimate and return the cards to their initial state."""
        worker = self._levels_worker
        thread = self._levels_thread
        self._levels_worker = None
        self._estimating_key = None
        self._progress = 0.0
        self._results = {}
        self._results_key = None
        self._error = ""
        if worker is not None:
            worker.cancel()
        if thread is not None:
            thread.quit()
            if wait:
                thread.wait(5000)
        if wait:
            self._levels_thread = None
        self._apply_levels_widgets()

    @Slot(float)
    def _on_levels_progress(self, value: float) -> None:
        if self._estimating_key is None:
            return
        self._progress = min(max(value, 0.0), 1.0)
        self.levels_progress.setValue(int(self._progress * 100))

    @Slot(object)
    def _on_levels_done(self, estimates: object) -> None:
        key = self._estimating_key
        if key is None or not isinstance(estimates, dict):
            return
        self._results = {
            quality: estimate
            for quality, estimate in estimates.items()
            if isinstance(quality, str) and isinstance(estimate, TotalEstimate)
        }
        self._results_key = key
        self._apply_levels_widgets()

    @Slot(str, str)
    def _on_levels_failed(self, code: str, _detail: str) -> None:
        if self._estimating_key is None or code == "cancelled":
            return
        self._error = error_text(code)
        self._apply_levels_widgets()

    @Slot()
    def _on_levels_finished(self) -> None:
        thread = self._levels_thread
        self._levels_worker = None
        self._estimating_key = None
        self._progress = 0.0
        if thread is not None:
            thread.quit()
            thread.wait(5000)
        self._levels_thread = None
        self._apply_levels_widgets()

    def _apply_levels_widgets(self) -> None:
        reference = self._reference()
        estimating = self._estimating_key is not None
        self.levels_button.setVisible(reference is not None)
        self.levels_button.setEnabled(reference is not None and not estimating)
        self.levels_progress.setVisible(estimating)
        self.levels_progress.setValue(int(self._progress * 100) if estimating else 0)
        self.levels_cancel_button.setVisible(estimating)
        self.levels_hint.setVisible(reference is not None)
        self.levels_status.setText(self._error)
        self.levels_status.setVisible(bool(self._error))
        for quality, card in self.cards.items():
            estimate = self._results.get(quality) if reference is not None else None
            if estimate is not None and reference is not None:
                card.set_estimate(_estimate_line(estimate, reference[1].size))
            else:
                card.set_estimate("")
