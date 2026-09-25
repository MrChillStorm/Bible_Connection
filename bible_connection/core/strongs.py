"""Strong's concordance lookups: what's tagged in a set of verses, where
those tags fall (for highlighting), the dictionary entry for a number,
and every verse using a given number (concordance browsing)."""
import re
import unicodedata

from bible_connection.core.strongs_parser import normalize_strong

_STRONG_NUMBER_RE = re.compile(r"^[GgHh]\d+$")


def _fold(s: str) -> str:
    """Lowercase and strip diacritics, so a plain-ASCII search like
    'agape' matches a transliteration like 'agápē'."""
    decomposed = unicodedata.normalize("NFKD", s.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def get_words_for_verses(conn, verse_ids: list[int]):
    """Distinct Strong's-tagged words in `verse_ids`, in first-appearance
    order, each with its dictionary entry and an occurrence count."""
    if not verse_ids:
        return []
    placeholders = ",".join("?" * len(verse_ids))
    return conn.execute(
        f"""SELECT ws.strong_number, se.original_word, se.transliteration,
                   se.definition, se.kjv_translations, COUNT(*) AS occurrence_count,
                   MIN(vw.verse_id) AS first_verse_id, MIN(vw.word_order) AS first_word_order
            FROM word_strongs ws
            JOIN verse_words vw ON vw.id = ws.verse_word_id
            JOIN strongs_entries se ON se.number = ws.strong_number
            WHERE ws.verse_id IN ({placeholders})
            GROUP BY ws.strong_number
            ORDER BY first_verse_id, first_word_order""",
        verse_ids,
    ).fetchall()


def get_word_spans(conn, verse_ids: list[int], strong_number: str):
    """(verse_id, span_start, span_end) for every occurrence of
    `strong_number` within `verse_ids` -- for highlighting."""
    if not verse_ids:
        return []
    placeholders = ",".join("?" * len(verse_ids))
    return conn.execute(
        f"""SELECT vw.verse_id, vw.span_start, vw.span_end
            FROM word_strongs ws
            JOIN verse_words vw ON vw.id = ws.verse_word_id
            WHERE ws.strong_number = ? AND ws.verse_id IN ({placeholders})""",
        [strong_number, *verse_ids],
    ).fetchall()


def get_entry(conn, strong_number: str):
    return conn.execute(
        "SELECT * FROM strongs_entries WHERE number = ?", (strong_number,)
    ).fetchone()


def search_strongs(conn, query: str, limit: int = 30):
    """Look up the whole concordance by Strong's number ('G26', 'h430')
    or by a word fragment matched against transliteration, KJV
    renderings, and definition text. Returns rows shaped like
    get_words_for_verses() (including a Bible-wide occurrence_count) so
    callers can render both with the same card."""
    query = query.strip()
    if not query:
        return []

    if _STRONG_NUMBER_RE.match(query):
        numbers = [normalize_strong(query)]
    else:
        # Diacritics in transliteration (agápē, ʼĕlôhîym, ...) make a
        # plain SQL LIKE useless for an English-keyboard search, so this
        # folds both sides to bare-ASCII-lowercase in Python instead.
        # The table is small (~14k rows), so a full scan per keystroke
        # is still effectively instant.
        needle = _fold(query)
        candidates = conn.execute(
            "SELECT number, transliteration, kjv_translations, definition FROM strongs_entries"
        ).fetchall()
        matches = [
            r for r in candidates
            if needle in _fold(r["transliteration"])
            or needle in _fold(r["kjv_translations"] or "")
            or needle in _fold(r["definition"] or "")
        ]
        matches.sort(key=lambda r: len(r["transliteration"]))
        numbers = [r["number"] for r in matches[:limit]]
    if not numbers:
        return []

    placeholders = ",".join("?" * len(numbers))
    rows = conn.execute(
        f"""SELECT se.number AS strong_number, se.original_word, se.transliteration,
                   se.definition, se.kjv_translations, COUNT(ws.id) AS occurrence_count
            FROM strongs_entries se
            LEFT JOIN word_strongs ws ON ws.strong_number = se.number
            WHERE se.number IN ({placeholders})
            GROUP BY se.number""",
        numbers,
    ).fetchall()
    order = {number: i for i, number in enumerate(numbers)}
    return sorted(rows, key=lambda r: order[r["strong_number"]])


def get_verses_for_strong(conn, strong_number: str, limit: int | None = None):
    """(verse rows, total occurrence count) for every verse using
    `strong_number` -- concordance browsing. Unlimited by default: even
    the most frequent word in the whole Bible (G3588, "the", ~6,400
    verses) is cheap to fetch and safe to render in the desktop app."""
    total = conn.execute(
        "SELECT COUNT(DISTINCT verse_id) FROM word_strongs WHERE strong_number = ?",
        (strong_number,),
    ).fetchone()[0]
    sql = """SELECT DISTINCT v.* FROM word_strongs ws
             JOIN verses v ON v.id = ws.verse_id
             WHERE ws.strong_number = ?
             ORDER BY v.id"""
    params = [strong_number]
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return rows, total
