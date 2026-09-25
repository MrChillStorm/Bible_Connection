"""Parses the tagged verse text from the scrollmapper OSIS-JSON KJV
source into plain text, 'words of Christ' (red-letter) character spans,
translator's marginal notes, and per-word Strong's-number spans, by
walking the inline XML-ish markup:

  <w lemma="strong:H0430">God</w>      -- word, tagged with Strong's number(s) (kept, span recorded)
  <q marker="" who="Jesus">...</q>     -- Jesus's spoken words (kept, span recorded)
  <note type="study"><catchWord>phrase</catchWord>: Heb. <rdg>...</rdg></note>
                                        -- translator's note; extracted as (catchword, note text),
                                           doesn't appear in the plain text itself
  <divineName>, <foreign>, <transChange>, <title>, <inscription>
                                        -- kept, tags stripped
  <div/>, <chapter/>, <milestone/>     -- structural markers, no text content

Every other tag is treated as harmless markup: stripped, inner text kept.
"""
import html
import re

_TOKEN_RE = re.compile(r"<(/?)(\w+)([^>]*?)(/?)>|([^<]+)")
_WHO_RE = re.compile(r'who="([^"]*)"')
_STRONG_RE = re.compile(r"strong:([HG]\d+)")
# block-level elements: the source doesn't put a literal space between
# these and adjacent text (e.g. a psalm's <title>...</title> runs
# straight into verse 1's text), but a word boundary belongs there
_BLOCK_BOUNDARY_TAGS = {"title", "div", "milestone", "chapter"}


def _emit(text: str, target: list[str]) -> None:
    for ch in html.unescape(text):
        if ch.isspace():
            if target and target[-1] == " ":
                continue
            target.append(" ")
        else:
            target.append(ch)


def parse_verse_text(raw: str):
    """Returns (plain_text, words_of_christ_spans, notes, word_spans).
    notes is a list of (catchword, note_text) pairs, in verse order.
    word_spans is a list of (start, end, [strong_numbers]) per tagged word."""
    buf: list[str] = []
    woc_spans: list[tuple[int, int]] = []
    jesus_depth = 0
    jesus_start = None

    word_start = None
    word_strongs: list[str] = []
    word_spans: list[tuple[int, int, list[str]]] = []

    note_active = False
    note_catchword_active = False
    note_catchword_buf: list[str] = []
    note_body_buf: list[str] = []
    notes: list[tuple[str, str]] = []

    for m in _TOKEN_RE.finditer(raw):
        closing, tag, attrs, self_closing, text = m.groups()

        if text is not None:
            if note_active:
                _emit(text, note_catchword_buf if note_catchword_active else note_body_buf)
            else:
                _emit(text, buf)
            continue

        if closing:
            if tag == "note" and note_active:
                note_active = False
                catchword = "".join(note_catchword_buf).strip()
                note_text = "".join(note_body_buf).strip().lstrip(": ").strip()
                if catchword or note_text:
                    notes.append((catchword, note_text))
                note_catchword_buf, note_body_buf = [], []
            elif tag == "catchWord" and note_active:
                note_catchword_active = False
            elif tag == "q" and jesus_depth > 0:
                jesus_depth -= 1
                if jesus_depth == 0 and jesus_start is not None:
                    end = len(buf)
                    while end > jesus_start and buf[end - 1] == " ":
                        end -= 1
                    if end > jesus_start:
                        woc_spans.append((jesus_start, end))
                    jesus_start = None
            elif tag == "w" and word_start is not None:
                end = len(buf)
                while end > word_start and buf[end - 1] == " ":
                    end -= 1
                if end > word_start and word_strongs:
                    word_spans.append((word_start, end, word_strongs))
                word_start, word_strongs = None, []
            if tag in _BLOCK_BOUNDARY_TAGS and not note_active:
                _emit(" ", buf)
            continue

        # opening or self-closing tag
        if tag == "note" and not self_closing:
            note_active = True
            note_catchword_active = False
            note_catchword_buf, note_body_buf = [], []
            continue
        if note_active:
            if tag == "catchWord" and not self_closing:
                note_catchword_active = True
            continue  # any other tag inside a note: pure markup, no state change

        if tag in _BLOCK_BOUNDARY_TAGS:
            _emit(" ", buf)
        if tag == "q" and not self_closing:
            who = _WHO_RE.search(attrs)
            if who and who.group(1) == "Jesus":
                if jesus_depth == 0:
                    jesus_start = len(buf)
                jesus_depth += 1
        elif tag == "w" and not self_closing:
            word_start = len(buf)
            word_strongs = _STRONG_RE.findall(attrs)
        # everything else: pure markup, nothing to do

    full = "".join(buf)
    stripped = full.strip()
    lead_trim = len(full) - len(full.lstrip())

    def adjust(start: int, end: int):
        s, e = start - lead_trim, end - lead_trim
        s = max(0, min(s, len(stripped)))
        e = max(0, min(e, len(stripped)))
        return (s, e) if e > s else None

    adjusted_woc = [a for a in (adjust(s, e) for s, e in woc_spans) if a]
    adjusted_words = []
    for s, e, strongs in word_spans:
        a = adjust(s, e)
        if a:
            adjusted_words.append((a[0], a[1], strongs))

    return stripped, adjusted_woc, notes, adjusted_words
