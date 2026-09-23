"""Load data/raw/kjv.csv (Book,Chapter,Verse,Text) into the verses table."""
import csv
from pathlib import Path

from books import BOOK_TO_ORDER, verse_id
from db import get_connection, init_schema

RAW_CSV = Path(__file__).resolve().parent.parent / "data" / "raw" / "kjv.csv"


def main() -> None:
    conn = get_connection()
    init_schema(conn)

    rows = []
    with RAW_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            book = row["Book"]
            order = BOOK_TO_ORDER.get(book)
            if order is None:
                raise ValueError(f"Unknown book in KJV source: {book!r}")
            chapter = int(row["Chapter"])
            verse = int(row["Verse"])
            vid = verse_id(order, chapter, verse)
            rows.append((vid, book, order, chapter, verse, row["Text"]))

    conn.execute("DELETE FROM verses_fts")
    conn.execute("DELETE FROM verses")
    conn.executemany(
        """INSERT INTO verses (id, book, book_order, chapter, verse, text)
           VALUES (?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.execute("INSERT INTO verses_fts (rowid, text) SELECT id, text FROM verses")
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM verses").fetchone()[0]
    print(f"Ingested {count} verses ({len(rows)} rows read) into {conn.execute('PRAGMA database_list').fetchone()[2]}")
    conn.close()


if __name__ == "__main__":
    main()
