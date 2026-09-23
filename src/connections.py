"""Look up a verse and its connections (curated + semantic), and simple
text search — the core query logic shared by the CLI and the API."""
import argparse
import math
import random
import re
from collections import Counter

from db import get_connection


_NUMERIC_PREFIX = {"1": "I", "2": "II", "3": "III"}
_OT_NT_BOUNDARY = 39  # Malachi is book_order 39, Matthew is 40
_MIN_VERSE_LENGTH = 60  # excludes formulaic short verses ("And the LORD spake unto
                        # Moses, saying") that score a perfect 1.0 on wording alone
                        # without being an interesting connection
_MIN_DISCOVER_WEIGHT = 0.75  # cosine similarity measures textual/thematic closeness,
                             # not "this is a meaningful connection" -- below this the
                             # pool leans toward shared sentence rhythm or vocabulary
                             # rather than substantive overlap (measured directly:
                             # cross-testament, no-curated-backing candidates drop from
                             # ~103 pairs at 0.75+ to noticeably weaker ones by 0.73)

# -- lexical corroboration for Discover: does the pair share at least one
# genuinely uncommon English word, or is the embedding similarity riding
# on sentence shape / generic vocabulary alone? --

_STOPWORDS = frozenset("""
a an the and or but if of to in on at by for with as is was were be been being
he she it they we i you him her them his hers its their our your my me us
this that these those who whom which what when where why how
not no so than then there here also too very just only even
shall will would should could can may might must do did does done
have has had having
from into unto upon over under between among through before after again against
up down out off about above below
all any each every both few more most other some such
thou thee thy thine thyself ye hath hast doth dost shalt wilt art
verily behold yea nay lo hither thither whither wherefore therefore wherewith
said saith spake speak speaketh saying answered answereth answer cried crieth asked
stand stood come came go went take took bring brought give gave see saw
hear heard sent send set put made make turn turned know knew get got run
fall fell lay look looked sit rose rise
""".split())
_TOKEN_RE = re.compile(r"[a-zA-Z']+")
_MIN_LEXICAL_IDF = 4.0  # a genuine connection usually hinges on at least one
                        # distinctly uncommon shared word; validated against a
                        # hand-checked sample -- a known-weak match ("thou art
                        # the man" / "thou art... the King of Israel") topped
                        # out at 2.65 on its best shared word (king/god/israel
                        # are all too common to mean much on their own), while
                        # every hand-picked genuinely good match cleared 4.5


def _stem(word: str) -> str:
    """Crude KJV-aware suffix stripping, not a real stemmer -- mainly folds
    common archaic verb endings ('keepeth' -> 'keep') into a base form so
    lexical overlap isn't blind to inflection. Known miss: irregular/
    'silent e' stems ('circumcised' doesn't fold to 'circumcise'). Good
    enough as a coarse corroboration signal, not precise enough for
    anything that needs to be exact."""
    for suffix in ("eth", "est"):
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            return word[: -len(suffix)]
    if word.endswith("ing") and len(word) > 5:
        return word[:-3]
    if word.endswith("ed") and len(word) > 4:
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def _content_words(text: str) -> frozenset:
    return frozenset(
        _stem(w)
        for w in (t.lower().strip("'") for t in _TOKEN_RE.findall(text))
        if w and w not in _STOPWORDS and len(w) > 2
    )


_lexical_index_cache = None  # (idf_by_word, content_words_by_verse_id); built once per process


def _lexical_index(conn):
    global _lexical_index_cache
    if _lexical_index_cache is None:
        rows = conn.execute("SELECT id, text FROM verses").fetchall()
        words_by_id = {r["id"]: _content_words(r["text"]) for r in rows}
        doc_freq = Counter(w for words in words_by_id.values() for w in words)
        n = len(rows)
        idf = {w: math.log(n / df) for w, df in doc_freq.items()}
        _lexical_index_cache = (idf, words_by_id)
    return _lexical_index_cache


def _max_shared_word_idf(conn, id_a: int, id_b: int) -> float:
    idf, words_by_id = _lexical_index(conn)
    shared = words_by_id.get(id_a, frozenset()) & words_by_id.get(id_b, frozenset())
    return max((idf[w] for w in shared), default=0.0)


def _normalize_book(book_input: str) -> str:
    parts = book_input.strip().split(" ", 1)
    if len(parts) == 2 and parts[0] in _NUMERIC_PREFIX:
        return f"{_NUMERIC_PREFIX[parts[0]]} {parts[1]}"
    return book_input.strip()


def find_verse(conn, ref: str):
    """Parse a loose reference like 'John 3:16' or '1 Samuel 17:45'."""
    m = re.match(r"^\s*([1-3]?\s?[A-Za-z ]+?)\s+(\d+):(\d+)\s*$", ref)
    if not m:
        return None
    book_input, chapter, verse = _normalize_book(m.group(1)), int(m.group(2)), int(m.group(3))
    row = conn.execute(
        "SELECT * FROM verses WHERE book = ? COLLATE NOCASE AND chapter = ? AND verse = ?",
        (book_input, chapter, verse),
    ).fetchone()
    if row is None:
        # loose fallback, e.g. "Revelation" for "Revelation of John"
        row = conn.execute(
            "SELECT * FROM verses WHERE book LIKE ? COLLATE NOCASE AND chapter = ? AND verse = ?",
            (f"{book_input}%", chapter, verse),
        ).fetchone()
    return row


def verse_ref(row) -> str:
    return f"{row['book']} {row['chapter']}:{row['verse']}"


def get_connections(conn, verse_id: int, limit: int = 10):
    curated = conn.execute(
        """SELECT v.*, e.weight FROM edges e
           JOIN verses v ON v.id = (CASE WHEN e.verse_id_a = ? THEN e.verse_id_b ELSE e.verse_id_a END)
           WHERE e.edge_type = 'curated' AND (e.verse_id_a = ? OR e.verse_id_b = ?)
           ORDER BY e.weight DESC LIMIT ?""",
        (verse_id, verse_id, verse_id, limit),
    ).fetchall()

    semantic = conn.execute(
        """SELECT v.*, e.weight FROM edges e
           JOIN verses v ON v.id = (CASE WHEN e.verse_id_a = ? THEN e.verse_id_b ELSE e.verse_id_a END)
           WHERE e.edge_type = 'semantic' AND (e.verse_id_a = ? OR e.verse_id_b = ?)
           ORDER BY e.weight DESC LIMIT ?""",
        (verse_id, verse_id, verse_id, limit),
    ).fetchall()

    return curated, semantic


def get_connections_for_verses(conn, verse_ids: list[int], limit: int = 20):
    """Aggregated connections for a *set* of verses (e.g. everything
    currently visible in the reading pane). For each edge type, returns
    the top connected verses outside the visible set, each annotated
    with which visible verse it connects from and the edge weight.
    """
    if not verse_ids:
        return [], []
    visible_set = set(verse_ids)
    placeholders = ",".join("?" * len(verse_ids))

    def fetch(edge_type):
        rows = conn.execute(
            f"""SELECT verse_id_a, verse_id_b, weight FROM edges
                WHERE edge_type = ? AND (verse_id_a IN ({placeholders}) OR verse_id_b IN ({placeholders}))""",
            (edge_type, *verse_ids, *verse_ids),
        ).fetchall()

        best: dict[int, tuple[float, int]] = {}  # target_id -> (weight, source_id)
        for r in rows:
            a, b, w = r["verse_id_a"], r["verse_id_b"], r["weight"]
            a_in, b_in = a in visible_set, b in visible_set
            if a_in and b_in:
                continue  # both ends already on screen -- not an interesting "connection"
            if a_in:
                source, target = a, b
            elif b_in:
                source, target = b, a
            else:
                continue
            if target not in best or w > best[target][0]:
                best[target] = (w, source)

        ranked = sorted(best.items(), key=lambda kv: -kv[1][0])[:limit]
        if not ranked:
            return []

        target_ids = [t for t, _ in ranked]
        source_ids = list({s for _, (_, s) in ranked})
        all_ids = list(set(target_ids) | set(source_ids))
        rows_by_id = {
            row["id"]: row
            for row in conn.execute(
                f"SELECT * FROM verses WHERE id IN ({','.join('?' * len(all_ids))})", all_ids
            ).fetchall()
        }

        return [
            {"verse": rows_by_id[target_id], "weight": weight, "source_verse": rows_by_id[source_id]}
            for target_id, (weight, source_id) in ranked
        ]

    return fetch("curated"), fetch("semantic")


def get_surprising_connections(conn, limit: int = 20, cross_testament_only: bool = True):
    """A browsable sample of 'semantic' connections that have no
    curated cross-reference behind them -- i.e. a machine-learning
    model found these on its own, nobody's traditional cross-reference
    list did. Meant for
    discovering something independent of whatever's currently being
    read, rather than reacting to it, so this samples randomly from a
    generous top-weighted pool instead of always returning the exact
    same ranked list.
    """
    testament_clause = (
        """AND ((va.book_order <= :boundary AND vb.book_order > :boundary)
             OR (va.book_order > :boundary AND vb.book_order <= :boundary))"""
        if cross_testament_only else ""
    )
    pool_size = limit * 15  # oversample so repeated shuffles don't always look identical
    rows = conn.execute(
        f"""SELECT e.weight, va.id AS a_id, vb.id AS b_id,
                   va.book, va.chapter, va.verse, va.text,
                   vb.book AS b_book, vb.chapter AS b_chapter, vb.verse AS b_verse, vb.text AS b_text
            FROM edges e
            JOIN verses va ON va.id = e.verse_id_a
            JOIN verses vb ON vb.id = e.verse_id_b
            WHERE e.edge_type = 'semantic'
              AND e.weight >= :min_weight
              AND LENGTH(va.text) > :min_len AND LENGTH(vb.text) > :min_len
              {testament_clause}
              AND NOT EXISTS (
                  SELECT 1 FROM edges c WHERE c.edge_type = 'curated'
                    AND ((c.verse_id_a = e.verse_id_a AND c.verse_id_b = e.verse_id_b)
                      OR (c.verse_id_a = e.verse_id_b AND c.verse_id_b = e.verse_id_a))
              )
            ORDER BY e.weight DESC
            LIMIT :pool_size""",
        {
            "boundary": _OT_NT_BOUNDARY,
            "min_len": _MIN_VERSE_LENGTH,
            "min_weight": _MIN_DISCOVER_WEIGHT,
            "pool_size": pool_size,
        },
    ).fetchall()

    # cosine similarity alone can't tell a real echo from two verses that
    # just share sentence shape or generic vocabulary -- require at least
    # one genuinely uncommon shared English word as corroboration
    rows = [r for r in rows if _max_shared_word_idf(conn, r["a_id"], r["b_id"]) >= _MIN_LEXICAL_IDF]

    sample = random.sample(rows, k=min(limit, len(rows)))
    sample.sort(key=lambda r: -r["weight"])
    return sample


def search_text(conn, query: str, limit: int = 15):
    return conn.execute(
        """SELECT v.* FROM verses_fts f
           JOIN verses v ON v.id = f.rowid
           WHERE verses_fts MATCH ? ORDER BY rank LIMIT ?""",
        (query, limit),
    ).fetchall()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", help="e.g. 'John 3:16'")
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()

    conn = get_connection()
    row = find_verse(conn, args.reference)
    if row is None:
        print(f"Could not find verse: {args.reference!r}")
        return

    print(f"{verse_ref(row)} — {row['text']}\n")

    curated, semantic = get_connections(conn, row["id"], limit=args.limit)

    print(f"Curated cross-references ({len(curated)}):")
    for r in curated:
        print(f"  [{r['weight']:>4.0f} votes] {verse_ref(r)} — {r['text']}")

    print(f"\nSemantic connections ({len(semantic)}):")
    for r in semantic:
        print(f"  [{r['weight']:.3f}] {verse_ref(r)} — {r['text']}")


if __name__ == "__main__":
    main()
