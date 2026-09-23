"""Downloads STEPBible's Translators Brief lexicons (TBESG for Greek,
TBESH for Hebrew) -- richer, Strong's-number-linked definitions (Abbott-
Smith/Middle Liddell for Greek, abridged BDB for Hebrew) than the base
OpenScriptures Strong's dictionary already ingested by
ingest_strongs_dictionary.py.

Not committed to the repo (see .gitignore): STEPBible's CC BY 4.0 terms
ask that this data be redistributed from their single GitHub source
rather than copied elsewhere, so this script re-downloads it instead of
shipping a local copy. https://github.com/STEPBible/STEPBible-Data
"""
import time
import urllib.request
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

_BASE = "https://raw.githubusercontent.com/STEPBible/STEPBible-Data/master/Lexicons/"
_FILES = {
    "tbesg.txt": _BASE + "TBESG%20-%20Translators%20Brief%20lexicon%20of%20Extended%20Strongs%20for%20Greek%20-%20STEPBible.org%20CC%20BY.txt",
    "tbesh.txt": _BASE + "TBESH%20-%20Translators%20Brief%20lexicon%20of%20Extended%20Strongs%20for%20Hebrew%20-%20STEPBible.org%20CC%20BY.txt",
}
_USER_AGENT = "Bible-Connections-personal-study-app (contact: local user)"


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for filename, url in _FILES.items():
        dest = RAW_DIR / filename
        print(f"Downloading {filename} ...")
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req) as resp:
            dest.write_bytes(resp.read())
        print(f"  saved to {dest} ({dest.stat().st_size:,} bytes)")
        time.sleep(1)


if __name__ == "__main__":
    main()
