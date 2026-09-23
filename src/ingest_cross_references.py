"""Load data/raw/cross_references.txt (openbible.info TSK-derived dataset)
into the edges table as edge_type='curated'.

Format: From Verse \t To Verse \t Votes, e.g.
    Gen.1.1  Heb.1.10  190
    Gen.1.1  Prov.8.22-Prov.8.30  76   (a range on the "to" side)

Refs are resolved to our internal verse ids via the verses table, so a
range is expanded to every verse actually present between its two
endpoints (handles the rare ranges that cross a chapter/book boundary).
"""
import re
from pathlib import Path

from books import ABBR_TO_BOOK
from db import get_connection

RAW_TXT = Path(__file__).resolve().parent.parent / "data" / "raw" / "cross_references.txt"

REF_RE = re.compile(r"^([1-3]?[A-Za-z]+)\.(\d+)\.(\d+)$")


def resolve_ref(ref: str, book_to_id_lookup) -> int | None:
    m = REF_RE.match(ref)
    if not m:
        return None
    abbr, chapter, verse = m.group(1), int(m.group(2)), int(m.group(3))
    book = ABBR_TO_BOOK.get(abbr)
    if book is None:
        return None
    return book_to_id_lookup.get((book, chapter, verse))


def main() -> None:
    conn = get_connection()

    lookup = {
        (r["book"], r["chapter"], r["verse"]): r["id"]
        for r in conn.execute("SELECT id, book, chapter, verse FROM verses")
    }
    all_ids = sorted(lookup.values())

    def ids_in_range(start_id: int, end_id: int) -> list[int]:
        lo, hi = min(start_id, end_id), max(start_id, end_id)
        import bisect
        i = bisect.bisect_left(all_ids, lo)
        j = bisect.bisect_right(all_ids, hi)
        return all_ids[i:j]

    conn.execute("DELETE FROM edges WHERE edge_type = 'curated'")

    inserted = 0
    skipped_rows = 0
    total_rows = 0
    with RAW_TXT.open(encoding="utf-8") as f:
        next(f)  # header
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            total_rows += 1
            from_ref, to_ref, votes = parts[0], parts[1], parts[2]

            from_id = resolve_ref(from_ref, lookup)
            if from_id is None:
                skipped_rows += 1
                continue

            if "-" in to_ref:
                start_ref, end_ref = to_ref.split("-")
                start_id = resolve_ref(start_ref, lookup)
                end_id = resolve_ref(end_ref, lookup)
                if start_id is None or end_id is None:
                    skipped_rows += 1
                    continue
                to_ids = ids_in_range(start_id, end_id)
            else:
                single = resolve_ref(to_ref, lookup)
                to_ids = [single] if single is not None else []
                if not to_ids:
                    skipped_rows += 1
                    continue

            weight = float(votes)
            for to_id in to_ids:
                if to_id == from_id:
                    continue
                a, b = (from_id, to_id) if from_id < to_id else (to_id, from_id)
                cur = conn.execute(
                    """INSERT OR IGNORE INTO edges (verse_id_a, verse_id_b, edge_type, weight, source)
                       VALUES (?, ?, 'curated', ?, 'openbible_tsk')""",
                    (a, b, weight),
                )
                inserted += cur.rowcount

    conn.commit()
    print(f"Read {total_rows} source rows, skipped {skipped_rows} unresolved, inserted {inserted} curated edges")
    conn.close()


if __name__ == "__main__":
    main()
