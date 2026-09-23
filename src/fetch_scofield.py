"""Fetches the 66 Scofield Reference Bible Notes book pages (rendered
HTML, transclusion already resolved server-side) from Wikisource and
caches them locally."""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from books import BOOK_ORDER

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "scofield"

# Wikisource page slug -> our canonical book name
SLUG_TO_BOOK = {
    "Genesis": "Genesis", "Exodus": "Exodus", "Leviticus": "Leviticus",
    "Numbers": "Numbers", "Deuteronomy": "Deuteronomy", "Joshua": "Joshua",
    "Judges": "Judges", "Ruth": "Ruth",
    "1 Kings (1 Samuel)": "I Samuel", "2 Kings (2 Samuel)": "II Samuel",
    "3 Kings (1 Kings)": "I Kings", "4 Kings (2 Kings)": "II Kings",
    "1 Chronicles": "I Chronicles", "2 Chronicles": "II Chronicles",
    "Ezra": "Ezra", "Nehemiah": "Nehemiah", "Esther": "Esther", "Job": "Job",
    "Psalms": "Psalms", "Proverbs": "Proverbs", "Ecclesiastes": "Ecclesiastes",
    "Song of Solomon (Canticles)": "Song of Solomon", "Isaiah": "Isaiah",
    "Jeremiah": "Jeremiah", "Lamentations": "Lamentations", "Ezekiel": "Ezekiel",
    "Daniel": "Daniel", "Hosea": "Hosea", "Joel": "Joel", "Amos": "Amos",
    "Obadiah": "Obadiah", "Jonah": "Jonah", "Micah": "Micah", "Nahum": "Nahum",
    "Habakkuk": "Habakkuk", "Zephaniah": "Zephaniah", "Haggai": "Haggai",
    "Zechariah": "Zechariah", "Malachi": "Malachi", "Matthew": "Matthew",
    "Mark": "Mark", "Luke": "Luke", "John": "John", "Acts": "Acts",
    "Romans": "Romans", "1 Corinthians": "I Corinthians",
    "2 Corinthians": "II Corinthians", "Galatians": "Galatians",
    "Ephesians": "Ephesians", "Philippians": "Philippians",
    "Colossians": "Colossians", "1 Thessalonians": "I Thessalonians",
    "2 Thessalonians": "II Thessalonians", "1 Timothy": "I Timothy",
    "2 Timothy": "II Timothy", "Titus": "Titus", "Philemon": "Philemon",
    "Hebrews": "Hebrews", "James": "James", "1 Peter": "I Peter",
    "2 Peter": "II Peter", "1 John": "I John", "2 John": "II John",
    "3 John": "III John", "Jude": "Jude", "Revelation": "Revelation of John",
}

API = "https://en.wikisource.org/w/api.php"


USER_AGENT = "BibleConnectionsApp/1.0 (personal desktop Bible study project; contact: local-only)"


def fetch_page_html(slug: str) -> str:
    page = f"Scofield Reference Bible Notes/{slug}"
    params = {"action": "parse", "page": page, "format": "json", "prop": "text"}
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.load(resp)
            return data["parse"]["text"]["*"]
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 4:
                wait = 10 * (attempt + 1)
                print(f"    rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                raise


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    assert set(SLUG_TO_BOOK.values()) == set(BOOK_ORDER), "mapping doesn't cover all 66 books"
    assert len(SLUG_TO_BOOK) == 66

    for i, (slug, book) in enumerate(SLUG_TO_BOOK.items(), 1):
        out_path = OUT_DIR / f"{book}.html"
        if out_path.exists():
            print(f"[{i}/66] {book}: already cached, skipping")
            continue
        print(f"[{i}/66] {book}: fetching '{slug}'...")
        html = fetch_page_html(slug)
        out_path.write_text(html, encoding="utf-8")
        time.sleep(2)  # be polite to Wikisource's servers

    print("Done.")


if __name__ == "__main__":
    main()
