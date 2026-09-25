"""Enriches strongs_entries.definition with STEPBible's Translators
Brief lexicons (TBESG for Greek: Abbott-Smith/Middle Liddell; TBESH for
Hebrew: abridged BDB) -- considerably fuller than the base OpenScriptures
definition already loaded by ingest_strongs_dictionary.py, which this
script must run after (it only updates rows that already exist).

Run fetch_strongs_lexicon.py first to download the two source files.
Idempotent: re-running just overwrites with the same derived text.

Source data: STEPBible-Data (github.com/STEPBible/STEPBible-Data),
CC BY 4.0, created by www.STEPBible.org based on work at Tyndale House
Cambridge.
"""
import re
from collections import defaultdict

from bible_connection.core.db import get_connection
from bible_connection.core.strongs_parser import normalize_strong
from bible_connection.pipeline import RAW_DIR


_DATA_LINE_RE = re.compile(r"^([GH]\d{4})\t")
_REF_TAG_RE = re.compile(r"</?ref=?(?:'[^']*'|\"[^\"]*\")?>", re.IGNORECASE)


def _clean_meaning(text: str) -> str:
    # <ref='Rom.2.4'>Rom.2:4</ref> -- STEPBible's own clickable verse
    # links, meaningless (and invalid) once copied out of their site;
    # this keeps the visible reference text and drops the tag itself.
    return _REF_TAG_RE.sub("", text).strip()


def parse_lexicon(text: str) -> dict[str, str]:
    """{normalized Strong's number: definition}. A handful of eStrong
    numbers have more than one sense-specific row (e.g. a common word
    that's also a proper name) -- those are joined rather than picking
    one arbitrarily, so no sense is silently dropped."""
    by_number: dict[str, list[str]] = defaultdict(list)
    for line in text.splitlines():
        if not _DATA_LINE_RE.match(line):
            continue
        fields = line.split("\t")
        if len(fields) < 8:
            continue
        number = normalize_strong(fields[0])
        meaning = _clean_meaning(fields[7])
        if meaning and meaning not in by_number[number]:
            by_number[number].append(meaning)

    return {number: "<br><br>".join(meanings) for number, meanings in by_number.items()}


def main() -> None:
    conn = get_connection()

    lexicon: dict[str, str] = {}
    for filename in ("tbesg.txt", "tbesh.txt"):
        path = RAW_DIR / filename
        if not path.exists():
            raise SystemExit(f"{path} not found -- run fetch_strongs_lexicon.py first")
        lexicon.update(parse_lexicon(path.read_text(encoding="utf-8")))

    existing = {r["number"] for r in conn.execute("SELECT number FROM strongs_entries")}
    matched = existing & lexicon.keys()

    conn.executemany(
        "UPDATE strongs_entries SET definition = ? WHERE number = ?",
        [(lexicon[number], number) for number in matched],
    )
    conn.commit()
    print(f"Enriched {len(matched)} of {len(existing)} Strong's entries "
          f"({len(existing) - len(matched)} kept their original OpenScriptures definition)")


if __name__ == "__main__":
    main()
