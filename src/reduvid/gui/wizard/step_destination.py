# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Step 5: output folder, container and replacement options."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from reduvid.core.plan import resolve_container
from reduvid.gui.widgets.option_card import OptionCard
from reduvid.gui.wizard_state import WizardState
from reduvid.i18n import _


class StepDestination(QWidget):
    """Choose where files are written and how the originals are handled."""

    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._container_group = QButtonGroup(self)
        self._container_group.setExclusive(True)
        self.container_cards: dict[str, OptionCard] = {}
        self._container_keys: list[str] = []
        self._build_ui()
        state.changed.connect(self.refresh)
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        heading = QLabel(_("Destination"), self)
        heading.setProperty("role", "heading")
        heading.setWordWrap(True)
        lead = QLabel(_("Choose where the converted files go and how they are stored."), self)
        lead.setProperty("role", "muted")
        lead.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(lead)

        folder_group = QGroupBox(_("Output folder"), self)
        folder_layout = QVBoxLayout(folder_group)
        self.same_folder_radio = QRadioButton(_("Same folder as each video"), folder_group)
        self.same_folder_radio.setAccessibleName(_("Same folder as each video"))
        self.other_folder_radio = QRadioButton(_("Another folder"), folder_group)
        self.other_folder_radio.setAccessibleName(_("Another folder"))
        self.same_folder_radio.toggled.connect(self._folder_changed)
        self.other_folder_radio.toggled.connect(self._folder_changed)
        folder_layout.addWidget(self.same_folder_radio)
        folder_layout.addWidget(self.other_folder_radio)

        folder_row = QHBoxLayout()
        self.folder_edit = QLineEdit(folder_group)
        self.folder_edit.setObjectName("outputFolderEdit")
        self.folder_edit.setAccessibleName(_("Output folder"))
        self.folder_edit.editingFinished.connect(self._folder_edited)
        self.browse_button = QPushButton(_("&Browse…"), folder_group)
        self.browse_button.setObjectName("browseOutputFolder")
        self.browse_button.setAccessibleName(_("Browse for the output folder"))
        self.browse_button.clicked.connect(self._browse_folder)
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(self.browse_button)
        folder_layout.addLayout(folder_row)
        layout.addWidget(folder_group)

        container_group = QGroupBox(_("Container"), self)
        container_layout = QVBoxLayout(container_group)
        for identifier, (key, name, tag, description) in enumerate(
            (
                (
                    "mkv",
                    _("MKV"),
                    _("Recommended"),
                    _("Keeps every track and subtitle format."),
                ),
                (
                    "mp4",
                    _("MP4"),
                    _("More compatible"),
                    _("Plays on more devices, but image subtitles are dropped."),
                ),
            )
        ):
            card = OptionCard(name, tag, description, container_group)
            self._container_group.addButton(card, identifier)
            container_layout.addWidget(card)
            self.container_cards[key] = card
            self._container_keys.append(key)
        self._container_group.idClicked.connect(self._container_selected)
        layout.addWidget(container_group)

        self.replace_original = QCheckBox(_("Replace the original"), self)
        self.replace_original.setObjectName("replaceOriginal")
        self.replace_original.setAccessibleName(_("Replace the original"))
        self.replace_original.toggled.connect(self._state.set_replace_original)
        layout.addWidget(self.replace_original)
        replace_hint = QLabel(
            _("The original is sent to the trash only if the copy is verified."), self
        )
        replace_hint.setProperty("role", "muted")
        replace_hint.setWordWrap(True)
        layout.addWidget(replace_hint)

        self.reduce_4k = QCheckBox(_("Reduce 4K video to 1080p"), self)
        self.reduce_4k.setObjectName("reduce4k")
        self.reduce_4k.setAccessibleName(_("Reduce 4K video to 1080p"))
        self.reduce_4k.toggled.connect(self._state.set_reduce_4k)
        layout.addWidget(self.reduce_4k)
        self.reduce_4k_hint = QLabel(
            _("If you keep 4K, Cinecat will have to convert it while you watch."), self
        )
        self.reduce_4k_hint.setProperty("role", "muted")
        self.reduce_4k_hint.setWordWrap(True)
        layout.addWidget(self.reduce_4k_hint)
        layout.addStretch(1)
        QWidget.setTabOrder(self.same_folder_radio, self.other_folder_radio)
        QWidget.setTabOrder(self.other_folder_radio, self.folder_edit)
        QWidget.setTabOrder(self.folder_edit, self.browse_button)
        QWidget.setTabOrder(self.browse_button, self.container_cards["mkv"])
        QWidget.setTabOrder(self.container_cards["mkv"], self.container_cards["mp4"])
        QWidget.setTabOrder(self.container_cards["mp4"], self.replace_original)
        QWidget.setTabOrder(self.replace_original, self.reduce_4k)

    def refresh(self) -> None:
        output_dir = self._state.output_dir
        self.same_folder_radio.blockSignals(True)
        self.other_folder_radio.blockSignals(True)
        self.same_folder_radio.setChecked(output_dir is None)
        self.other_folder_radio.setChecked(output_dir is not None)
        self.same_folder_radio.blockSignals(False)
        self.other_folder_radio.blockSignals(False)
        self.folder_edit.setText(str(output_dir) if output_dir is not None else "")
        self.folder_edit.setEnabled(output_dir is not None)
        self.browse_button.setEnabled(output_dir is not None)

        self._sync_container_cards()

        self.replace_original.blockSignals(True)
        self.replace_original.setChecked(self._state.replace_original)
        self.replace_original.blockSignals(False)

        show_reduce = self._state.destination == "cinecat" and self._state.has_4k()
        self.reduce_4k.setVisible(show_reduce)
        self.reduce_4k_hint.setVisible(show_reduce)
        if show_reduce:
            self.reduce_4k.blockSignals(True)
            self.reduce_4k.setChecked(self._state.reduce_4k)
            self.reduce_4k.blockSignals(False)

    def _sync_container_cards(self) -> None:
        if self._state.destination == "cinecat":
            self._set_container_card(
                "mkv",
                "",
                _(
                    "Keeps every track and subtitle format, but Cinecat will convert it "
                    "while you watch"
                ),
            )
            self._set_container_card("mp4", _("Recommended"), _("Plays directly in Cinecat"))
        else:
            self._set_container_card(
                "mkv", _("Recommended"), _("Keeps every track and subtitle format.")
            )
            self._set_container_card(
                "mp4",
                _("More compatible"),
                _("Plays on more devices, but image subtitles are dropped."),
            )
        card = self.container_cards.get(resolve_container(self._state.options()))
        if card is not None:
            card.setChecked(True)

    def _set_container_card(self, key: str, tag: str, description: str) -> None:
        card = self.container_cards.get(key)
        if card is None:
            return
        card.description_label.setText(description)
        card.set_label(tag)

    def _folder_changed(self) -> None:
        if self.other_folder_radio.isChecked():
            self.folder_edit.setEnabled(True)
            self.browse_button.setEnabled(True)
            self._folder_edited()
        else:
            self.folder_edit.setEnabled(False)
            self.browse_button.setEnabled(False)
            self._state.set_output_dir(None)

    def _folder_edited(self) -> None:
        if not self.other_folder_radio.isChecked():
            return
        text = self.folder_edit.text().strip()
        self._state.set_output_dir(Path(text).expanduser() if text else None)

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, _("Choose the output folder"), self.folder_edit.text()
        )
        if folder:
            self.folder_edit.setText(folder)
            self._state.set_output_dir(Path(folder))

    def _container_selected(self, identifier: int) -> None:
        self._state.set_container(self._container_keys[identifier])
