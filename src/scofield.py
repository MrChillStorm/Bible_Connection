"""Scofield Reference Bible study-note lookup for the reader UI."""


def get_scofield_notes_for_chapter(conn, book: str, chapter: int) -> dict[int, list]:
    """Returns {verse_id: [scofield_notes rows in order]} for one chapter."""
    rows = conn.execute(
        """SELECT s.* FROM scofield_notes s
           JOIN verses v ON v.id = s.verse_id
           WHERE v.book = ? AND v.chapter = ?
           ORDER BY v.verse, s.order_in_verse""",
        (book, chapter),
    ).fetchall()
    by_verse: dict[int, list] = {}
    for row in rows:
        by_verse.setdefault(row["verse_id"], []).append(row)
    return by_verse
