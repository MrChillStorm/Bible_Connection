"""Parses per-word Strong's-number spans from the OSIS-JSON KJV source
into verse_words + word_strongs. Requires strongs_entries to already be
loaded (run ingest_strongs_dictionary.py first)."""
import json
from pathlib import Path

from db import get_connection, init_schema
from osis_parser import parse_verse_text
from strongs_parser import normalize_strong

RAW_JSON = Path(__file__).resolve().parent.parent / "data" / "raw" / "kjv_osis.json"


def main() -> None:
    conn = get_connection()
    init_schema(conn)

    known_numbers = {r["number"] for r in conn.execute("SELECT number FROM strongs_entries")}
    if not known_numbers:
        raise RuntimeError("strongs_entries is empty -- run ingest_strongs_dictionary.py first")

    with RAW_JSON.open(encoding="utf-8") as f:
        data = json.load(f)

    lookup = {
        (r["book"], r["chapter"], r["verse"]): r["id"]
        for r in conn.execute("SELECT id, book, chapter, verse FROM verses")
    }

    conn.execute("DELETE FROM word_strongs")
    conn.execute("DELETE FROM verse_words")

    unknown_numbers = set()
    word_rows = []  # (verse_id, word_order, span_start, span_end, [numbers])

    for book in data["books"]:
        for chapter in book["chapters"]:
            for verse in chapter["verses"]:
                key = (book["name"], chapter["chapter"], verse["verse"])
                verse_id = lookup.get(key)
                if verse_id is None:
                    continue
                _plain, _woc, _notes, words = parse_verse_text(verse["text"])
                for order, (start, end, raw_numbers) in enumerate(words):
                    numbers = [normalize_strong(n) for n in raw_numbers]
                    numbers = [n for n in numbers if n in known_numbers]
                    unknown_numbers.update(set(normalize_strong(n) for n in raw_numbers) - known_numbers)
                    if numbers:
                        word_rows.append((verse_id, order, start, end, numbers))

    cur = conn.cursor()
    strongs_rows = []
    for verse_id, order, start, end, numbers in word_rows:
        cur.execute(
            "INSERT INTO verse_words (verse_id, word_order, span_start, span_end) VALUES (?, ?, ?, ?)",
            (verse_id, order, start, end),
        )
        verse_word_id = cur.lastrowid
        strongs_rows.extend((verse_word_id, verse_id, n) for n in numbers)

    conn.executemany(
        "INSERT INTO word_strongs (verse_word_id, verse_id, strong_number) VALUES (?, ?, ?)",
        strongs_rows,
    )
    conn.commit()

    print(f"Inserted {len(word_rows)} tagged words, {len(strongs_rows)} word-strongs associations")
    if unknown_numbers:
        print(f"WARNING: {len(unknown_numbers)} Strong's numbers not found in dictionary: {sorted(unknown_numbers)[:10]}")
    conn.close()


if __name__ == "__main__":
    main()
