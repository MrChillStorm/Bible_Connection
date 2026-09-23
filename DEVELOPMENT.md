# Development notes

This is the technical companion to [README.md](README.md). Read that
first if you just want to run the app — nothing here is required for
normal use, since the built database (`data/processed/bible.db`)
already ships in this repo.

## Project layout

```
src/                 data layer: parsing, ingestion scripts, query helpers
  schema.sql         SQLite schema
  db.py              connection + schema init/migration
  books.py           canonical book list, ordering, verse_id()
  osis_parser.py      parses the OSIS-tagged KJV XML/JSON
  anchor_utils.py     locates a footnote's catchword as a text span
  connections.py       get_connections(), search_text(), etc. — used by both
                        the desktop app and the API
  ingest_*.py          one-shot data loaders (see "Rebuilding from scratch")
  fetch_scofield.py    downloads Scofield notes from Wikisource
  embeddings.py        computes verse embeddings + semantic edges
desktop/             PySide6 desktop app (the primary interface)
api/                 FastAPI web API (secondary interface)
web/                 minimal static HTML frontend for the API
data/raw/            source files (KJV OSIS, cross-references, Strong's, Scofield HTML)
data/processed/      bible.db -- the only thing left here; see below for user_state.db
```

There are deliberately **two** SQLite files, opened separately
(`db.get_connection()` / `db.get_user_connection()`), and they don't
even live in the same directory:

- **`data/processed/bible.db`** — verses, connections, footnotes,
  Strong's, Scofield notes. Built by the ingestion scripts, unchanged
  by normal use of the app, and committed to git so a fresh clone
  works immediately.
- **`user_state.db`, in the OS's per-user data directory** (e.g.
  `~/Library/Application Support/Bible Connection/` on macOS, via the
  `platformdirs` package — `db.USER_DB_PATH`) — reading position,
  last-opened book, read/unread checkboxes. The only thing that
  changes as you read, and deliberately outside the project folder
  entirely: two OS accounts sharing one copy of the app get
  independent reading histories, moving/redownloading the project
  folder doesn't strand anyone's progress, and it structurally can't
  end up in a git commit (nothing to `.gitignore` — it was never under
  the project directory to begin with).

These used to be one file, then one directory; splitting them was a
deliberate fix in two stages, not the original design (see "Personal
state" below) — a single `conn` no longer means "the database," code
now needs to be explicit about which of the two it means.

### Database shape

- `verses` — id (see `verse_id()` below), book, book_order, chapter,
  verse, text, woc_spans (JSON char ranges for red-letter text)
- `embeddings` — verse_id, model, dim, raw vector bytes
- `edges` — verse_id_a, verse_id_b, edge_type (`curated` or `semantic`), weight, source
- `verses_fts` — FTS5 full-text index over verse text
- `footnotes` — verse_id, order_in_verse, catchword, note, anchor_pos
- `scofield_notes` — same shape as `footnotes`
- `strongs_entries` — number (PK), original_word, transliteration,
  pronunciation, derivation, definition, kjv_translations
- `verse_words` / `word_strongs` — per-word span offsets and their
  Strong's number, so the reader can highlight "every occurrence of
  this original word" in the current chapter

`user_state.db` (`user_schema.sql`) holds the other three, kept
separate for exactly the reason described above:
- `reading_state`, `app_state`, `book_status` — per-book last-read
  position, misc app state, and the read/unread checkmarks

### Personal state used to live in the content database (then in the project folder)

Two rounds of the same underlying problem: personal state kept ending
up somewhere it shouldn't.

**Round one:** `reading_state`/`app_state`/`book_status` were just
three more tables in `bible.db`. That became a problem the moment this
project needed to go on GitHub — `bible.db` is supposed to be
committed (so a fresh clone works without rebuilding), but it was also
accumulating someone's actual reading history, and there was no way to
commit one without the other. Fixed by moving those three tables into
their own file (`get_user_connection()` in `db.py`) rather than
"remember to clear those tables before every commit," which is the
kind of manual step that reliably gets forgotten. `db._migrate_legacy_user_state()`
handles the one-time move for a database built before the split —
copies any existing rows into the new file, then drops the legacy
tables from the content database so it's clean of personal data going
forward; it's a no-op once that's done, safe to call on every launch.

**Round two:** that new file still lived inside the project folder
(`data/processed/user_state.db`), just gitignored instead of tracked —
which solved the git problem but not the underlying one: it was still
keyed to wherever the project folder happened to sit, so two OS
accounts sharing one copy of the app would share (and clobber) each
other's reading progress, and moving or redownloading the folder would
strand your history behind. Fixed by moving it again, this time out of
the project entirely and into the OS's per-user data directory via
`platformdirs.user_data_dir()`. `db._migrate_user_db_location()`
handles this one the same way — moves the file on first run after the
change, a no-op afterward.

**Round three:** not a design fix this time, just a consequence of the
project's own rename from "Bible Connections" to "Bible Connection" —
`user_data_dir()`'s app-name argument determines the per-user directory
name, so renaming the app moved *where* `user_state.db` lives on disk
too (`~/Library/Application Support/Bible Connections/` →
`.../Bible Connection/`), same underlying problem as round two, just
triggered by a name change instead of a location redesign.
`_migrate_user_db_location()` now checks both legacy locations — the
original project-folder path and the old plural-named home directory —
and moves straight to the current location from whichever it finds; a
very old install jumps directly there rather than through the
intermediate plural-named stop.

All three migration checks run unconditionally on every
`get_user_connection()` call; they're cheap existence checks when
there's nothing left to migrate.

`LibraryPage` and `ReadingPane` each take a `user_conn` alongside the
regular content `conn` now (`ReadingPane` only for the "resume where
you left off" lookup when you switch books from its combo box —
everything else it does is content-only).

Verse IDs are `book_order * 1_000_000 + chapter * 1000 + verse` —
monotonic and sortable across the whole Bible, which is what makes
"nearest chapter" and range queries cheap without joins.

## Rebuilding from scratch

You don't need to do this — `data/processed/bible.db` is already
built, zipped, and committed as `bible.db.zip` (see "Shipping
`bible.db`" below); the app extracts it on first launch. This section
is only relevant if you're changing how the data is parsed or want to
regenerate a table after editing an ingest script. Each script is
idempotent (delete-then-insert), and they must run in this order since
later ones depend on earlier ones:

```bash
cd src
python3 ingest_kjv.py                # base verse text, from data/raw/kjv.csv
python3 ingest_words_of_christ.py    # red-letter spans, from kjv_osis.json
python3 ingest_footnotes.py          # KJV translators' footnotes, from kjv_osis.json
python3 ingest_strongs_words.py      # per-word Strong's tagging, from kjv_osis.json
python3 ingest_strongs_dictionary.py # Strong's Hebrew/Greek dictionary entries (base definitions)
python3 fetch_strongs_lexicon.py     # downloads STEPBible's richer Greek/Hebrew lexicon (not committed -- see below)
python3 ingest_strongs_lexicon.py    # replaces base definitions with the richer lexicon text where available
python3 ingest_cross_references.py   # curated cross-references (openbible.info/TSK)
python3 fetch_scofield.py            # downloads Scofield HTML from Wikisource (slow, network-bound)
python3 ingest_scofield.py           # parses the downloaded HTML into scofield_notes
python3 embeddings.py                # encodes every verse + computes semantic edges (slow, CPU-bound)
```

`embeddings.py` takes `--skip-encode` to reuse an existing
`embeddings` table and only recompute edges (useful when tuning
`--top-k` / `--threshold`), and both flags are also exposed on the CLI.

**Strong's definitions come from two layered sources.**
`ingest_strongs_dictionary.py` loads OpenScriptures' raw Strong's
dictionary first — for Greek in particular, that's genuinely just
Strong's original one-line 1890 gloss (e.g. G26/ἀγάπη: "love, i.e.
affection or benevolence; specially (plural) a love-feast"). `fetch_strongs_lexicon.py`
+ `ingest_strongs_lexicon.py` then overwrite `definition` with
[STEPBible-Data](https://github.com/STEPBible/STEPBible-Data)'s
Translators Brief lexicons — Abbott-Smith for Greek, abridged BDB for
Hebrew, both Strong's-number-linked, **© Tyndale House Cambridge,
data created by www.STEPBible.org, licensed CC BY 4.0** — wherever a
match exists (95.5% of entries; the ~4.5% gap is mostly G3203–G3302,
which STEPBible's own docs note "aren't used for some reason"). Same
G26 entry afterward runs to several sentences of etymology, LXX usage,
and NT sense breakdown.

STEPBible's license permits including their data in software freely,
but asks two things of anyone who does: (1) note any changes made, and
(2) don't redistribute the raw dataset yourself — point people to
github.com/STEPBible/STEPBible-Data instead. On (1): `ingest_strongs_lexicon.py`
strips STEPBible's own internal `<ref=...>` hyperlink markup (meaningless
outside stepbible.org) and, where one Strong's number has more than
one STEPBible sense-entry (e.g. G1 has separate "Alpha" and "ah!"
entries), joins them into one field with `<br><br>`, since this
project's schema holds one `definition` per number rather than their
disambiguated dStrong scheme — no wording is altered, only reformatted
and merged. On (2): `tbesg.txt`/`tbesh.txt` are fetched on demand and
gitignored, never committed (unlike this project's other raw sources)
— only the derived, reformatted text inside `bible.db` ships.

## Shipping `bible.db`

`bible.db` (~192MB) isn't committed to git directly — it's zipped down
to `bible.db.zip` (~82MB, `zip -9`) and *that's* what's tracked;
`src/db_bootstrap.py` extracts it into `data/processed/bible.db` the
first time the app runs on a machine (~1.5s, measured), and every
launch after that just opens the extracted file directly. Two things
drove this instead of the more obvious options:

- **Committing the raw 192MB file directly doesn't work at all** —
  GitHub hard-rejects any single git object over 100MB.
- **Git LFS** (the standard workaround for exactly this problem) was
  tried first and works, but it bills *download* bandwidth to the repo
  owner's account, with only 1GB/month included free. At ~190MB a
  pull, that's roughly five clones a month before LFS starts failing
  for everyone — trivially exceeded by ordinary traffic, and something
  like a crawler doing full clones would blow through it on day one
  with no way to tell "real reader" from "bot" apart at that layer.
  Zipped-and-committed sidesteps this entirely: it's an ordinary git
  blob, subject to git's normal (unmetered) clone bandwidth, not LFS's
  billed bandwidth.

A GitHub Release asset (uploaded separately, downloaded on first
launch) was considered too — release-asset bandwidth is also unmetered
— but it adds a real network dependency and failure mode (no internet
on first launch = broken app) that a git-committed zip just doesn't
have, so it was dropped once the zip turned out to fit under 100MB
with room to spare.

**Why extraction instead of reading the zip live**: SQLite needs true
random-access seeks into the file for its B-tree paging — jumping
straight to page N wherever a query needs it — and DEFLATE/zip
compression only decompresses sequentially from the start of a member.
There's no way to seek into the middle of a compressed stream, so the
zip has to become a real file on disk before SQLite can open it at
all. `extract_bible_db()` extracts to a temp name and renames into
place atomically, so a crash or a full disk mid-extract can't leave a
truncated `bible.db` that a later launch would mistake for the real
thing.

Note this only fixes bandwidth for *future* clones — the original
192MB LFS blob still exists in this repo's earlier history (the
initial commit and the footnote-anchoring fix that followed it), since
removing it fully would mean rewriting history and force-pushing.
`git clone` only pulls LFS objects the checked-out tree actually
references though, and the current tree no longer references it at
all, so a normal clone today never touches it or its bandwidth cost.

## How connections are found

Two independent kinds of edge live in the `edges` table, both scored
0–1 and both surfaced together in the Connections tab:

**Curated edges** come straight from openbible.info's Treasury of
Scripture Knowledge cross-reference data — connections people have
been drawing between passages for centuries. Weight is their supplied
relevance score.

**Semantic edges** are computed by [`embeddings.py`](src/embeddings.py). Every verse is
encoded with `sentence-transformers/all-MiniLM-L6-v2`
(normalized, so dot product == cosine similarity), and for each verse
we brute-force its cosine similarity against all ~31k others in
batches (never materializing the full N×N matrix — that's ~3.7GB).
This is small enough that no vector index (FAISS, pgvector, etc.) is
worth the complexity.

Two guards keep the results useful:
- **Adjacent-chapter suppression** — a verse's own neighboring
  chapters are excluded from its candidates, since "the next verse
  down" is trivially similar and not an interesting connection.
- **Strong's lemma re-ranking** — the plain-English embedding can't
  tell that two verses share the same *underlying* Hebrew/Greek word
  (as opposed to two different original words that both got translated
  the same way in English). `build_lemma_matrix()` builds a sparse,
  TF-IDF-weighted, **L2-row-normalized** matrix of each verse's tagged
  Strong's numbers, and verses sharing rare original-language words get
  a small boost (`LEMMA_BOOST_ALPHA = 0.15`, capped) added to their
  *ranking* score only — never to the *stored* weight, which stays
  pure cosine similarity throughout.

  The row-normalization matters: without it, a verse sharing several
  moderately common words (e.g. "God", "the", "that") with another can
  rack up a large raw idf-sum purely by sharing many weak signals, none
  individually distinctive — enough to outrank a verse sharing one
  genuinely rare word. Proper cosine similarity divides that back down
  by each verse's own total lemma "weight budget", so a handful of
  common shared words can't out-vote one rare shared word. This was
  caught and fixed during development; final result is 142,374
  semantic edges (vs. 142,377 with no lemma signal at all — the boost
  mostly reorders and swaps close candidates rather than admitting
  wildly different ones).

  Concretely: for each verse, a pool of `top_k * 4` candidates is
  picked by the *boosted* ranking score, then filtered down to only
  those that clear the similarity `threshold` on **pure cosine alone**,
  then re-sorted by the boosted score and truncated to `top_k`. The
  lemma signal can reorder or surface candidates; it can never smuggle
  a low-cosine match past the quality bar.

**The Discover tab** (`connections.get_surprising_connections()`) is a
read-only view over the same `edges` table, not a separate computation
— it samples `semantic` edges that have no matching `curated` edge for
the same verse pair (i.e. no traditional cross-reference backs them),
excludes verses under `_MIN_VERSE_LENGTH` characters (kills formulaic
short verses like "And the LORD spake unto Moses, saying," which
recur so often they hit a perfect 1.0 cosine score without being an
interesting connection), and by default restricts to pairs that cross
the Old/New Testament boundary (`book_order` 39/40, Malachi/Matthew) —
prophecy/fulfillment and typology tend to be the most legible kind of
surprising connection, and same-testament results skew toward genre
duplicates (parallel Kings/Chronicles or Kings/Isaiah narrative blocks
retelling the same events in nearly identical wording). "Shuffle"
re-samples randomly from the top `limit * 15` pool by weight, rather
than always returning the same fixed top-N, so repeated shuffles don't
look identical.

A `_MIN_DISCOVER_WEIGHT = 0.75` floor also applies. Cosine similarity
measures textual/thematic *closeness*, not "this is a meaningful
connection" — measured directly against the cross-testament,
no-curated-backing pool: only ~100 pairs clear 0.75, versus ~300 that
clear the old unfloored `limit * 15` sampling window down to 0.727, and
the extra ~200 in that gap noticeably lean toward shared sentence
rhythm or vocabulary (e.g. two unrelated verses that both happen to use
a "thou art ___" declaration) rather than substantive overlap. If
Discover starts feeling thin (not enough variety on repeated shuffles)
before it feels noisy, raise `limit * 15`; if it still surfaces weak
matches, raise `_MIN_DISCOVER_WEIGHT` instead — don't touch both at
once, since they trade off against each other.

**Lexical corroboration** (`_max_shared_word_idf()`) is a second,
independent filter on top of the weight floor. The first thing tried
here was plain content-word overlap (Jaccard / overlap-coefficient on
non-stopword words, optionally IDF-weighted) as a combined score with
cosine — it was tested directly against known good and bad examples and
**rejected**: a known-weak match ("Thou art the man" / "thou art...
King of Israel", overlap driven by "god"/"israel"/"king") scored
*higher* on every normalization tried than several genuinely good
matches (Numbers 24:19/Luke 1:33, which share only "Jacob"), because
those good matches make their connection through a single distinctive
word or through meaning rather than literal vocabulary — exactly the
kind of match embeddings exist to catch, and exactly what an
overlap-ratio filter penalizes. A combined score built from a signal
that doesn't itself separate good from bad would just launder that
noise into a single number, not remove it. Optimizing the combination
weights against Spearman correlation (or anything else) doesn't fix
this either without labeled ground truth to optimize against — with a
weak feature going in, no amount of curve-fitting the mixing weights
recovers a separation that wasn't there to begin with.

What did separate cleanly, checked directly on the same examples: the
single **highest**-IDF word the two verses share, rather than an
overlap ratio of all of them. The weak match's best shared word ("king")
scored 2.65; every hand-checked good match cleared 4.5. Intuition: a
real connection usually turns on *at least one* genuinely uncommon
word, whereas coincidental overlap tends to be made of several
moderately-common-but-non-stopword words ("god," "israel," "king")
that individually mean little. `_MIN_LEXICAL_IDF = 4.0` is set between
those two clusters. Verses are tokenized with a light KJV-aware
suffix stripper (`_stem()` — not a real stemmer, just folds `-eth`/
`-est`/`-ing`/`-ed`/plural `-s`, so "keepeth" and "keep" count as the
same word) before IDF is computed once per process and cached
(`_lexical_index()`, ~235ms for all ~31k verses, paid once at the
first Discover load). Known gap: irregular stems it can't fold
("circumcised" doesn't reduce to "circumcise") still read as
zero-overlap false negatives — acceptable for a coarse corroboration
signal, not for anything needing real precision.

## Desktop app architecture notes

- The connections shown while reading are **not** a live vector
  search — they're pre-computed rows in `edges`, joined against
  whichever verses are currently visible
  (`connections.get_connections_for_verses()`). This is what makes
  scrolling instant with no model in the loop at runtime; the
  `sentence-transformers` dependency is only ever imported by
  `embeddings.py`, not by the desktop app itself.
- Light/dark mode is read once at launch via Qt's
  `styleHints().colorScheme()` (`desktop/theme.py`), not polled — the
  app doesn't currently react to the OS theme changing while it's
  already running.
- **Live font scaling** (`desktop/fonts.py`) is a single module-level
  multiplier (`fonts.px(base) -> round(base * scale)`), persisted via
  `reading_state.get/set_font_scale()` (another `app_state` key,
  alongside `last_book`). Every explicit `font-size` in the desktop app
  is written as `fonts.px(N)` rather than a literal, so the A-/A+
  buttons in `main_window.py` can rescale everything from one place.
  Two things had to be true for "live" to actually work, both verified
  directly rather than assumed:
  - Re-applying `QApplication.setStyleSheet()` *does* retroactively
    restyle already-constructed widgets' inherited/cascaded font (confirmed
    by direct test) — which is what makes buttons, tab labels, combo
    boxes, and the Strong's concordance list (which paints with
    `option.font`, never an explicit size) grow for free.
  - It does **not** touch a widget's own explicit `setStyleSheet()`
    override (also confirmed directly) — so every card/label that sets
    its own `font-size` needs an explicit `refresh_fonts()` call,
    which `MainWindow._change_font_scale()` fires on every pane after
    updating the global stylesheet.
  - `build_app_stylesheet()` lives in `theme.py`, not `main.py` (where
    it was originally defined) — `main_window.py` needs to call it on
    every scale change, and `main.py` imports `MainWindow` from
    `main_window.py`, so leaving it in `main.py` would have been a
    circular import.
  - Each pane's `refresh_fonts()` re-renders its *current* content
    rather than re-querying, since re-querying isn't always safe to
    repeat: `DiscoveryPane` caches `_last_rows` specifically so a
    font-size change can't reshuffle the feed (its normal refresh path
    randomly re-samples), and `ReadingPane.refresh_fonts()` calls
    `_load_chapter()` with `true_top_verse()` as the target so the
    reload restores approximately the same scroll position instead of
    jumping to verse 1.
- The "← Back to reading" button anchors to the *first* jump in a
  chain, not the most recent one: clicking through several connections
  in a row still returns you to the chapter position you started from,
  not the last card you clicked. This is deliberate (`MainWindow._return_point`,
  guarded so it's only set when currently `None`) — the alternative
  ("back" meaning "previous card") was tried and rejected as confusing.
- Hovering a verse for its Scofield note vs. hovering a lettered
  footnote marker share one hover-resolution codepath in
  `reading_pane.py`'s `eventFilter()`: it checks `anchorAt()` for an
  `fn:`-prefixed anchor first (a footnote marker), and falls back to
  resolving whatever verse is under the cursor for a Scofield lookup.
  An earlier version gave Scofield notes their own inline marker
  (`§N`) with anchored text spans, matching the footnote design; it was
  simplified to whole-verse hovering because most Scofield notes are
  about the whole verse rather than one phrase, and the marker-width
  math for two different marker styles sharing one line was a source
  of off-by-one bugs. One known cosmetic edge case remains from the
  original footnote-anchoring approach: on rare verses (~0.2% of
  spans), a footnote marker can fall inside a Strong's word's
  highlighted span — not fixed, since eliminating it would need
  non-trivial re-flowing logic for a purely cosmetic overlap.
- **`anchor_utils.resolve_anchor()` needed two fix attempts, not one,
  for the same underlying class of bug**: a verse where the KJV
  translators attached the same marginal note to more than one
  occurrence of an idiom (Ezekiel 44:5 has "mark well" twice, both
  footnoted "Heb. set thine heart") had both notes resolving to the
  *first* occurrence, since `resolve_anchor()` originally always
  searched from the start of the text — reported directly as "AB" glued
  onto one spot showing only one note on hover. The first fix (a single
  forward-scanning cursor shared across all of a verse's notes) was
  itself wrong and caught before shipping: Esther 1:19 lists its
  "from him" note *after* "unto..." in document order despite "from
  him" occurring earlier in the actual verse text, so a shared
  monotonic cursor skipped past it and mis-anchored it to the wrong
  spot. The correct fix tracks occurrence count **per distinct
  catchword string** (`{catchword: count}`, scoped to one verse) rather
  than one cursor for the whole verse — a repeated phrase still
  resolves to successive occurrences, but unrelated catchwords never
  interfere with each other regardless of what order the source lists
  them in. Rebuilding both `footnotes` and `scofield_notes` with the
  fix improved resolution from 6936/2926 to 6949/2926 phrase-anchored
  notes respectively (the footnotes gain is real; Scofield had no
  matching bug in the same run, just applied for consistency since it
  shares the same helper). A handful of cases remain where two markers
  still land on the exact same spot — checked directly, and unlike the
  above, these are correct: either two genuinely separate KJV notes
  attached to one single word (e.g. an "or, ..." alternate reading plus
  a "Heb. ..." literal one on the same occurrence), or two catchword
  strings where one is a substring/suffix of the other, coincidentally
  sharing an end offset. The HTML already renders these as two distinct
  `<a>` tags (`_verse_body_html()`'s `markers_by_pos` already keyed on
  a list, not a single marker), so both are technically hoverable —
  it's a usability limitation (two tiny adjacent superscript letters
  with no visual gap) rather than a data or resolution bug, left as-is.
- Every card in the Connections/Search/Strong's/Discover panes shares
  one `ClickableCard` base (`desktop/cards.py`) with a copy-to-clipboard
  button rendered from inline SVG (`_svg_icon()`) rather than a Unicode
  glyph, since glyph coverage for something like U+2398 varies by font.
  The button's own click doesn't trigger the card's `mousePressEvent`
  (and thus navigate) — Qt delivers the press to whichever widget is
  actually under the cursor.
- **The one list that isn't built from `ClickableCard` widgets is the
  Strong's concordance view** (`word_detail_page.py`'s `_ConcordanceList`)
  — it can hold thousands of rows (the most frequent word in the whole
  KJV, G3588 "the," occurs ~6,400 times), and a `QVBoxLayout` of real
  widget children re-lays-out every child on every geometry change,
  getting *progressively* slower as more accumulate. Measured directly:
  building that list as cards took several seconds and kept growing
  (each additional batch of 150 cards got slower than the last), while
  a plain `QListWidget` with a custom `QStyledItemDelegate` — which only
  ever calls `paint()`/`sizeHint()` for rows actually on screen — loaded
  the same 6,369 rows in ~30ms. If any other list in this app ever needs
  to hold more than a couple hundred rows, use this pattern, not
  `ClickableCard`.

## The launcher (`Bible Connection.app`)

A real macOS `.app` bundle, not a script with a document icon — the
project used to ship `Run Bible Connections.command` (a plain shell
script Finder knows to open in Terminal), which worked but had no
icon, flashed a Terminal window on every launch, and doesn't mean
anything on Windows (`.command` is a macOS/Finder-specific convention;
double-clicking one there just prompts "what program should open this
file?"). The bundle is minimal, not a PyInstaller-style frozen build —
it's `Contents/Info.plist` + `Contents/Resources/AppIcon.icns` +
`Contents/MacOS/launch`, a shell script that still just runs
`python3 main.py` from the `desktop/` directory. Packages still need
to be pip-installed once per the README; this only replaces the
double-click-to-run step, not the setup step.

**The one non-obvious bug, caught only by testing via `open` (i.e. the
same path a real double-click takes) rather than running the script
directly:** a GUI-launched macOS app does not get PATH from the user's
shell profile the way a Terminal session does. Plain `python3` in that
context resolved to Apple's bare Command Line Tools Python — which has
none of the pip-installed packages — instead of the Homebrew (or
similar) install a Terminal session finds, even though the packages
really were installed correctly. The fix: route both the dependency
check and the actual launch through a *login* invocation of the user's
own shell (`"$SHELL" -l -c '...'`), which sources the same profile a
real Terminal window would and finds the right `python3` regardless of
whether Python was installed via Homebrew, python.org, or something
else. Hardcoding a path like `/opt/homebrew/bin/python3` would have
"worked" on the machine that built it and silently failed on anyone
else's (wrong path on Intel Macs, wrong entirely for a non-Homebrew
install).

The icon (source at `packaging/icon.svg`, rebuildable via
`packaging/build_icon.py`) was generated, not drawn by hand — the SVG
is rendered to every required size via `QSvgRenderer` (the same
technique `desktop/cards.py`'s `_svg_icon()` already uses), assembled
into a `.iconset` folder, then run through macOS's built-in
`iconutil -c icns`. Two lessons from actually testing it rather than
just building it:
- XML comments cannot contain a literal `--` anywhere in the comment
  body (only immediately before the closing `-->`) — an em-dash-style
  `--` inside a comment silently broke the whole SVG's rendering (Qt's
  `QSvgRenderer` fails silently rather than raising, producing a fully
  transparent image with no error).
- The first version used the app's *light-theme* background color
  (near-white parchment) for the icon itself. That's not a dark-mode
  bug — real OS-adaptive icons need Apple's `actool` asset-catalog
  compiler, which flatly refuses to run without the full Xcode.app
  installed ("requires Xcode" is its literal error under Command Line
  Tools alone, confirmed directly; there's no way around this short of
  installing Xcode). The actual problem was simpler: composited against
  a real dark Dock background, a light icon background just looks like
  a stray white square, independent of any dark-mode feature. Fixed by
  giving the icon its own bold, saturated background color (a dark
  maroon) instead of a near-white one — the normal way static (non-
  adaptive) Mac icons avoid looking out of place, and how the large
  majority of third-party Mac apps handle this, since few bother with
  real light/dark/tinted variants at all.

## The Windows launcher (`packaging/windows/`)

Everything in this section is built from correct, stable, decades-old
Windows APIs and reasoned through carefully, but — unlike the macOS
`.app` above, which was tested by actually launching it repeatedly via
`open` — **none of it has run on a real Windows machine**, because this
codebase's only development machine is a Mac with no Windows Script
Host available to test against. Where the macOS section says "confirmed
directly," this section can only say "should be correct, per the
documented API."

**What's genuinely verified, independent of any Windows machine:**
`BibleConnection.ico` is a hand-built multi-resolution icon (Qt can
only write single-frame `.ico` files, so this constructs the container
format directly: a 6-byte `ICONDIR` header, a 16-byte `ICONDIRENTRY`
per size, then each size's raw PNG bytes back to back — PNG-compressed
icon frames have been standard since Windows Vista). Checked two ways
that don't depend on Windows at all: `file` (libmagic, independent of
anything in this repo) correctly identifies it as "MS Windows icon
resource - 7 icons" with the right per-frame details, and Qt's own
`QImageReader` — a separate code path from the writer above — round-
trips and correctly decodes all 7 embedded sizes.

**What's reasoned-through but unverified:** the two `.vbs` files.
- `launch.vbs` is the actual executable behind the icon: it runs
  hidden (`shell.Run(cmd, 0, ...)` — the `0` is what suppresses the
  console window a `.bat` double-click would otherwise flash), checks
  for the required packages via `py -3` (the Python Launcher for
  Windows, installed system-wide by the official python.org installer
  specifically to avoid PATH ambiguity — more reliable than plain
  `python`/`python3`, which can resolve to a Microsoft Store redirect
  stub that does nothing useful if no real Python is installed), and
  shows a native `MsgBox` plus opens a real Command Prompt at the
  project folder if that check fails, mirroring what the macOS version
  does with `osascript`/`open -a Terminal`.
- A `.vbs` file can't carry a custom icon of its own in Windows
  Explorer (it always shows the default script icon) — only a
  *shortcut to one* can. Hence `Create Desktop Shortcut.vbs`: a
  separate, one-time setup script (run once, mirroring the one-time
  `pip install`) that uses `WScript.Shell.CreateShortcut()` to write a
  real `.lnk` file to the Desktop with `BibleConnection.ico` attached,
  pointing at `launch.vbs`. `.lnk` is a proprietary binary format that
  can't be hand-authored as text, which is why this needs its own
  script rather than just being a file included in the repo.
- Quoting throughout uses `Q = Chr(34)` and string concatenation rather
  than literal nested quote characters, specifically to avoid the kind
  of nested-quote counting mistake that actually broke the macOS
  `.command` file's AppleScript earlier in this same project (see the
  macOS section above) — safer to verify by eye than four consecutive
  quote characters.

If this is ever tested on real Windows and something doesn't work,
start with whichever assumption above is least certain: that `py`
exists and is on PATH (it might not be, depending on how Python was
installed), and that `WScript.Shell.Run`'s exit-code semantics for a
failed `cmd /c` invocation behave as documented.

## Web UI (secondary)

A small FastAPI app (`api/main.py`) exposes the same connection/search
logic over HTTP, with a static single-page frontend in `web/index.html`.
This exists mainly for quick experimentation outside Qt (e.g. checking
what an API client would see). Run it with:

```bash
uvicorn api.main:app --reload --app-dir /path/to/Bible_Connection
```

Endpoints: `GET /api/verse?ref=John+3:16`, `GET /api/search?q=...`,
`GET /api/stats`.

## GitHub Pages (for `extras/ezekiel-temple.html`)

Enabled via `gh api -X POST repos/.../pages -f "source[branch]=main" -f "source[path]=/"`,
serving the whole repo as static files at `https://mrchillstorm.github.io/Bible_Connection/`.
It exists for exactly one reason: GitHub's own file viewer doesn't
execute HTML — clicking a plain relative link to a `.html` file in a
rendered README just shows its source code, not a running page. The
README's Ezekiel's Temple picture links to the Pages URL specifically
so it opens as a live page instead. Nothing else in the repo currently
depends on Pages being enabled, and nothing else is designed to be
accessed through it — `web/index.html` (the secondary API frontend)
would technically be reachable there too, but it needs the FastAPI
backend running to do anything, so visiting it via Pages alone just
shows a non-functional page, not a broken one. `bible.db.zip` sits in
the served tree as well, but harmlessly — nothing links to it, and
Pages serving it as a static download wouldn't do any harm even if
something did.

## CLI (no server needed)

Everything the API does is also reachable directly through
`src/connections.py`'s functions from a `python3` REPL — `find_verse()`,
`get_connections()`, `search_text()` — useful for one-off queries
against the database without starting anything.

## Extending it

- **New connection types**: add rows to `edges` with a new `edge_type`
  value; `get_connections()`/`get_connections_for_verses()` already
  aggregate across whatever types are present, so the UI needs no
  changes to surface a new type — only a legend/color if you want it
  visually distinguished (see `theme.py`'s `curated`/`semantic` tokens).
- **New study-note sources**: `footnotes` and `scofield_notes` are
  identically shaped; a third note source can reuse the same table
  shape and `anchor_utils.resolve_anchor()` phrase-matching, or reuse
  the whole-verse-hover pattern if it doesn't need phrase anchoring.
- **A different translation**: everything downstream keys off
  `verses.text` and `verse_id()`; swapping in another OSIS-tagged
  source means rewriting `ingest_kjv.py`'s CSV parsing and re-running
  the whole pipeline. Red-letter spans, footnotes, and Strong's tagging
  all assume KJV-shaped OSIS markup and would need re-validation against
  a different source's tagging conventions.

## Scaling up

At ~31,000 verses, brute-force cosine similarity and a single SQLite
file are both well within comfortable range — the full embedding
matrix is a few hundred MB and every query here is single-user,
read-mostly. If this ever needed to serve many concurrent users or a
much larger corpus (e.g. multiple translations or extra-biblical texts),
the two things worth revisiting first would be a proper vector index
(pgvector or FAISS) in place of the batched brute-force scan, and
moving from SQLite to Postgres for concurrent write access — neither
is warranted at the current scale.
