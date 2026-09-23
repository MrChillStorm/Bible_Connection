"""Shown in place of the chapter view when a Strong's word is clicked:
its full dictionary entry plus every verse that uses it (concordance
browsing). A back control returns to exactly where you were reading --
this page never touches reading_state."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMenu,
    QPushButton, QStyle, QStyledItemDelegate, QVBoxLayout, QWidget,
)

from connections import verse_ref
from strongs import get_entry, get_verses_for_strong
import fonts
from theme import colors

TEXT_ROLE = Qt.ItemDataRole.UserRole
NAV_ROLE = Qt.ItemDataRole.UserRole + 1  # (book, chapter, verse)
ROW_MARGIN = 10
LINE_GAP = 4


class _VerseDelegate(QStyledItemDelegate):
    """Paints a bold reference + wrapped verse text directly, without a
    real widget per row. The concordance list can hold thousands of
    rows (~6,400 for the single most frequent word in the whole KJV) --
    a QVBoxLayout of card widgets lays out every child on every
    geometry change and measurably slows down as more accumulate, while
    a QListWidget only ever calls paint()/sizeHint() for rows actually
    on screen."""

    def _ref_font(self, option):
        font = option.font
        font.setBold(True)
        return font

    def _text_width(self, option):
        widget = option.widget
        width = (widget.viewport().width() if widget else option.rect.width()) - 2 * ROW_MARGIN
        return max(width, 50)

    def sizeHint(self, option, index):
        text = index.data(TEXT_ROLE) or ""
        text_width = self._text_width(option)
        ref_h = QFontMetrics(self._ref_font(option)).height()
        body_h = QFontMetrics(option.font).boundingRect(
            QRect(0, 0, text_width, 0), Qt.TextFlag.TextWordWrap, text
        ).height()
        return QSize(text_width, ROW_MARGIN + ref_h + LINE_GAP + body_h + ROW_MARGIN)

    def paint(self, painter, option, index):
        c = colors()
        painter.save()
        if option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, c["hover_bg"])

        text_width = self._text_width(option)
        x = option.rect.x() + ROW_MARGIN
        y = option.rect.y() + ROW_MARGIN

        ref_font = self._ref_font(option)
        painter.setFont(ref_font)
        painter.setPen(c["ink"])
        ref_h = QFontMetrics(ref_font).height()
        painter.drawText(QRect(x, y, text_width, ref_h), Qt.TextFlag.TextSingleLine, index.data(Qt.ItemDataRole.DisplayRole))

        body_font = option.font
        painter.setFont(body_font)
        body_rect = QRect(x, y + ref_h + LINE_GAP, text_width, option.rect.height())
        painter.drawText(body_rect, Qt.TextFlag.TextWordWrap, index.data(TEXT_ROLE) or "")
        painter.restore()


class _ConcordanceList(QListWidget):
    verseSelected = Signal(str, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(_VerseDelegate(self))
        self.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.setFrameShape(QListWidget.Shape.NoFrame)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.itemClicked.connect(self._on_item_clicked)
        self.customContextMenuRequested.connect(self._on_context_menu)

    def load(self, verses):
        self.clear()
        for row in verses:
            item = QListWidgetItem(verse_ref(row))
            item.setData(TEXT_ROLE, row["text"])
            item.setData(NAV_ROLE, (row["book"], row["chapter"], row["verse"]))
            self.addItem(item)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.scheduleDelayedItemsLayout()  # row heights depend on the new wrap width

    def _on_item_clicked(self, item: QListWidgetItem):
        book, chapter, verse = item.data(NAV_ROLE)
        self.verseSelected.emit(book, chapter, verse)

    def _on_context_menu(self, pos):
        item = self.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        copy_action = menu.addAction("Copy verse")
        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen == copy_action:
            QApplication.clipboard().setText(f"{item.text()} — {item.data(TEXT_ROLE)}")


class WordDetailPage(QWidget):
    backRequested = Signal()
    verseSelected = Signal(str, int, int)

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._current_strong_number = None
        c = colors()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)

        top_bar = QHBoxLayout()
        back_btn = QPushButton("← Back to reading")
        back_btn.clicked.connect(self.backRequested.emit)
        top_bar.addWidget(back_btn)
        top_bar.addStretch(1)
        outer.addLayout(top_bar)

        self.word_label = QLabel()
        self.word_label.setWordWrap(True)
        self.word_label.setStyleSheet("margin-top:12px;")
        outer.addWidget(self.word_label)

        self.gloss_label = QLabel()
        self.gloss_label.setWordWrap(True)
        self.gloss_label.setStyleSheet(f"font-size:{fonts.px(15)}px; color:{c['ink']}; margin-top:6px;")
        outer.addWidget(self.gloss_label)

        self.count_label = QLabel()
        self.count_label.setStyleSheet(f"font-size:{fonts.px(13)}px; color:{c['muted']}; margin-top:10px; margin-bottom:4px;")
        outer.addWidget(self.count_label)

        self.list = _ConcordanceList()
        self.list.verseSelected.connect(self.verseSelected)
        outer.addWidget(self.list)

    def refresh_fonts(self):
        """Re-applies the two labels whose font-size is only otherwise
        set once, in __init__, then re-renders the current word (if
        any) so its inline spans and concordance row heights follow
        the new scale too."""
        c = colors()
        self.gloss_label.setStyleSheet(f"font-size:{fonts.px(15)}px; color:{c['ink']}; margin-top:6px;")
        self.count_label.setStyleSheet(f"font-size:{fonts.px(13)}px; color:{c['muted']}; margin-top:10px; margin-bottom:4px;")
        if self._current_strong_number is not None:
            self.show_word(self._current_strong_number)

    def show_word(self, strong_number: str):
        entry = get_entry(self.conn, strong_number)
        if entry is None:
            return
        self._current_strong_number = strong_number
        c = colors()

        self.word_label.setText(
            f'<span style="font-size:{fonts.px(28)}px; font-weight:bold; color:{c["ink"]};">{entry["original_word"]}</span>'
            f'&nbsp;&nbsp;<span style="font-size:{fonts.px(17)}px; font-style:italic; color:{c["semantic"]};">{entry["transliteration"]}</span>'
            f'&nbsp;&nbsp;<span style="font-size:{fonts.px(13)}px; color:{c["muted"]};">{strong_number}</span>'
        )

        parts = []
        if entry["definition"]:
            parts.append(entry["definition"])
        if entry["kjv_translations"]:
            parts.append(f"<b>KJV renderings:</b> {entry['kjv_translations']}")
        self.gloss_label.setText("<br><br>".join(parts) if parts else "No definition available.")

        verses, total = get_verses_for_strong(self.conn, strong_number)
        self.count_label.setText(f"USED IN {total} VERSE{'S' if total != 1 else ''}")
        self.list.load(verses)
