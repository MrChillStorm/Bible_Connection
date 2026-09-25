"""Setup on first launch, and again after an update: extracts the
pre-built content database from the zip shipped inside the package
into the per-user data folder (db.DB_PATH).

bible.db itself (~190MB) isn't committed to git directly -- GitHub
rejects any single git object over 100MB, and the usual workaround
(Git LFS) bills download bandwidth to the repo owner's account with
only 1GB/month free, which a handful of clones -- let alone a crawler
doing full clones -- would burn through immediately. Zipped, the same
database drops to ~82MB (KJV text and notes compress well), comfortably
under git's limit, so it ships as an ordinary tracked file: no LFS,
no external download, nothing that depends on the network at all.

SQLite needs true random-access seeks into the file for its B-tree
paging, which a compressed stream can't provide -- so the shipped zip
has to be extracted to a real bible.db on disk before the app can open
it. Measured at ~1.5s for the full database on ordinary hardware.

Each extraction records which zip it came from (the CRC and size the
zip already stores for its bible.db, so checking costs nothing) in
bible.db.source next to it. An update that ships a different zip gets
extracted again on the next launch; a database rebuilt in place by the
pipeline keeps its record, so it's never overwritten behind anyone's
back.
"""
import shutil
import zipfile
from pathlib import Path

from bible_connection.core.db import DB_PATH

ZIP_PATH = Path(__file__).resolve().parents[1] / "data" / "bible.db.zip"
SOURCE_PATH = DB_PATH.with_name("bible.db.source")


def _zip_id() -> str:
    with zipfile.ZipFile(ZIP_PATH) as zf:
        info = zf.getinfo("bible.db")
    return f"{info.CRC:08x} {info.file_size}"


def bible_db_ready() -> bool:
    """True when bible.db exists and came from the zip shipped now (or
    was built by hand, with no record of a zip at all)."""
    if not DB_PATH.exists():
        return False
    if not ZIP_PATH.exists() or not SOURCE_PATH.exists():
        return True
    return SOURCE_PATH.read_text().strip() == _zip_id()


def extract_bible_db() -> None:
    """Unzips the shipped bible.db.zip into place. Extracts to a
    temporary name first and renames into place atomically, so a
    crash or a full disk mid-extract can never leave a truncated
    bible.db that a later launch would mistake for the real thing."""
    if not ZIP_PATH.exists():
        raise FileNotFoundError(
            f"{ZIP_PATH} is missing -- the app needs this file to build "
            "its Bible database. Try reinstalling Bible Connection."
        )

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = DB_PATH.with_suffix(".db.tmp")
    with zipfile.ZipFile(ZIP_PATH) as zf, zf.open("bible.db") as src:
        with open(tmp_path, "wb") as dst:
            shutil.copyfileobj(src, dst)
    tmp_path.replace(DB_PATH)
    SOURCE_PATH.write_text(_zip_id() + "\n")


def pack_bible_db() -> None:
    """The other direction, for shipping a rebuilt database: zips
    bible.db into the package's bible.db.zip (maximum compression, as
    `zip -9` would) and records it as the source, so the next launch
    doesn't extract the same thing straight back."""
    tmp_path = ZIP_PATH.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.write(DB_PATH, "bible.db")
    tmp_path.replace(ZIP_PATH)
    SOURCE_PATH.write_text(_zip_id() + "\n")
