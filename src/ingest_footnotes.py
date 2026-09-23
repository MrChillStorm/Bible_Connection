"""Extracts translator's marginal notes from the OSIS-JSON KJV source
into the footnotes table, anchored to a specific phrase in verses.text
wherever the note's catchword can be located there.
"""
import json
from pathlib import Path

from anchor_utils import resolve_anchor
from db import get_connection, init_schema
from osis_parser import parse_verse_text

RAW_JSON = Path(__file__).resolve().parent.parent / "data" / "raw" / "kjv_osis.json"


def main() -> None:
    conn = get_connection()
    init_schema(conn)

    with RAW_JSON.open(encoding="utf-8") as f:
        data = json.load(f)

    lookup = {
        (r["book"], r["chapter"], r["verse"]): r["id"]
        for r in conn.execute("SELECT id, book, chapter, verse FROM verses")
    }

    conn.execute("DELETE FROM footnotes")

    rows = []
    resolved = 0
    for book in data["books"]:
        for chapter in book["chapters"]:
            for verse in chapter["verses"]:
                key = (book["name"], chapter["chapter"], verse["verse"])
                verse_id = lookup.get(key)
                if verse_id is None:
                    continue
                plain, _spans, notes, _words = parse_verse_text(verse["text"])
                occurrence_counts: dict[str, int] = {}
                for order, (catchword, note_text) in enumerate(notes):
                    occurrence = occurrence_counts.get(catchword, 0)
                    anchor_pos = resolve_anchor(plain, catchword, occurrence=occurrence)
                    if anchor_pos < len(plain):
                        resolved += 1
                        occurrence_counts[catchword] = occurrence + 1
                    rows.append((verse_id, order, catchword, note_text, anchor_pos))

    conn.executemany(
        """INSERT INTO footnotes (verse_id, order_in_verse, catchword, note, anchor_pos)
           VALUES (?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()

    print(f"Inserted {len(rows)} footnotes ({resolved} anchored to a phrase, {len(rows) - resolved} at verse end)")
    conn.close()


if __name__ == "__main__":
    main()
