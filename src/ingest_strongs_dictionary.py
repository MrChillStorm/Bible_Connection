"""Loads the Strong's Hebrew + Greek dictionary (OpenScriptures XML)
into the strongs_entries table."""
from pathlib import Path

from db import get_connection, init_schema
from strongs_parser import parse_greek, parse_hebrew

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def main() -> None:
    conn = get_connection()
    init_schema(conn)

    greek = parse_greek((RAW_DIR / "strongs_greek.xml").read_text(encoding="utf-8"))
    hebrew = parse_hebrew((RAW_DIR / "strongs_hebrew.xml").read_text(encoding="utf-8"))

    conn.execute("DELETE FROM strongs_entries")
    rows = [
        (
            number,
            e["original_word"],
            e["transliteration"],
            e["pronunciation"],
            e["derivation"],
            e["definition"],
            e["kjv_translations"],
        )
        for number, e in {**hebrew, **greek}.items()
    ]
    conn.executemany(
        """INSERT INTO strongs_entries
           (number, original_word, transliteration, pronunciation, derivation, definition, kjv_translations)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    print(f"Loaded {len(hebrew)} Hebrew + {len(greek)} Greek Strong's entries ({len(rows)} total)")
    conn.close()


if __name__ == "__main__":
    main()
