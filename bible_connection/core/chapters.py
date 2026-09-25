"""Chapter-level data access for the reader UI."""
from bible_connection.core.books import BOOK_TO_ORDER


def get_chapter(conn, book: str, chapter: int):
    """Ordered list of verse rows for one chapter."""
    return conn.execute(
        "SELECT * FROM verses WHERE book = ? AND chapter = ? ORDER BY verse",
        (book, chapter),
    ).fetchall()


def chapter_count(conn, book: str) -> int:
    row = conn.execute("SELECT MAX(chapter) AS n FROM verses WHERE book = ?", (book,)).fetchone()
    return row["n"] or 1


def book_exists(book: str) -> bool:
    return book in BOOK_TO_ORDER
