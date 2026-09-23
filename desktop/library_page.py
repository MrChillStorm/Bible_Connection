"""Start page: Old/New Testament books grouped by traditional genre, with
a per-book 'read' checkbox. Clicking a book's name opens the reader."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from book_status import get_all_read, set_read
from books import BOOK_ORDER, NT_GROUPS, OT_GROUPS
import fonts
from theme import colors


def _read_style(c: dict) -> str:
    return (
        "text-align:left; padding:4px 6px; border:none; background:transparent; "
        f"color:{c['muted']}; text-decoration: line-through;"
    )


def _unread_style(c: dict) -> str:
    return f"text-align:left; padding:4px 6px; border:none; background:transparent; color:{c['ink']};"


class LibraryPage(QWidget):
    bookSelected = Signal(str)

    def __init__(self, user_conn, parent=None):
        super().__init__(parent)
        self.conn = user_conn  # book_status only -- this page never touches the content database
        self._book_buttons: dict[str, QPushButton] = {}
        c = colors()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)

        self.title_label = QLabel("Bible Connections")
        self.title_label.setStyleSheet(f"font-size:{fonts.px(26)}px; font-weight: bold; color:{c['curated']};")
        outer.addWidget(self.title_label)

        self.progress_label = QLabel()
        self.progress_label.setStyleSheet(f"color:{c['muted']}; margin-bottom: 12px;")
        outer.addWidget(self.progress_label)

        self.columns_layout = QHBoxLayout()
        self.columns_layout.setSpacing(28)
        outer.addLayout(self.columns_layout)

        self._rebuild_columns()

    def _rebuild_columns(self):
        while self.columns_layout.count():
            item = self.columns_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        read_set = get_all_read(self.conn)
        self._update_progress_label(read_set)
        self.columns_layout.addWidget(self._build_testament_column("OLD TESTAMENT", OT_GROUPS, read_set))
        self.columns_layout.addWidget(self._build_testament_column("NEW TESTAMENT", NT_GROUPS, read_set))

    def refresh_fonts(self):
        c = colors()
        self.title_label.setStyleSheet(f"font-size:{fonts.px(26)}px; font-weight: bold; color:{c['curated']};")
        self._rebuild_columns()

    def _update_progress_label(self, read_set: set[str]):
        self.progress_label.setText(
            f"{len(read_set)} of {len(BOOK_ORDER)} books read — "
            f"choose a book to start reading, check one off once you've finished it."
        )

    def _build_testament_column(self, heading: str, groups, read_set: set[str]) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(2)
        c = colors()

        head = QLabel(heading)
        head.setStyleSheet(f"font-size:{fonts.px(16)}px; font-weight: bold; color:{c['curated']}; letter-spacing:1px;")
        layout.addWidget(head)

        for group_name, book_list in groups:
            group_label = QLabel(group_name)
            group_label.setStyleSheet(f"font-size:{fonts.px(13)}px; font-weight: bold; color:{c['semantic']}; margin-top: 10px;")
            layout.addWidget(group_label)
            for book in book_list:
                layout.addLayout(self._book_row(book, book in read_set))

        layout.addStretch(1)
        scroll.setWidget(content)
        return scroll

    def _book_row(self, book: str, is_read: bool) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(4, 0, 4, 0)

        checkbox = QCheckBox()
        checkbox.setChecked(is_read)
        checkbox.stateChanged.connect(lambda state, b=book: self._on_read_toggled(b, state))
        row.addWidget(checkbox)

        c = colors()
        btn = QPushButton(book)
        btn.setFlat(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(_read_style(c) if is_read else _unread_style(c))
        btn.clicked.connect(lambda _, b=book: self.bookSelected.emit(b))
        self._book_buttons[book] = btn

        row.addWidget(btn)
        row.addStretch(1)
        return row

    def _on_read_toggled(self, book: str, state):
        is_read = bool(state)
        set_read(self.conn, book, is_read)
        btn = self._book_buttons.get(book)
        if btn:
            c = colors()
            btn.setStyleSheet(_read_style(c) if is_read else _unread_style(c))
        self._update_progress_label(get_all_read(self.conn))
