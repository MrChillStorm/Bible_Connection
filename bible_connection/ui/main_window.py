from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow, QPushButton, QSplitter, QStackedWidget,
    QTabWidget, QVBoxLayout, QWidget,
)

from bible_connection.core.db import get_connection, get_user_connection, init_schema, init_user_schema
from bible_connection.core.reading_state import get_position, set_font_scale, set_last_book, set_position
from bible_connection.ui import fonts
from bible_connection.ui.theme import build_app_stylesheet, colors

from bible_connection.ui.connections_pane import ConnectionsPane
from bible_connection.ui.discovery_pane import DiscoveryPane
from bible_connection.ui.library_page import LibraryPage
from bible_connection.ui.reading_pane import ReadingPane
from bible_connection.ui.search_panel import SearchPanel
from bible_connection.ui.strongs_pane import StrongsPane
from bible_connection.ui.word_detail_page import WordDetailPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bible Connection")
        self.resize(1400, 900)

        self.conn = get_connection()
        init_schema(self.conn)
        self.user_conn = get_user_connection()
        init_user_schema(self.user_conn, self.conn)

        self.library_page = LibraryPage(self.user_conn)
        self.library_page.bookSelected.connect(self._open_book)

        self.reading_pane = ReadingPane(self.conn, self.user_conn)
        self.connections_pane = ConnectionsPane(self.conn)
        self.search_panel = SearchPanel(self.conn)
        self.strongs_pane = StrongsPane(self.conn)
        self.word_detail_page = WordDetailPage(self.conn)
        self.discovery_pane = DiscoveryPane(self.conn)

        tabs = QTabWidget()
        tabs.addTab(self.connections_pane, "Connections")
        tabs.addTab(self.strongs_pane, "Strong's")
        tabs.addTab(self.search_panel, "Search")
        tabs.addTab(self.discovery_pane, "Discover")

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.reading_pane)
        splitter.addWidget(tabs)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        reader_page = QWidget()
        reader_layout = QVBoxLayout(reader_page)
        reader_layout.setContentsMargins(8, 8, 8, 8)

        top_bar = QHBoxLayout()
        library_btn = QPushButton("☰ Library")
        library_btn.clicked.connect(self._show_library)
        top_bar.addWidget(library_btn)
        self.back_btn = QPushButton("← Back to reading")
        self.back_btn.clicked.connect(self._back_to_previous_position)
        self.back_btn.hide()
        top_bar.addWidget(self.back_btn)
        top_bar.addStretch(1)

        shrink_btn = QPushButton("A-")
        shrink_btn.setFixedWidth(36)
        shrink_btn.clicked.connect(lambda: self._change_font_scale(-fonts.SCALE_STEP))
        self.font_scale_label = QLabel()
        self.font_scale_label.setFixedWidth(44)
        self.font_scale_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grow_btn = QPushButton("A+")
        grow_btn.setFixedWidth(36)
        grow_btn.clicked.connect(lambda: self._change_font_scale(fonts.SCALE_STEP))
        top_bar.addWidget(shrink_btn)
        top_bar.addWidget(self.font_scale_label)
        top_bar.addWidget(grow_btn)
        self._update_font_scale_label()

        reader_layout.addLayout(top_bar)

        self._return_point = None  # (book, chapter, top_verse) to jump back to
        reader_layout.addWidget(splitter)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.library_page)      # index 0: start page
        self.stack.addWidget(reader_page)            # index 1: reader
        self.stack.addWidget(self.word_detail_page)  # index 2: Strong's word detail
        self.setCentralWidget(self.stack)

        self.reading_pane.visibleVersesChanged.connect(self.connections_pane.update_for_verses)
        self.reading_pane.visibleVersesChanged.connect(self.strongs_pane.update_for_verses)
        self.reading_pane.positionChanged.connect(self._on_position_changed)
        self.connections_pane.verseSelected.connect(self._navigate_to)
        self.connections_pane.verseHoverChanged.connect(self.reading_pane.set_hover_highlight)
        self.search_panel.verseSelected.connect(self._navigate_to)
        self.strongs_pane.wordHoverChanged.connect(self.reading_pane.set_word_highlight)
        self.strongs_pane.wordSelected.connect(self._open_word_detail)
        self.word_detail_page.backRequested.connect(self._back_to_reading)
        self.word_detail_page.verseSelected.connect(self._navigate_to)
        self.discovery_pane.verseSelected.connect(self._navigate_to)

        self.stack.setCurrentIndex(0)

    def _open_book(self, book: str):
        # deliberately choosing a book from the library makes any pending
        # "back to previous" target stale
        self._return_point = None
        self.back_btn.hide()
        # switch pages *before* loading -- the reading pane needs real
        # layout geometry (only available once it's the visible stack
        # page) for its deferred scroll-to-verse to land correctly
        self.stack.setCurrentIndex(1)
        pos = get_position(self.user_conn, book)
        chapter, verse = pos if pos else (1, 1)
        self.reading_pane.load_position(book, chapter, verse)

    def _show_library(self):
        self.stack.setCurrentIndex(0)

    def _navigate_to(self, book: str, chapter: int, verse: int):
        # anchor to the chapter you were reading *before this whole chain
        # of jumps started* -- only set it once, on the first jump; later
        # jumps (another connection, a different tab, etc.) must not
        # overwrite it, so "back" always returns to that same chapter
        # no matter how many links you click in between
        if self._return_point is None and self.reading_pane.book is not None:
            current_top = self.reading_pane.true_top_verse() or 1
            self._return_point = (self.reading_pane.book, self.reading_pane.chapter, current_top)
            self.back_btn.show()
        self.stack.setCurrentIndex(1)
        self.reading_pane.load_position(book, chapter, verse)

    def _back_to_previous_position(self):
        if self._return_point is None:
            return
        book, chapter, verse = self._return_point
        self._return_point = None
        self.back_btn.hide()
        self.stack.setCurrentIndex(1)
        self.reading_pane.load_position(book, chapter, verse)

    def _on_position_changed(self, book: str, chapter: int, top_verse: int):
        set_position(self.user_conn, book, chapter, top_verse)
        set_last_book(self.user_conn, book)

    def _open_word_detail(self, strong_number: str):
        self.word_detail_page.show_word(strong_number)
        self.stack.setCurrentIndex(2)

    def _back_to_reading(self):
        # the reader page's own state was never touched, so switching
        # back to it lands exactly where the reader was left
        self.stack.setCurrentIndex(1)

    def _update_font_scale_label(self):
        self.font_scale_label.setText(f"{round(fonts.get_scale() * 100)}%")

    def _change_font_scale(self, delta: float):
        fonts.set_scale(fonts.get_scale() + delta)
        set_font_scale(self.user_conn, fonts.get_scale())
        self._update_font_scale_label()

        # the base/inherited font (buttons, tabs, combo boxes, the
        # Strong's concordance list) updates just by re-applying the
        # app stylesheet; every explicit per-widget font-size override
        # needs its own refresh_fonts() call, since Qt won't touch a
        # widget's own stylesheet just because a parent one changed
        QApplication.instance().setStyleSheet(build_app_stylesheet(colors()))

        self.library_page.refresh_fonts()
        self.reading_pane.refresh_fonts()
        self.connections_pane.refresh_fonts()
        self.strongs_pane.refresh_fonts()
        self.search_panel.refresh_fonts()
        self.discovery_pane.refresh_fonts()
        self.word_detail_page.refresh_fonts()
