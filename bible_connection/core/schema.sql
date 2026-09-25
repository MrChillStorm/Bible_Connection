-- Bible Connections schema (SQLite).
-- Designed to map directly onto Postgres + pgvector later:
--   verses/edges stay as-is; embeddings.vector (BLOB) becomes a
--   `vector` column via pgvector instead of raw float32 bytes.

CREATE TABLE IF NOT EXISTS verses (
    id INTEGER PRIMARY KEY,          -- book_order*1e6 + chapter*1000 + verse
    book TEXT NOT NULL,
    book_order INTEGER NOT NULL,
    chapter INTEGER NOT NULL,
    verse INTEGER NOT NULL,
    text TEXT NOT NULL,
    woc_spans TEXT,                  -- JSON [[start,end],...] char offsets into `text`: Jesus's words (red letter)
    UNIQUE (book, chapter, verse)
);

CREATE INDEX IF NOT EXISTS idx_verses_book_order ON verses (book_order, chapter, verse);

CREATE TABLE IF NOT EXISTS embeddings (
    verse_id INTEGER PRIMARY KEY REFERENCES verses (id),
    model TEXT NOT NULL,
    dim INTEGER NOT NULL,
    vector BLOB NOT NULL             -- float32, little-endian, length dim*4 bytes
);

-- edge_type: 'curated' (openbible.info / TSK) | 'semantic' (embedding similarity)
-- future: 'lemma', 'quotation', 'thematic'
-- Stored with verse_id_a < verse_id_b so each pair appears once per type.
CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verse_id_a INTEGER NOT NULL REFERENCES verses (id),
    verse_id_b INTEGER NOT NULL REFERENCES verses (id),
    edge_type TEXT NOT NULL,
    weight REAL NOT NULL,
    source TEXT,
    UNIQUE (verse_id_a, verse_id_b, edge_type)
);

CREATE INDEX IF NOT EXISTS idx_edges_a ON edges (verse_id_a, edge_type);
CREATE INDEX IF NOT EXISTS idx_edges_b ON edges (verse_id_b, edge_type);

CREATE VIRTUAL TABLE IF NOT EXISTS verses_fts USING fts5(
    text, content='verses', content_rowid='id'
);

-- Reading position, last-opened book, and read/unread checkboxes are
-- personal state, not shared content -- they live in a separate
-- database (see user_schema.sql / db.py get_user_connection()) so
-- this file can be committed to git without leaking anyone's reading
-- history, while still shipping fully built.

-- Translator's marginal notes (KJV "Heb./Gr." literal renderings etc.),
-- parsed from the OSIS source. anchor_pos is a char offset into
-- verses.text -- where the note's catchword phrase was found (end of
-- the match), or len(text) when the catchword couldn't be located.
CREATE TABLE IF NOT EXISTS footnotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verse_id INTEGER NOT NULL REFERENCES verses (id),
    order_in_verse INTEGER NOT NULL,
    catchword TEXT NOT NULL,
    note TEXT NOT NULL,
    anchor_pos INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_footnotes_verse ON footnotes (verse_id);

-- Scofield Reference Bible study notes (1917 ed., public domain),
-- same shape as footnotes -- catchword-anchored where possible, else
-- attached at verse end.
CREATE TABLE IF NOT EXISTS scofield_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verse_id INTEGER NOT NULL REFERENCES verses (id),
    order_in_verse INTEGER NOT NULL,
    catchword TEXT NOT NULL,
    note TEXT NOT NULL,
    anchor_pos INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scofield_notes_verse ON scofield_notes (verse_id);

-- Strong's Hebrew/Greek dictionary (OpenScriptures, public domain).
-- number is a canonical unpadded form ('H430', 'G2424').
CREATE TABLE IF NOT EXISTS strongs_entries (
    number TEXT PRIMARY KEY,
    original_word TEXT NOT NULL,
    transliteration TEXT NOT NULL,
    pronunciation TEXT,
    derivation TEXT,
    definition TEXT,
    kjv_translations TEXT
);

-- Per-word spans in verses.text, tagged with the Strong's number(s)
-- for that word (usually one; occasionally more when a single English
-- word renders a Greek article+noun pair, e.g. 'God' <- G3588 + G2316).
CREATE TABLE IF NOT EXISTS verse_words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verse_id INTEGER NOT NULL REFERENCES verses (id),
    word_order INTEGER NOT NULL,
    span_start INTEGER NOT NULL,
    span_end INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_verse_words_verse ON verse_words (verse_id);

-- One row per (word, strong_number) pair; verse_id is denormalized here
-- so "every verse using H430" is a single indexed lookup (a proper
-- concordance query) without joining back through verse_words.
CREATE TABLE IF NOT EXISTS word_strongs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verse_word_id INTEGER NOT NULL REFERENCES verse_words (id),
    verse_id INTEGER NOT NULL REFERENCES verses (id),
    strong_number TEXT NOT NULL REFERENCES strongs_entries (number)
);

CREATE INDEX IF NOT EXISTS idx_word_strongs_number ON word_strongs (strong_number);
CREATE INDEX IF NOT EXISTS idx_word_strongs_verse ON word_strongs (verse_id);
CREATE INDEX IF NOT EXISTS idx_word_strongs_word ON word_strongs (verse_word_id);
