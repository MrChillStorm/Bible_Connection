"""Parses the cached Scofield Reference Notes HTML (data/raw/scofield/)
into the scofield_notes table, anchored the same way footnotes are."""
from pathlib import Path

from anchor_utils import resolve_anchor
from books import BOOK_ORDER
from db import get_connection, init_schema
from scofield_parser import parse_book_notes

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "scofield"


def main() -> None:
    conn = get_connection()
    init_schema(conn)

    conn.execute("DELETE FROM scofield_notes")

    rows = []
    resolved = 0
    missing_books = []

    for book in BOOK_ORDER:
        path = RAW_DIR / f"{book}.html"
        if not path.exists():
            missing_books.append(book)
            continue

        verse_lookup = {}
        text_lookup = {}
        for r in conn.execute(
            "SELECT chapter, verse, id, text FROM verses WHERE book = ?", (book,)
        ):
            verse_lookup[(r["chapter"], r["verse"])] = r["id"]
            text_lookup[(r["chapter"], r["verse"])] = r["text"]

        notes = parse_book_notes(path.read_text(encoding="utf-8"))
        order_counters: dict[int, int] = {}

        for chapter, verse, catchword, note_text in notes:
            key = (chapter, verse)
            verse_id = verse_lookup.get(key)
            if verse_id is None:
                continue
            plain = text_lookup[key]
            anchor_pos = resolve_anchor(plain, catchword)
            if anchor_pos < len(plain):
                resolved += 1
            order = order_counters.get(verse_id, 0)
            order_counters[verse_id] = order + 1
            rows.append((verse_id, order, catchword, note_text, anchor_pos))

    conn.executemany(
        """INSERT INTO scofield_notes (verse_id, order_in_verse, catchword, note, anchor_pos)
           VALUES (?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()

    print(f"Inserted {len(rows)} Scofield notes ({resolved} anchored to a phrase, {len(rows) - resolved} at verse end)")
    if missing_books:
        print(f"WARNING: {len(missing_books)} books had no cached HTML: {missing_books}")
    conn.close()


if __name__ == "__main__":
    main()
