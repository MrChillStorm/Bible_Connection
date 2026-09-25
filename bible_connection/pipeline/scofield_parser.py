"""Parses one book's Scofield Reference Notes page (rendered HTML from
Wikisource, transclusion already resolved) into (chapter, verse,
catchword, note_text) tuples.

Structure: 'CHAPTER N' headings (h2/h3) set the current chapter; 'Verse
N' headings open a verse's notes. Within a verse's content, each
top-level <p> whose first child is a <b> tag starts a new
catchword-anchored note; a <ul> list or a plain <p> continues the
current note. A 'Verse N' section with no leading-<b> paragraph at all
produces one note with an empty catchword (anchored at verse-end, like
unresolved footnotes).

Traversal is a single flat pass over every h2/h3/h4/p/ul tag in true
document order (via find_all, which recurses regardless of nesting) --
deliberately NOT a sibling walk from each heading. The source
transcludes the original scanned book page-by-page, and each physical
page can land in its own wrapper element, so a heading and the content
that logically follows it are not always siblings in the DOM.
"""
import re

from bs4 import BeautifulSoup

_CHAPTER_RE = re.compile(r"^CHAPTER\s+(\d+)", re.I)
_VERSE_RE = re.compile(r"^Verse\s+(\d+)", re.I)


def _first_real_child(tag):
    for child in tag.children:
        if getattr(child, "name", None):
            return child
        if str(child).strip():
            return child
    return None


def parse_book_notes(html: str) -> list[tuple[int, int, str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[tuple[int, int, str, str]] = []

    current_chapter = 1
    current_verse = None
    notes_for_verse: list[list] = []  # [catchword, [text parts]]

    def flush_verse():
        if current_verse is None:
            return
        for catchword, parts in notes_for_verse:
            note_text = " ".join(p for p in parts if p).strip()
            if catchword or note_text:
                results.append((current_chapter, current_verse, catchword, note_text))
        notes_for_verse.clear()

    for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "ul"]):
        if tag.name in ("h1", "h2", "h3", "h4"):
            text = tag.get_text(strip=True)

            m_chapter = _CHAPTER_RE.match(text)
            if m_chapter:
                flush_verse()
                current_chapter = int(m_chapter.group(1))
                current_verse = None
                continue

            m_verse = _VERSE_RE.match(text)
            if m_verse:
                flush_verse()
                current_verse = int(m_verse.group(1))
                continue

            # some other heading (e.g. a book/section introduction) --
            # stop attributing content to whatever verse was open
            flush_verse()
            current_verse = None
            continue

        if current_verse is None:
            continue  # content before the first 'Verse N' heading (intro material)

        first = _first_real_child(tag) if tag.name == "p" else None
        starts_new_note = tag.name == "p" and getattr(first, "name", None) == "b"

        if starts_new_note:
            catchword = first.get_text(strip=True)
            full_text = tag.get_text(" ", strip=True)
            rest = full_text[len(catchword):].strip() if full_text.startswith(catchword) else full_text
            notes_for_verse.append([catchword, [rest] if rest else []])
        else:
            part = tag.get_text(" ", strip=True)
            if not part:
                continue
            if not notes_for_verse:
                notes_for_verse.append(["", [part]])
            else:
                notes_for_verse[-1][1].append(part)

    flush_verse()
    return results
