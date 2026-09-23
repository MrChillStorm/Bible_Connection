"""One-time setup: extracts the pre-built content database from the
zip shipped in the repo, the first time the app runs on a machine.

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
it. Measured at ~1.5s for the full database on ordinary hardware, and
only ever needed once per machine.
"""
import shutil
import zipfile

from db import DB_PATH

ZIP_PATH = DB_PATH.parent / "bible.db.zip"


def bible_db_ready() -> bool:
    return DB_PATH.exists()


def extract_bible_db() -> None:
    """Unzips the shipped bible.db.zip into place. Extracts to a
    temporary name first and renames into place atomically, so a
    crash or a full disk mid-extract can never leave a truncated
    bible.db that a later launch would mistake for the real thing."""
    if not ZIP_PATH.exists():
        raise FileNotFoundError(
            f"{ZIP_PATH} is missing -- the app needs this file to build "
            "its Bible database. Try re-downloading the project."
        )

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = DB_PATH.with_suffix(".db.tmp")
    with zipfile.ZipFile(ZIP_PATH) as zf, zf.open("bible.db") as src:
        with open(tmp_path, "wb") as dst:
            shutil.copyfileobj(src, dst)
    tmp_path.replace(DB_PATH)
