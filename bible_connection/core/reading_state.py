"""Per-book reading position persistence, for the desktop reader's
'resume where you left off' behavior."""
from datetime import datetime, timezone


def get_position(conn, book: str):
    """Returns (chapter, verse) for the last-read spot in `book`, or None."""
    row = conn.execute(
        "SELECT chapter, verse FROM reading_state WHERE book = ?", (book,)
    ).fetchone()
    return (row["chapter"], row["verse"]) if row else None


def set_position(conn, book: str, chapter: int, verse: int) -> None:
    conn.execute(
        """INSERT INTO reading_state (book, chapter, verse, updated_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT (book) DO UPDATE SET chapter=excluded.chapter, verse=excluded.verse, updated_at=excluded.updated_at""",
        (book, chapter, verse, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def get_last_book(conn) -> str | None:
    row = conn.execute("SELECT value FROM app_state WHERE key = 'last_book'").fetchone()
    return row["value"] if row else None


def set_last_book(conn, book: str) -> None:
    conn.execute(
        "INSERT INTO app_state (key, value) VALUES ('last_book', ?) "
        "ON CONFLICT (key) DO UPDATE SET value=excluded.value",
        (book,),
    )
    conn.commit()


def get_font_scale(conn) -> float | None:
    row = conn.execute("SELECT value FROM app_state WHERE key = 'font_scale'").fetchone()
    return float(row["value"]) if row else None


def set_font_scale(conn, scale: float) -> None:
    conn.execute(
        "INSERT INTO app_state (key, value) VALUES ('font_scale', ?) "
        "ON CONFLICT (key) DO UPDATE SET value=excluded.value",
        (str(scale),),
    )
    conn.commit()
