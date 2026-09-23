"""Live Strong's word list: every Hebrew/Greek-tagged word for whatever
set of verses is currently visible in the reading pane, plus a search
box to look up any word in the whole concordance by number (G26, H430)
or by transliteration/gloss (agape, love) without needing it on screen.
Hovering a word highlights its occurrence(s) in the reading pane;
clicking opens the full dictionary entry + concordance view."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QLineEdit, QScrollArea, QVBoxLayout, QWidget

from cards import StrongsCard
from strongs import get_words_for_verses, search_strongs
from theme import colors

PLACEHOLDER = "Scroll the reading pane to see its Strong's-tagged Hebrew/Greek words here."
EMPTY = "No Strong's-tagged words in view."


class StrongsPane(QWidget):
    wordHoverChanged = Signal(object)  # strong_number (str) while hovering, or None
    wordSelected = Signal(str)         # strong_number

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._latest_verse_ids: list[int] = []
        self._search_active = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search the concordance: a word or number (agape, G26, H430)")
        self.search_input.textChanged.connect(self._on_search_changed)
        outer.addWidget(self.search_input)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setSpacing(8)
        self.content_layout.addStretch(1)
        self.scroll.setWidget(self.content)
        outer.addWidget(self.scroll)

        self._message(PLACEHOLDER)

    def _clear(self):
        self.wordHoverChanged.emit(None)  # cards about to be destroyed won't fire leaveEvent
        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _message(self, text: str):
        self._clear()
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color:{colors()['muted']}; font-style:italic;")
        self.content_layout.insertWidget(0, lbl)

    def _render(self, rows, count_suffix: str, empty_text: str):
        if not rows:
            self._message(empty_text)
            return
        self._clear()
        accent = colors()["semantic"]
        for row in rows:
            card = StrongsCard(row, accent, count_suffix=count_suffix)
            card.hoverChanged.connect(
                lambda hovered, num=row["strong_number"]: self.wordHoverChanged.emit(num if hovered else None)
            )
            card.clicked.connect(lambda num=row["strong_number"]: self.wordSelected.emit(num))
            self.content_layout.insertWidget(self.content_layout.count() - 1, card)

    def _on_search_changed(self, text: str):
        query = text.strip()
        if not query:
            self._search_active = False
            self.update_for_verses(self._latest_verse_ids)
            return
        self._search_active = True
        results = search_strongs(self.conn, query)
        self._render(results, "in the Bible", f'No match for "{query}".')

    def update_for_verses(self, verse_ids):
        self._latest_verse_ids = verse_ids
        if self._search_active:
            return
        words = get_words_for_verses(self.conn, verse_ids)
        self._render(words, "in view", EMPTY)

    def refresh_fonts(self):
        """Re-renders whatever's currently shown (a search result set
        or the live in-view list) at the new font scale. If nothing's
        been shown yet, the placeholder text has no explicit font-size
        of its own, so it already picks up the new base font for free."""
        if self._search_active:
            self._on_search_changed(self.search_input.text())
        elif self._latest_verse_ids:
            self.update_for_verses(self._latest_verse_ids)
