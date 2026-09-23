-- Personal reading state (SQLite). Kept in its own database file,
-- separate from schema.sql's content database, specifically so it
-- never needs to be (and never accidentally is) committed to git.

-- Per-book reading position, for the desktop reader's "resume where you
-- left off" behavior: each book remembers its own last chapter/verse.
CREATE TABLE IF NOT EXISTS reading_state (
    book TEXT PRIMARY KEY,
    chapter INTEGER NOT NULL,
    verse INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);

-- Small key/value store for app-level state, e.g. which book was open
-- when the app last closed.
CREATE TABLE IF NOT EXISTS app_state (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Whole-book "I've read this" checkbox, independent of reading_state
-- (which tracks in-progress position). Manually toggled by the user.
CREATE TABLE IF NOT EXISTS book_status (
    book TEXT PRIMARY KEY,
    read INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
