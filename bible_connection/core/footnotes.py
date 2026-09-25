"""Footnote lookup for the reader UI."""


def get_footnotes_for_chapter(conn, book: str, chapter: int) -> dict[int, list]:
    """Returns {verse_id: [footnote rows in order]} for one chapter."""
    rows = conn.execute(
        """SELECT f.* FROM footnotes f
           JOIN verses v ON v.id = f.verse_id
           WHERE v.book = ? AND v.chapter = ?
           ORDER BY v.verse, f.order_in_verse""",
        (book, chapter),
    ).fetchall()
    by_verse: dict[int, list] = {}
    for row in rows:
        by_verse.setdefault(row["verse_id"], []).append(row)
    return by_verse
