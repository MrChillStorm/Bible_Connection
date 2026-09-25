"""Live connections list: shows curated + semantic connections for
whatever set of verses is currently visible in the reading pane."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from bible_connection.core.connections import get_connections_for_verses, verse_ref
from bible_connection.ui import fonts
from bible_connection.ui.cards import ConnectionCard
from bible_connection.ui.theme import colors


class ConnectionsPane(QWidget):
    verseSelected = Signal(str, int, int)
    verseHoverChanged = Signal(object)  # verse id (int) while hovering a card, or None

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._latest_verse_ids: list[int] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setSpacing(8)
        self.content_layout.addStretch(1)
        self.scroll.setWidget(self.content)
        outer.addWidget(self.scroll)

        self._placeholder()

    def _placeholder(self):
        self._clear()
        lbl = QLabel("Scroll the reading pane to see connections for the visible verses.")
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color:{colors()['muted']}; font-style:italic;")
        self.content_layout.insertWidget(0, lbl)

    def update_for_verses(self, verse_ids):
        self._latest_verse_ids = verse_ids
        curated, semantic = get_connections_for_verses(self.conn, verse_ids, limit=15)
        self._render(curated, semantic)

    def refresh_fonts(self):
        """Re-renders whatever's currently shown at the new font scale,
        without re-querying (a plain re-render of the same data)."""
        if self._latest_verse_ids:
            self.update_for_verses(self._latest_verse_ids)
        else:
            self._placeholder()

    def _clear(self):
        self.verseHoverChanged.emit(None)  # cards about to be destroyed won't fire leaveEvent
        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _add_section_title(self, text: str, color: str):
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(f"color:{color}; font-size:{fonts.px(13)}px; font-weight:bold;")
        self.content_layout.insertWidget(self.content_layout.count() - 1, lbl)

    def _add_empty(self):
        lbl = QLabel("None found.")
        lbl.setStyleSheet(f"color:{colors()['muted']}; font-style:italic; font-size:{fonts.px(14)}px;")
        self.content_layout.insertWidget(self.content_layout.count() - 1, lbl)

    def _add_card(self, c, color: str, is_curated: bool):
        v = c["verse"]
        source = c["source_verse"]
        weight_text = f"{c['weight']:.0f} votes" if is_curated else f"{c['weight']:.3f}"
        source_text = f"from {verse_ref(source)}"
        card = ConnectionCard(verse_ref(v), weight_text, source_text, v["text"], color)
        card.clicked.connect(
            lambda book=v["book"], chapter=v["chapter"], verse=v["verse"]: self.verseSelected.emit(book, chapter, verse)
        )
        card.hoverChanged.connect(
            lambda hovered, vid=source["id"]: self.verseHoverChanged.emit(vid if hovered else None)
        )
        self.content_layout.insertWidget(self.content_layout.count() - 1, card)

    def _render(self, curated, semantic):
        c = colors()
        self._clear()
        self._add_section_title("Curated cross-references", c["curated"])
        if not curated:
            self._add_empty()
        for item in curated:
            self._add_card(item, c["curated"], True)

        self._add_section_title("Semantic connections", c["semantic"])
        if not semantic:
            self._add_empty()
        for item in semantic:
            self._add_card(item, c["semantic"], False)
