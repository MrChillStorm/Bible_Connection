"""Canonical KJV book ordering and abbreviation mapping.

The verse id scheme used throughout this project is:
    id = book_order * 1_000_000 + chapter * 1000 + verse
book_order is 1-66 in canonical Protestant Bible order (matches the row
order in data/raw/kjv.csv). This keeps ids sortable in reading order and
lets range lookups (e.g. cross-reference ranges) use a simple BETWEEN
query on the verses table.
"""

BOOK_ORDER = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua",
    "Judges", "Ruth", "I Samuel", "II Samuel", "I Kings", "II Kings",
    "I Chronicles", "II Chronicles", "Ezra", "Nehemiah", "Esther", "Job",
    "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon", "Isaiah",
    "Jeremiah", "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel",
    "Amos", "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah",
    "Haggai", "Zechariah", "Malachi", "Matthew", "Mark", "Luke", "John",
    "Acts", "Romans", "I Corinthians", "II Corinthians", "Galatians",
    "Ephesians", "Philippians", "Colossians", "I Thessalonians",
    "II Thessalonians", "I Timothy", "II Timothy", "Titus", "Philemon",
    "Hebrews", "James", "I Peter", "II Peter", "I John", "II John",
    "III John", "Jude", "Revelation of John",
]

BOOK_TO_ORDER = {name: i + 1 for i, name in enumerate(BOOK_ORDER)}

# Maps the abbreviations used by openbible.info's cross-reference dataset
# to the canonical book names above.
ABBR_TO_BOOK = {
    "Gen": "Genesis", "Exod": "Exodus", "Lev": "Leviticus", "Num": "Numbers",
    "Deut": "Deuteronomy", "Josh": "Joshua", "Judg": "Judges", "Ruth": "Ruth",
    "1Sam": "I Samuel", "2Sam": "II Samuel", "1Kgs": "I Kings",
    "2Kgs": "II Kings", "1Chr": "I Chronicles", "2Chr": "II Chronicles",
    "Ezra": "Ezra", "Neh": "Nehemiah", "Esth": "Esther", "Job": "Job",
    "Ps": "Psalms", "Prov": "Proverbs", "Eccl": "Ecclesiastes",
    "Song": "Song of Solomon", "Isa": "Isaiah", "Jer": "Jeremiah",
    "Lam": "Lamentations", "Ezek": "Ezekiel", "Dan": "Daniel", "Hos": "Hosea",
    "Joel": "Joel", "Amos": "Amos", "Obad": "Obadiah", "Jonah": "Jonah",
    "Mic": "Micah", "Nah": "Nahum", "Hab": "Habakkuk", "Zeph": "Zephaniah",
    "Hag": "Haggai", "Zech": "Zechariah", "Mal": "Malachi",
    "Matt": "Matthew", "Mark": "Mark", "Luke": "Luke", "John": "John",
    "Acts": "Acts", "Rom": "Romans", "1Cor": "I Corinthians",
    "2Cor": "II Corinthians", "Gal": "Galatians", "Eph": "Ephesians",
    "Phil": "Philippians", "Col": "Colossians",
    "1Thess": "I Thessalonians", "2Thess": "II Thessalonians",
    "1Tim": "I Timothy", "2Tim": "II Timothy", "Titus": "Titus",
    "Phlm": "Philemon", "Heb": "Hebrews", "Jas": "James",
    "1Pet": "I Peter", "2Pet": "II Peter", "1John": "I John",
    "2John": "II John", "3John": "III John", "Jude": "Jude", "Rev": "Revelation of John",
}


def verse_id(book_order: int, chapter: int, verse: int) -> int:
    return book_order * 1_000_000 + chapter * 1000 + verse


# Traditional genre groupings, for the library/start page. Order within
# each group matches canonical Bible order.
OT_GROUPS = [
    ("Law", ["Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy"]),
    ("History", [
        "Joshua", "Judges", "Ruth", "I Samuel", "II Samuel", "I Kings", "II Kings",
        "I Chronicles", "II Chronicles", "Ezra", "Nehemiah", "Esther",
    ]),
    ("Wisdom & Poetry", ["Job", "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon"]),
    ("Major Prophets", ["Isaiah", "Jeremiah", "Lamentations", "Ezekiel", "Daniel"]),
    ("Minor Prophets", [
        "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah", "Nahum",
        "Habakkuk", "Zephaniah", "Haggai", "Zechariah", "Malachi",
    ]),
]

NT_GROUPS = [
    ("Gospels", ["Matthew", "Mark", "Luke", "John"]),
    ("History", ["Acts"]),
    ("Pauline Epistles", [
        "Romans", "I Corinthians", "II Corinthians", "Galatians", "Ephesians",
        "Philippians", "Colossians", "I Thessalonians", "II Thessalonians",
        "I Timothy", "II Timothy", "Titus", "Philemon",
    ]),
    ("General Epistles", [
        "Hebrews", "James", "I Peter", "II Peter", "I John", "II John", "III John", "Jude",
    ]),
    ("Apocalyptic", ["Revelation of John"]),
]
