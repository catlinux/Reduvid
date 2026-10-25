# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Step 3: choose how much quality to keep."""

from __future__ import annotations

from PySide6.QtWidgets import QButtonGroup, QLabel, QVBoxLayout, QWidget

from reduvid.gui.widgets.option_card import OptionCard
from reduvid.gui.widgets.what_is_this import WhatIsThis
from reduvid.gui.wizard_state import WizardState
from reduvid.i18n import _


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

    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self.cards: dict[str, OptionCard] = {}
        self._quality_keys: list[str] = []
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
        layout.addStretch(1)
        self._group.idClicked.connect(self._on_selected)

    def _on_selected(self, identifier: int) -> None:
        self._state.set_quality(self._quality_keys[identifier])

    def _sync(self) -> None:
        recommended = _RECOMMENDED.get(self._state.destination, "balanced")
        for quality, option_card in self.cards.items():
            option_card.set_label(_("Recommended") if quality == recommended else "")
        selected_card = self.cards.get(self._state.quality)
        if selected_card is not None:
            selected_card.setChecked(True)
        self.recommendation_label.setText(_recommendation(self._state.destination))
