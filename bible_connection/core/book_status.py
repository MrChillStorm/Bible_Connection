"""Manual whole-book 'read' checkbox state, for the library start page."""
from datetime import datetime, timezone


def get_all_read(conn) -> set[str]:
    rows = conn.execute("SELECT book FROM book_status WHERE read = 1").fetchall()
    return {r["book"] for r in rows}


def set_read(conn, book: str, read: bool) -> None:
    conn.execute(
        """INSERT INTO book_status (book, read, updated_at) VALUES (?, ?, ?)
           ON CONFLICT (book) DO UPDATE SET read=excluded.read, updated_at=excluded.updated_at""",
        (book, 1 if read else 0, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
