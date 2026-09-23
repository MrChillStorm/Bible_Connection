"""The chapter reader: book/chapter navigation + a scrollable chapter
view that reports which verses are currently visible (debounced), so the
connections pane can update live as the user scrolls."""
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
)

import fonts
from books import BOOK_ORDER
from chapters import chapter_count, get_chapter
from footnotes import get_footnotes_for_chapter
from reading_state import get_position
from scofield import get_scofield_notes_for_chapter
from strongs import get_word_spans
from theme import colors

DEBOUNCE_MS = 200
NOTE_PLACEHOLDER = "Hover a small lettered marker for a translator's note, or hover any verse for its Scofield study note (when available)."

# Same pixel size and weight as the verse-number superscript (which is
# known legible): an explicit small size compounds with Qt's own
# superscript shrink and renders as only a few pixels tall. Uppercase
# letters, since lowercase only fills x-height (~half a digit's
# cap-height) and looks much smaller than it measures.
_MARKER_STYLE = "text-decoration:none; color:{color}; font-size:{size}px; vertical-align:super; font-weight:bold;"


def _footnote_marker_label(fn_row) -> str:
    return chr(ord("A") + (fn_row["order_in_verse"] % 26))


def _marker_html(href: str, label: str, color: str) -> str:
    style = _MARKER_STYLE.format(color=color, size=fonts.px(18))
    return f'<a href="{href}" style="{style}">{label}</a>'


def _verse_body_html(text: str, woc_spans_json, footnote_rows, red: str, footnote_color: str):
    """Renders verse text with 'words of Christ' spans in red and small
    lettered translator's-note markers, all HTML-escaped. (Scofield
    study notes are looked up per-verse on hover instead of getting
    their own inline marker -- simpler, and avoids every marker type
    needing to agree on exactly how many characters it inserts, which
    the highlight-offset math downstream depends on getting right.)
    Returns (html, marker_widths) -- marker_widths is a sorted
    [(plain-text offset, char width)] list needed later to translate a
    plain-text character span into a document cursor position, since
    each marker inserts characters absent from the original text."""
    spans = json.loads(woc_spans_json) if woc_spans_json else []

    cut_points = {0, len(text)}
    for start, end in spans:
        cut_points.add(start)
        cut_points.add(end)
    markers_by_pos: dict[int, list] = {}
    marker_width_by_pos: dict[int, int] = {}
    for fn in footnote_rows:
        pos = min(fn["anchor_pos"], len(text))
        cut_points.add(pos)
        label = _footnote_marker_label(fn)
        markers_by_pos.setdefault(pos, []).append((label, fn["id"]))
        marker_width_by_pos[pos] = marker_width_by_pos.get(pos, 0) + len(label)
    cuts = sorted(cut_points)

    def in_red(pos: int) -> bool:
        return any(s <= pos < e for s, e in spans)

    parts = []
    for i in range(len(cuts) - 1):
        seg_start, seg_end = cuts[i], cuts[i + 1]
        for label, row_id in markers_by_pos.get(seg_start, []):
            parts.append(_marker_html(f"fn:{row_id}", label, footnote_color))
        if seg_start < seg_end:
            segment = html.escape(text[seg_start:seg_end])
            parts.append(f'<span style="color:{red};">{segment}</span>' if in_red(seg_start) else segment)
    for label, row_id in markers_by_pos.get(len(text), []):
        parts.append(_marker_html(f"fn:{row_id}", label, footnote_color))

    return "".join(parts), sorted(marker_width_by_pos.items())


class ReadingPane(QWidget):
    visibleVersesChanged = Signal(list)       # list[int] of verse ids currently visible
    positionChanged = Signal(str, int, int)   # book, chapter, top-visible verse number

    def __init__(self, conn, user_conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.user_conn = user_conn  # only for the book-combo's "resume where you left off" lookup
        self.book = None
        self.chapter = None
        self._block_verse_ids: list[int] = []
        self._block_verse_nums: list[int] = []
        self._loading = False
        self._previewing = False
        self._preview_top_verse = None  # top verse to restore to once hover ends
        self._footnote_lookup: dict[str, dict] = {}
        self._scofield_lookup: dict[int, list] = {}  # verse_id -> [{"catchword", "note"}, ...]
        self._current_hover_display = None  # ("fn", anchor_id) or ("sc", verse_id) or None
        self._verse_marker_positions: dict[int, list] = {}
        self._preview_selections: list = []
        self._word_selections: list = []

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self._emit_visible_range)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        self.book_combo = QComboBox()
        self.book_combo.addItems(BOOK_ORDER)
        self.book_combo.currentTextChanged.connect(self._on_book_selected)

        self.chapter_combo = QComboBox()
        self.chapter_combo.currentIndexChanged.connect(self._on_chapter_selected)

        self.prev_btn = QPushButton("◀ Prev")
        self.prev_btn.clicked.connect(self.go_prev_chapter)
        self.next_btn = QPushButton("Next ▶")
        self.next_btn.clicked.connect(self.go_next_chapter)

        toolbar.addWidget(self.book_combo)
        toolbar.addWidget(self.chapter_combo)
        toolbar.addWidget(self.prev_btn)
        toolbar.addWidget(self.next_btn)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        c = colors()
        self.browser.setStyleSheet(
            f"QTextBrowser {{ background: {c['surface']}; border: 1px solid {c['border']}; "
            f"border-radius: 8px; padding: 8px; }}"
        )
        self.browser.verticalScrollBar().valueChanged.connect(self._schedule_visible_update)
        self.browser.viewport().setMouseTracking(True)
        self.browser.viewport().installEventFilter(self)
        layout.addWidget(self.browser)

        self.note_panel = QLabel(NOTE_PLACEHOLDER)
        self.note_panel.setWordWrap(True)
        self.note_panel.setMinimumHeight(90)
        self._style_note_panel(hovering=False)
        layout.addWidget(self.note_panel)

    # -- note hover: a footnote's lettered marker takes priority (small,
    # deliberate target); otherwise, hovering anywhere on a verse shows
    # its Scofield study note(s), if any -- no inline marker needed. --

    def _style_note_panel(self, hovering: bool):
        c = colors()
        style = "font-style:normal;" if hovering else "font-style:italic;"
        self.note_panel.setStyleSheet(
            f"color:{c['ink'] if hovering else c['muted']}; font-size:{fonts.px(14)}px; {style} "
            f"padding:6px 4px; border-top:1px solid {c['border']}; margin-top:4px;"
        )

    def refresh_fonts(self):
        """Re-renders the current chapter (if any) at the new font
        scale, restoring approximately the same scroll position."""
        self._style_note_panel(hovering=self._current_hover_display is not None)
        if self.book is not None:
            self._load_chapter(self.book, self.chapter, self.true_top_verse() or 1)

    def _verse_id_at(self, pos):
        cursor = self.browser.cursorForPosition(pos)
        block_index = cursor.blockNumber()
        if 0 <= block_index < len(self._block_verse_ids):
            return self._block_verse_ids[block_index]
        return None

    def eventFilter(self, obj, event):
        if obj is self.browser.viewport():
            if event.type() == QEvent.Type.MouseMove:
                anchor = self.browser.anchorAt(event.pos())
                if anchor.startswith("fn:"):
                    display = ("fn", anchor[3:])
                else:
                    verse_id = self._verse_id_at(event.pos())
                    display = ("sc", verse_id) if verse_id in self._scofield_lookup else None
                self._update_note_hover(display)
            elif event.type() == QEvent.Type.Leave:
                self._update_note_hover(None)
        return super().eventFilter(obj, event)

    def _update_note_hover(self, display):
        if display == self._current_hover_display:
            return
        self._current_hover_display = display

        if display is not None:
            kind, key = display
            if kind == "fn":
                data = self._footnote_lookup.get(key)
                if data:
                    self._show_note(data["ref"], "Translator's note", colors()["semantic"], [(data["catchword"], data["note"])])
                    return
            else:  # "sc"
                notes = self._scofield_lookup.get(key)
                if notes:
                    ref = notes[0]["ref"]
                    self._show_note(ref, "Scofield", colors()["scofield"], [(n["catchword"], n["note"]) for n in notes])
                    return

        self._style_note_panel(hovering=False)
        self.note_panel.setText(NOTE_PLACEHOLDER)

    def _show_note(self, ref: str, source_label: str, label_color: str, catchword_notes: list[tuple[str, str]]):
        self._style_note_panel(hovering=True)
        parts = [
            f"<i>{html.escape(cw)}</i>: {html.escape(note)}" if cw else html.escape(note)
            for cw, note in catchword_notes
        ]
        self.note_panel.setText(
            f"<b>{ref}</b> <span style=\"color:{label_color}; font-size:{fonts.px(12)}px; font-weight:bold;\">({source_label})</span> — "
            + " &nbsp;·&nbsp; ".join(parts)
        )

    # -- public navigation API --

    def load_position(self, book: str, chapter: int, scroll_to_verse: int = 1):
        self._loading = True
        try:
            idx = self.book_combo.findText(book)
            if idx >= 0:
                self.book_combo.setCurrentIndex(idx)
            self._populate_chapters(book)
            cidx = self.chapter_combo.findText(str(chapter))
            if cidx >= 0:
                self.chapter_combo.setCurrentIndex(cidx)
        finally:
            self._loading = False
        self._load_chapter(book, chapter, scroll_to_verse)

    def go_prev_chapter(self):
        if self.chapter and self.chapter > 1:
            self._load_chapter(self.book, self.chapter - 1, 1)
            self._sync_combos()
        else:
            idx = BOOK_ORDER.index(self.book)
            if idx > 0:
                prev_book = BOOK_ORDER[idx - 1]
                self.load_position(prev_book, chapter_count(self.conn, prev_book), 1)

    def go_next_chapter(self):
        n = chapter_count(self.conn, self.book)
        if self.chapter and self.chapter < n:
            self._load_chapter(self.book, self.chapter + 1, 1)
            self._sync_combos()
        else:
            idx = BOOK_ORDER.index(self.book)
            if idx < len(BOOK_ORDER) - 1:
                self.load_position(BOOK_ORDER[idx + 1], 1, 1)

    # -- combo box wiring --

    def _populate_chapters(self, book: str):
        self.chapter_combo.blockSignals(True)
        self.chapter_combo.clear()
        n = chapter_count(self.conn, book)
        self.chapter_combo.addItems([str(i) for i in range(1, n + 1)])
        self.chapter_combo.blockSignals(False)

    def _sync_combos(self):
        self._loading = True
        try:
            bidx = self.book_combo.findText(self.book)
            if bidx >= 0:
                self.book_combo.setCurrentIndex(bidx)
            self._populate_chapters(self.book)
            cidx = self.chapter_combo.findText(str(self.chapter))
            if cidx >= 0:
                self.chapter_combo.setCurrentIndex(cidx)
        finally:
            self._loading = False

    def _on_book_selected(self, book: str):
        if self._loading or not book:
            return
        pos = get_position(self.user_conn, book)
        chapter, verse = pos if pos else (1, 1)
        self.load_position(book, chapter, verse)

    def _on_chapter_selected(self, index: int):
        if self._loading or index < 0:
            return
        self._load_chapter(self.book_combo.currentText(), index + 1, 1)

    # -- rendering --

    def _load_chapter(self, book: str, chapter: int, scroll_to_verse):
        rows = get_chapter(self.conn, book, chapter)
        footnotes_by_verse = get_footnotes_for_chapter(self.conn, book, chapter)
        scofield_by_verse = get_scofield_notes_for_chapter(self.conn, book, chapter)
        self.book = book
        self.chapter = chapter
        self._block_verse_ids = []
        self._block_verse_nums = []
        self._previewing = False
        self._preview_top_verse = None
        self._footnote_lookup = {}
        self._scofield_lookup = {}
        self._current_hover_display = None
        self._verse_marker_positions = {}
        self._preview_selections = []
        self._word_selections = []
        c = colors()

        html_parts = []
        for row in rows:
            self._block_verse_ids.append(row["id"])
            self._block_verse_nums.append(row["verse"])
            ref = f"{book} {chapter}:{row['verse']}"
            fn_rows = footnotes_by_verse.get(row["id"], [])
            for fn in fn_rows:
                self._footnote_lookup[str(fn["id"])] = {"ref": ref, "catchword": fn["catchword"], "note": fn["note"]}
            sc_rows = scofield_by_verse.get(row["id"], [])
            if sc_rows:
                self._scofield_lookup[row["id"]] = [
                    {"ref": ref, "catchword": sc["catchword"], "note": sc["note"]} for sc in sc_rows
                ]

            body, marker_positions = _verse_body_html(
                row["text"], row["woc_spans"], fn_rows, c["words_of_christ"], c["semantic"]
            )
            self._verse_marker_positions[row["id"]] = marker_positions
            html_parts.append(
                f'<p style="margin:0 0 12px 0; line-height:1.6; font-size:{fonts.px(18)}px; color:{c["ink"]};">'
                f'<span style="color:{c["curated"]}; font-weight:bold; font-size:{fonts.px(18)}px; vertical-align:super;">{row["verse"]}</span>'
                f'&#160;{body}</p>'
            )
        self._apply_extra_selections()  # both layers just reset above; old cursors are now stale
        self.note_panel.setText(NOTE_PLACEHOLDER)
        self._style_note_panel(hovering=False)
        self.browser.setHtml("".join(html_parts))

        target_verse = scroll_to_verse or 1
        QTimer.singleShot(0, lambda: self._scroll_to_verse(target_verse))

    def _scroll_to_verse(self, verse_number: int):
        try:
            block_index = self._block_verse_nums.index(verse_number)
        except ValueError:
            block_index = 0
        block = self.browser.document().findBlockByNumber(block_index)
        cursor = QTextCursor(block)
        self.browser.setTextCursor(cursor)
        rect = self.browser.document().documentLayout().blockBoundingRect(block)
        self.browser.verticalScrollBar().setValue(int(rect.top()))
        QTimer.singleShot(0, self._emit_visible_range)

    # -- hover preview (driven by the connections pane) --
    # Hovering a connection card scrolls to + highlights the *source*
    # verse (the one already in this chapter that the card connects
    # from), then snaps back to where you were reading once hover ends.

    def current_top_verse(self):
        if not self._block_verse_nums:
            return None
        viewport_rect = self.browser.viewport().rect()
        top_cursor = self.browser.cursorForPosition(viewport_rect.topLeft())
        idx = max(0, min(top_cursor.blockNumber(), len(self._block_verse_nums) - 1))
        return self._block_verse_nums[idx]

    def true_top_verse(self):
        # Clicking a card fires while the mouse is still over it -- i.e.
        # still hovering, mid-preview-scroll -- so current_top_verse()
        # at that instant reports the preview's temporary position, not
        # where the user was actually reading. Callers that need "where
        # was the user really scrolled to" (e.g. capturing a return
        # point before navigating away) should use this instead.
        if self._previewing and self._preview_top_verse is not None:
            return self._preview_top_verse
        return self.current_top_verse()

    def _scroll_block_to_top(self, block_index: int):
        block = self.browser.document().findBlockByNumber(block_index)
        rect = self.browser.document().documentLayout().blockBoundingRect(block)
        self.browser.verticalScrollBar().setValue(int(rect.top()))
        return block

    def _apply_extra_selections(self):
        # Two independent highlight layers share one QTextBrowser, so
        # they're composed here rather than one calling setExtraSelections
        # directly -- otherwise whichever fires last (e.g. the connections
        # pane's routine refresh on every scroll) wipes out the other
        # (e.g. an unrelated Strong's word highlight) even though neither
        # has anything to do with the other.
        self.browser.setExtraSelections(self._preview_selections + self._word_selections)

    def set_hover_highlight(self, verse_id):
        if verse_id is None:
            self._end_preview()
            return
        if verse_id not in self._block_verse_ids:
            return

        if not self._previewing:
            self._preview_top_verse = self.current_top_verse()
            self._previewing = True

        block_index = self._block_verse_ids.index(verse_id)
        block = self._scroll_block_to_top(block_index)

        cursor = QTextCursor(block)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(colors()["highlight"]))
        selection = QTextEdit.ExtraSelection()
        selection.cursor = cursor
        selection.format = fmt
        self._preview_selections = [selection]
        self._apply_extra_selections()

    def _end_preview(self):
        self._preview_selections = []
        self._apply_extra_selections()
        if not self._previewing:
            return
        self._previewing = False
        top_verse = self._preview_top_verse
        self._preview_top_verse = None
        if top_verse is None:
            return
        try:
            block_index = self._block_verse_nums.index(top_verse)
        except ValueError:
            return
        self._scroll_block_to_top(block_index)

    # -- Strong's word highlight (driven by the Strong's pane) --
    # Unlike the connections preview, this never scrolls: the word is
    # already visible (it's only listed because it's in the visible
    # range), it just needs marking. Multiple occurrences within the
    # loaded chapter can be highlighted at once.

    def _block_local_offset(self, verse_id: int, verse_number: int, plain_pos: int, is_end: bool = False) -> int:
        # A block's rendered text is [verse-number digits][nbsp][verse
        # body], and each marker in the body inserts `width` characters
        # absent from the original plain text -- both must be summed to
        # land on the right character.
        #
        # A marker at position P renders immediately *before* the
        # original character at P. For a span's start (inclusive), a
        # marker exactly at P belongs before our first character, so it
        # counts (`<=`). For a span's end (exclusive -- "stop before
        # this position"), a marker exactly at P belongs *after* our
        # last included character, so it must NOT count, or the
        # highlight silently swallows the marker glyph itself. Getting
        # this asymmetry wrong was a real bug: every span ending right
        # at a marker came out one marker-width too long.
        prefix_len = len(str(verse_number)) + 1
        positions = self._verse_marker_positions.get(verse_id, [])
        if is_end:
            inserted_chars = sum(w for p, w in positions if p < plain_pos)
        else:
            inserted_chars = sum(w for p, w in positions if p <= plain_pos)
        return prefix_len + inserted_chars + plain_pos

    def set_word_highlight(self, strong_number):
        if strong_number is None or not self._block_verse_ids:
            self._word_selections = []
            self._apply_extra_selections()
            return

        rows = get_word_spans(self.conn, self._block_verse_ids, strong_number)
        selections = []
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(colors()["highlight"]))

        for row in rows:
            verse_id = row["verse_id"]
            if verse_id not in self._block_verse_ids:
                continue
            block_index = self._block_verse_ids.index(verse_id)
            verse_number = self._block_verse_nums[block_index]
            block_start = self.browser.document().findBlockByNumber(block_index).position()

            start = block_start + self._block_local_offset(verse_id, verse_number, row["span_start"])
            end = block_start + self._block_local_offset(verse_id, verse_number, row["span_end"], is_end=True)

            cursor = QTextCursor(self.browser.document())
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)

            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format = fmt
            selections.append(selection)

        self._word_selections = selections
        self._apply_extra_selections()

    # -- visible-range tracking --

    def _schedule_visible_update(self):
        self._debounce.start()

    def _emit_visible_range(self):
        if self._previewing or not self._block_verse_ids:
            return
        viewport_rect = self.browser.viewport().rect()
        top_cursor = self.browser.cursorForPosition(viewport_rect.topLeft())
        bottom_cursor = self.browser.cursorForPosition(viewport_rect.bottomLeft())
        top_block = max(0, min(top_cursor.blockNumber(), len(self._block_verse_ids) - 1))
        bottom_block = max(0, min(bottom_cursor.blockNumber(), len(self._block_verse_ids) - 1))

        verse_ids = self._block_verse_ids[top_block:bottom_block + 1]
        top_verse_num = self._block_verse_nums[top_block]

        self.visibleVersesChanged.emit(verse_ids)
        self.positionChanged.emit(self.book, self.chapter, top_verse_num)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._schedule_visible_update()
