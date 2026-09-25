"""Browsable feed of ML-found ('semantic') connections that have no
curated cross-reference behind them -- for discovering something
independent of whatever's currently being read, rather than reacting
to it."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from bible_connection.core.connections import get_surprising_connections
from bible_connection.ui import fonts
from bible_connection.ui.cards import DiscoveryCard
from bible_connection.ui.theme import colors

BATCH_SIZE = 20


class DiscoveryPane(QWidget):
    verseSelected = Signal(str, int, int)

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._last_rows = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        self.intro = QLabel(
            "Connections a machine-learning model found on its own, with no "
            "traditional cross-reference behind them — a place to browse for "
            "something you weren't already reading toward."
        )
        self.intro.setWordWrap(True)
        self.intro.setStyleSheet(f"color:{colors()['muted']}; font-size:{fonts.px(13)}px; margin-bottom:2px;")
        outer.addWidget(self.intro)

        controls = QHBoxLayout()
        self.cross_testament_check = QCheckBox("Old ↔ New Testament only")
        self.cross_testament_check.setChecked(True)
        self.cross_testament_check.toggled.connect(self._load_batch)
        shuffle_btn = QPushButton("Shuffle")
        shuffle_btn.clicked.connect(self._load_batch)
        controls.addWidget(self.cross_testament_check)
        controls.addStretch(1)
        controls.addWidget(shuffle_btn)
        outer.addLayout(controls)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setSpacing(8)
        self.content_layout.addStretch(1)
        self.scroll.setWidget(self.content)
        outer.addWidget(self.scroll)

        self._load_batch()

    def _clear(self):
        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _load_batch(self):
        self._last_rows = get_surprising_connections(
            self.conn, limit=BATCH_SIZE, cross_testament_only=self.cross_testament_check.isChecked()
        )
        self.scroll.verticalScrollBar().setValue(0)
        self._render_rows(self._last_rows)

    def refresh_fonts(self):
        """Re-renders the current batch at the new font scale, without
        re-sampling -- a font-size change shouldn't shuffle the feed
        out from under you."""
        self.intro.setStyleSheet(f"color:{colors()['muted']}; font-size:{fonts.px(13)}px; margin-bottom:2px;")
        self._render_rows(self._last_rows)

    def _render_rows(self, rows):
        self._clear()
        if not rows:
            lbl = QLabel("No matches — try unchecking the testament filter.")
            lbl.setStyleSheet(f"color:{colors()['muted']}; font-style:italic;")
            self.content_layout.insertWidget(0, lbl)
            return
        accent = colors()["semantic"]
        for row in rows:
            card = DiscoveryCard(row, accent)
            card.verseASelected.connect(self.verseSelected)
            card.verseBSelected.connect(self.verseSelected)
            self.content_layout.insertWidget(self.content_layout.count() - 1, card)
