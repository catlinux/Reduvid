# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Step 2: where the videos will be watched."""

from __future__ import annotations

from PySide6.QtWidgets import QButtonGroup, QLabel, QVBoxLayout, QWidget

from reduvid.gui.widgets.option_card import OptionCard
from reduvid.gui.wizard_state import WizardState
from reduvid.i18n import _


# Card key, destination it selects, card title, tag and description.
def _options() -> tuple[tuple[str, str, str, str, str], ...]:
    return (
        (
            "jellyfin",
            "jellyfin",
            _("Jellyfin"),
            _("Direct play"),
            _("TV, phone or browser through your Jellyfin server."),
        ),
        (
            "modern",
            "modern",
            _("Modern devices"),
            _("H.265"),
            _("Newer phones, tablets and TVs that play H.265."),
        ),
        (
            "archive",
            "archive",
            _("Save for archive"),
            _("H.265"),
            _("Videos you keep for later; saving space matters more than speed."),
        ),
        (
            "unknown",
            "jellyfin",
            _("I don't know"),
            "",
            _("Use the Jellyfin profile, which works on almost everything."),
        ),
    )


class StepTarget(QWidget):
    """Exclusive destination cards, including the safe "I don't know" option."""

    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self.cards: dict[str, OptionCard] = {}
        self._keys: list[tuple[str, str]] = []
        self._selected_key: str | None = None
        self._build_ui()
        state.changed.connect(self._sync)
        self._sync()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        heading = QLabel(_("Where will you watch them?"), self)
        heading.setProperty("role", "heading")
        heading.setWordWrap(True)
        lead = QLabel(
            _("Choose the device you will use the most. You can change this later."), self
        )
        lead.setProperty("role", "muted")
        lead.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(lead)

        for identifier, (key, destination, name, tag, description) in enumerate(_options()):
            card = OptionCard(name, tag, description, self)
            card.setObjectName("card")
            self._group.addButton(card, identifier)
            layout.addWidget(card)
            self.cards[key] = card
            self._keys.append((key, destination))
        layout.addStretch(1)
        self._group.idClicked.connect(self._on_selected)

    def _on_selected(self, identifier: int) -> None:
        key, destination = self._keys[identifier]
        self._selected_key = key
        self._state.set_destination(destination)

    def _sync(self) -> None:
        current = None
        if self._selected_key is not None:
            destinations = dict(self._keys)
            if destinations.get(self._selected_key) == self._state.destination:
                current = self._selected_key
        if current is None:
            current = next(
                (key for key, destination in self._keys if destination == self._state.destination),
                "jellyfin",
            )
        card = self.cards.get(current)
        if card is not None:
            card.setChecked(True)
