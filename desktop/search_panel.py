"""Bonus feature: look up one verse by reference or free-text phrase and
see its own curated + semantic connections. Independent of whatever is
currently scrolled into view in the reading pane."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from connections import find_verse, get_connections, search_text, verse_ref
from cards import ConnectionCard, SearchHitCard
import fonts
from theme import colors


class SearchPanel(QWidget):
    verseSelected = Signal(str, int, int)

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        search_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Reference (John 3:16) or a phrase (shepherd)")
        self.input.returnPressed.connect(self._do_search)
        self.button = QPushButton("Search")
        self.button.clicked.connect(self._do_search)
        search_row.addWidget(self.input)
        search_row.addWidget(self.button)
        outer.addLayout(search_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setSpacing(8)
        self.content_layout.addStretch(1)
        self.scroll.setWidget(self.content)
        outer.addWidget(self.scroll)

    def _clear(self):
        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def refresh_fonts(self):
        """Re-runs the current query, if any, so results re-render at
        the new font scale. Idempotent -- same input, same results."""
        if self.input.text().strip():
            self._do_search()

    def _do_search(self):
        query = self.input.text().strip()
        if not query:
            return
        row = find_verse(self.conn, query)
        if row is not None:
            self._render_verse(row)
        else:
            self._render_hits(search_text(self.conn, query, limit=20))

    def _render_hits(self, hits):
        self._clear()
        if not hits:
            lbl = QLabel("No matches.")
            lbl.setStyleSheet(f"color:{colors()['muted']}; font-style:italic;")
            self.content_layout.insertWidget(0, lbl)
            return
        for row in hits:
            card = SearchHitCard(verse_ref(row), row["text"])
            card.clicked.connect(
                lambda book=row["book"], chapter=row["chapter"], verse=row["verse"]: self.verseSelected.emit(book, chapter, verse)
            )
            self.content_layout.insertWidget(self.content_layout.count() - 1, card)

    def _render_verse(self, row):
        c = colors()
        self._clear()
        title = SearchHitCard(verse_ref(row), row["text"])
        title.clicked.connect(
            lambda book=row["book"], chapter=row["chapter"], verse=row["verse"]: self.verseSelected.emit(book, chapter, verse)
        )
        self.content_layout.insertWidget(0, title)

        curated, semantic = get_connections(self.conn, row["id"], limit=10)

        self._add_section_title("Curated cross-references", c["curated"])
        if not curated:
            self._add_empty()
        for r in curated:
            self._add_card(r, c["curated"], True)

        self._add_section_title("Semantic connections", c["semantic"])
        if not semantic:
            self._add_empty()
        for r in semantic:
            self._add_card(r, c["semantic"], False)

    def _add_section_title(self, text: str, color: str):
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(f"color:{color}; font-size:{fonts.px(13)}px; font-weight:bold;")
        self.content_layout.insertWidget(self.content_layout.count() - 1, lbl)

    def _add_empty(self):
        lbl = QLabel("None found.")
        lbl.setStyleSheet(f"color:{colors()['muted']}; font-style:italic; font-size:{fonts.px(14)}px;")
        self.content_layout.insertWidget(self.content_layout.count() - 1, lbl)

    def _add_card(self, row, color: str, is_curated: bool):
        weight_text = f"{row['weight']:.0f} votes" if is_curated else f"{row['weight']:.3f}"
        card = ConnectionCard(verse_ref(row), weight_text, "", row["text"], color)
        card.clicked.connect(
            lambda book=row["book"], chapter=row["chapter"], verse=row["verse"]: self.verseSelected.emit(book, chapter, verse)
        )
        self.content_layout.insertWidget(self.content_layout.count() - 1, card)
