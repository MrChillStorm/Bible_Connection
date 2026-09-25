"""Small clickable card widgets shared by the connections pane and the
search panel."""
import re
from functools import lru_cache

from PySide6.QtCore import QByteArray, QSize, QTimer, Qt, Signal
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from bible_connection.ui import fonts
from bible_connection.ui.theme import colors

_BR_TAG_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_ANY_TAG_RE = re.compile(r"<[^>]+>")


def _plain_text(html: str, limit: int | None = None) -> str:
    """Strips markup for a plain-text preview or clipboard copy. Some
    Strong's definitions (STEPBible's Abbott-Smith/BDB lexicon text)
    contain <b>/<i>/<BR /> formatting -- fine for a QLabel that renders
    it as rich text, but truncating that raw HTML at a fixed character
    count (as the compact card preview does) can cut a tag in half."""
    text = _BR_TAG_RE.sub(" ", html)
    text = _ANY_TAG_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    if limit is not None and len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + "…"
    return text

# The familiar two-overlapping-rectangles "copy" icon (as seen on a
# markdown code block) and the checkmark it swaps to after a successful
# copy -- rendered from inline SVG rather than a Unicode glyph, since
# glyph coverage/rendering for something like U+2398 varies by font.
_COPY_SVG_BODY = (
    '<rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>'
    '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>'
)
_CHECK_SVG_BODY = '<polyline points="20 6 9 17 4 12"></polyline>'


@lru_cache(maxsize=None)
def _svg_icon(body: str, color: str, size: int = 16) -> QIcon:
    # Every card in a given theme uses the same two icons (grey copy,
    # green check) -- cached so a concordance page with thousands of
    # cards doesn't re-render the same SVG thousands of times. Safe to
    # cache for the process lifetime since the theme is only read once
    # at launch (see theme.py).
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
        f"{body}</svg>"
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def _make_copy_button(text: str) -> QPushButton:
    """A small icon-only copy button, matching the copy icon on a
    markdown code block (swaps to a checkmark briefly after copying).
    A child widget's own click handling keeps this from also
    triggering a containing card's mousePressEvent (and thus
    navigating) -- Qt routes the press to whichever widget is under
    the cursor, and the button consumes it before it would reach a
    parent's override."""
    c = colors()
    copy_icon = _svg_icon(_COPY_SVG_BODY, c["muted"])
    check_icon = _svg_icon(_CHECK_SVG_BODY, c["scofield"])

    btn = QPushButton()
    btn.setIcon(copy_icon)
    btn.setIconSize(QSize(14, 14))
    btn.setFixedSize(24, 24)
    btn.setToolTip("Copy")
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{ border: none; background: transparent; border-radius: 4px; }}"
        f"QPushButton:hover {{ background: {c['hover_bg']}; }}"
    )

    def revert():
        btn.setIcon(copy_icon)
        btn.setToolTip("Copy")

    def do_copy():
        QApplication.clipboard().setText(text)
        btn.setIcon(check_icon)
        btn.setToolTip("Copied")
        QTimer.singleShot(1200, revert)

    btn.clicked.connect(do_copy)
    return btn


class ClickableCard(QFrame):
    clicked = Signal()
    hoverChanged = Signal(bool)

    def __init__(self, accent_color: str, parent=None):
        super().__init__(parent)
        c = colors()
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            f"""
            ClickableCard {{
                background: {c['surface']};
                border: 1px solid {c['border']};
                border-left: 4px solid {accent_color};
                border-radius: 8px;
            }}
            ClickableCard:hover {{ background: {c['hover_bg']}; }}
            """
        )

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self.hoverChanged.emit(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hoverChanged.emit(False)
        super().leaveEvent(event)

    def _make_copy_button(self, text: str) -> QPushButton:
        return _make_copy_button(text)


class ConnectionCard(ClickableCard):
    def __init__(self, ref_text: str, weight_text: str, source_text: str, body_text: str, accent_color: str, parent=None):
        super().__init__(accent_color, parent)
        c = colors()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)

        header = QHBoxLayout()
        ref_label = QLabel(f"<b>{ref_text}</b>")
        ref_label.setStyleSheet(f"color:{c['ink']};")
        weight_label = QLabel(weight_text)
        weight_label.setStyleSheet(f"color:{c['muted']}; font-size:{fonts.px(13)}px;")
        header.addWidget(ref_label)
        header.addStretch(1)
        header.addWidget(weight_label)
        header.addWidget(self._make_copy_button(f"{ref_text} — {body_text}"))
        layout.addLayout(header)

        if source_text:
            source_label = QLabel(source_text)
            source_label.setStyleSheet(f"color:{c['muted']}; font-size:{fonts.px(12)}px;")
            layout.addWidget(source_label)

        body = QLabel(body_text)
        body.setWordWrap(True)
        body.setStyleSheet(f"font-size:{fonts.px(15)}px; color:{c['ink']};")
        layout.addWidget(body)


class SearchHitCard(ClickableCard):
    def __init__(self, ref_text: str, body_text: str, parent=None):
        c = colors()
        super().__init__(c["curated"], parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        header = QHBoxLayout()
        ref_label = QLabel(f"<b>{ref_text}</b>")
        ref_label.setStyleSheet(f"color:{c['ink']};")
        header.addWidget(ref_label)
        header.addStretch(1)
        header.addWidget(self._make_copy_button(f"{ref_text} — {body_text}"))
        layout.addLayout(header)

        body = QLabel(body_text)
        body.setWordWrap(True)
        body.setStyleSheet(f"font-size:{fonts.px(14)}px; color:{c['ink']};")
        layout.addWidget(body)


class StrongsCard(ClickableCard):
    def __init__(self, row, accent_color: str, count_suffix: str = "in view", parent=None):
        c = colors()
        super().__init__(accent_color, parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)

        full_gloss = row["definition"] or row["kjv_translations"] or ""

        header = QHBoxLayout()
        word_label = QLabel(f"<b>{row['original_word']}</b>  <i>{row['transliteration']}</i>")
        word_label.setStyleSheet(f"color:{c['ink']}; font-size:{fonts.px(16)}px;")
        number_label = QLabel(row["strong_number"])
        number_label.setStyleSheet(f"color:{c['muted']}; font-size:{fonts.px(13)}px;")
        header.addWidget(word_label)
        header.addStretch(1)
        header.addWidget(number_label)
        copy_text = (
            f"{row['original_word']} ({row['transliteration']}) {row['strong_number']} "
            f"— {_plain_text(full_gloss)}"
        )
        header.addWidget(self._make_copy_button(copy_text))
        layout.addLayout(header)

        gloss_label = QLabel(_plain_text(full_gloss, limit=110))
        gloss_label.setWordWrap(True)
        gloss_label.setStyleSheet(f"font-size:{fonts.px(14)}px; color:{c['ink']};")
        layout.addWidget(gloss_label)

        if row["occurrence_count"] > 1:
            count_label = QLabel(f"{row['occurrence_count']}× {count_suffix}")
            count_label.setStyleSheet(f"color:{c['muted']}; font-size:{fonts.px(12)}px;")
            layout.addWidget(count_label)


class _ClickableVerseLabel(QLabel):
    clicked = Signal()

    def __init__(self, ref_text: str, body_text: str, parent=None):
        c = colors()
        super().__init__(
            f'<span style="font-weight:bold; color:{c["ink"]};">{ref_text}</span><br>'
            f'<span style="color:{c["ink"]};">{body_text}</span>',
            parent,
        )
        self.setWordWrap(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            f"QLabel {{ padding: 5px; border-radius: 6px; }}"
            f"QLabel:hover {{ background: {c['hover_bg']}; }}"
        )

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class DiscoveryCard(QFrame):
    """Pairs two verses connected only by ML-found ('semantic')
    similarity, with no curated cross-reference behind them -- for
    browsing for something unexpected, independent of whichever verse
    is currently being read. Each verse is independently clickable
    (there's no single "the" destination the way a normal connection
    card has one), so this isn't built on ClickableCard."""
    verseASelected = Signal(str, int, int)
    verseBSelected = Signal(str, int, int)

    def __init__(self, row, accent_color: str, parent=None):
        super().__init__(parent)
        c = colors()
        self.setStyleSheet(
            f"""
            DiscoveryCard {{
                background: {c['surface']};
                border: 1px solid {c['border']};
                border-left: 4px solid {accent_color};
                border-radius: 8px;
            }}
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)

        header = QHBoxLayout()
        tag = QLabel("ML-DISCOVERED CONNECTION")
        tag.setStyleSheet(f"color:{accent_color}; font-size:{fonts.px(12)}px; font-weight:bold;")
        weight_label = QLabel(f"{row['weight']:.3f}")
        weight_label.setStyleSheet(f"color:{c['muted']}; font-size:{fonts.px(13)}px;")
        header.addWidget(tag)
        header.addStretch(1)
        header.addWidget(weight_label)
        copy_text = (
            f"{row['book']} {row['chapter']}:{row['verse']} — {row['text']}"
            f"  ⟷  {row['b_book']} {row['b_chapter']}:{row['b_verse']} — {row['b_text']}"
        )
        header.addWidget(_make_copy_button(copy_text))
        layout.addLayout(header)

        self.verse_a = _ClickableVerseLabel(f"{row['book']} {row['chapter']}:{row['verse']}", row["text"])
        self.verse_a.clicked.connect(
            lambda: self.verseASelected.emit(row["book"], row["chapter"], row["verse"])
        )
        layout.addWidget(self.verse_a)

        connector = QLabel("⟷")
        connector.setAlignment(Qt.AlignmentFlag.AlignCenter)
        connector.setStyleSheet(f"color:{c['muted']}; font-size:{fonts.px(15)}px;")
        layout.addWidget(connector)

        self.verse_b = _ClickableVerseLabel(f"{row['b_book']} {row['b_chapter']}:{row['b_verse']}", row["b_text"])
        self.verse_b.clicked.connect(
            lambda: self.verseBSelected.emit(row["b_book"], row["b_chapter"], row["b_verse"])
        )
        layout.addWidget(self.verse_b)
