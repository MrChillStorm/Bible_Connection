import shutil
import sqlite3
from pathlib import Path

from platformdirs import user_data_dir

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "processed" / "bible.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
USER_SCHEMA_PATH = Path(__file__).resolve().parent / "user_schema.sql"

_LEGACY_USER_TABLES = ("reading_state", "app_state", "book_status")
_LEGACY_USER_DB_PATH = ROOT / "data" / "processed" / "user_state.db"  # pre-homedir location

# The OS's conventional per-user application-data directory --
# deliberately outside this project folder, so personal state isn't
# tied to wherever that folder happens to live. Two OS accounts sharing
# one copy of the app get independent reading histories, and moving or
# redownloading the project folder doesn't strand anyone's progress.
# appauthor=False skips Windows' extra publisher-named subfolder, which
# this project has no use for.
USER_DB_PATH = Path(user_data_dir("Bible Connections", appauthor=False)) / "user_state.db"


def get_connection() -> sqlite3.Connection:
    """The shared content database: verses, connections, footnotes,
    Strong's entries, Scofield notes. Built by the ingestion scripts,
    unchanged by normal use of the app, and safe to commit to git."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_user_connection() -> sqlite3.Connection:
    """Personal reading state: position, last-opened book, read/unread
    checkboxes. Lives in the OS's per-user data directory, not inside
    this project folder -- deliberately a separate file from the
    content database too, so nothing written here should ever end up
    in a git commit."""
    _migrate_user_db_location()
    USER_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(USER_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text())
    _migrate(conn)
    conn.commit()


def init_user_schema(user_conn: sqlite3.Connection, content_conn: sqlite3.Connection) -> None:
    user_conn.executescript(USER_SCHEMA_PATH.read_text())
    user_conn.commit()
    _migrate_legacy_user_state(content_conn, user_conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """Adds columns introduced after a database already existed.
    CREATE TABLE IF NOT EXISTS in schema.sql only helps fresh databases."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(verses)")}
    if "woc_spans" not in existing:
        conn.execute("ALTER TABLE verses ADD COLUMN woc_spans TEXT")


def _migrate_legacy_user_state(content_conn: sqlite3.Connection, user_conn: sqlite3.Connection) -> None:
    """reading_state/app_state/book_status used to live in the content
    database, before it was split out so personal reading history
    would never end up committed alongside it. Copies over any rows
    from an older database, then drops the legacy tables so the
    content database is clean of personal data going forward. Safe to
    call on every launch -- a no-op once the legacy tables are gone."""
    existing_tables = {
        row["name"] for row in content_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if not existing_tables & set(_LEGACY_USER_TABLES):
        return

    if "reading_state" in existing_tables:
        for row in content_conn.execute("SELECT * FROM reading_state"):
            user_conn.execute(
                """INSERT OR REPLACE INTO reading_state (book, chapter, verse, updated_at)
                   VALUES (?, ?, ?, ?)""",
                (row["book"], row["chapter"], row["verse"], row["updated_at"]),
            )
    if "app_state" in existing_tables:
        for row in content_conn.execute("SELECT * FROM app_state"):
            user_conn.execute(
                "INSERT OR REPLACE INTO app_state (key, value) VALUES (?, ?)",
                (row["key"], row["value"]),
            )
    if "book_status" in existing_tables:
        for row in content_conn.execute("SELECT * FROM book_status"):
            user_conn.execute(
                "INSERT OR REPLACE INTO book_status (book, read, updated_at) VALUES (?, ?, ?)",
                (row["book"], row["read"], row["updated_at"]),
            )
    user_conn.commit()

    for table in _LEGACY_USER_TABLES:
        content_conn.execute(f"DROP TABLE IF EXISTS {table}")
    content_conn.commit()


def _migrate_user_db_location() -> None:
    """user_state.db used to live inside this project folder
    (data/processed/user_state.db) before it moved to the OS's proper
    per-user directory. Moves the file over on first run after the
    change. Must run before anything ever calls sqlite3.connect() on
    the new path -- that call alone creates an empty file, which would
    make this look like a fresh install and the check below would
    wrongly skip the move."""
    if _LEGACY_USER_DB_PATH.exists() and not USER_DB_PATH.exists():
        USER_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(_LEGACY_USER_DB_PATH), str(USER_DB_PATH))
