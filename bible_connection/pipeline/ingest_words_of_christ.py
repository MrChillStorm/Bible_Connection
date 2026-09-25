"""Enriches the existing `verses` rows with 'words of Christ' (red-letter)
character spans, parsed from the tagged OSIS-JSON KJV source.

Pure enrichment: doesn't touch verses.text (already verified identical
to the plain text this source produces once parsed), so it doesn't
invalidate embeddings, FTS, or edges -- just adds the woc_spans column.
"""
import json

from bible_connection.core.db import get_connection, init_schema
from bible_connection.pipeline import RAW_DIR
from bible_connection.pipeline.osis_parser import parse_verse_text

RAW_JSON = RAW_DIR / "kjv_osis.json"


def main() -> None:
    conn = get_connection()
    init_schema(conn)

    with RAW_JSON.open(encoding="utf-8") as f:
        data = json.load(f)

    lookup = {
        (r["book"], r["chapter"], r["verse"]): r["id"]
        for r in conn.execute("SELECT id, book, chapter, verse FROM verses")
    }

    updates = []
    mismatches = []
    verses_with_woc = 0

    for book in data["books"]:
        for chapter in book["chapters"]:
            for verse in chapter["verses"]:
                key = (book["name"], chapter["chapter"], verse["verse"])
                verse_id = lookup.get(key)
                if verse_id is None:
                    mismatches.append(key)
                    continue

                plain, spans, _notes, _words = parse_verse_text(verse["text"])
                existing_text = conn.execute(
                    "SELECT text FROM verses WHERE id = ?", (verse_id,)
                ).fetchone()["text"]
                if plain != existing_text:
                    mismatches.append((*key, "text differs, skipped"))
                    continue

                if spans:
                    verses_with_woc += 1
                updates.append((json.dumps(spans) if spans else None, verse_id))

    conn.executemany("UPDATE verses SET woc_spans = ? WHERE id = ?", updates)
    conn.commit()

    print(f"Updated {len(updates)} verses, {verses_with_woc} contain words of Christ")
    if mismatches:
        print(f"WARNING: {len(mismatches)} verses skipped due to mismatch:")
        for m in mismatches[:10]:
            print("  ", m)
    conn.close()


if __name__ == "__main__":
    main()
