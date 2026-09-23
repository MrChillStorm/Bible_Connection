"""Shared phrase-anchoring logic: locating a note's catchword/key-phrase
as a character span within a verse's plain text. Used by both the
translator's footnotes and the Scofield notes ingestion."""

# Single-character, length-preserving substitutions so that "goats'
# hair" (a plain-typed catchword) matches "goats' hair" (typeset with a
# curly apostrophe) in the verse text. Being 1-for-1 substitutions, an
# index found in the normalized text is still valid against the original.
_NORMALIZE = str.maketrans({
    "’": "'", "‘": "'",   # curly apostrophes/quotes -> straight
    "“": '"', "”": '"',
    "–": "-", "—": "-",   # en/em dash -> hyphen
})


def _normalize(s: str) -> str:
    return s.translate(_NORMALIZE)


def resolve_anchor(plain_text: str, catchword: str) -> int:
    """Char offset right after the catchword phrase in plain_text, or
    len(plain_text) (attach at verse end) if it can't be located."""
    cw = catchword.rstrip("… .").strip()
    if not cw:
        return len(plain_text)
    norm_text = _normalize(plain_text)
    norm_cw = _normalize(cw)
    idx = norm_text.find(norm_cw)
    if idx == -1:
        idx = norm_text.lower().find(norm_cw.lower())
    if idx == -1:
        return len(plain_text)
    return idx + len(cw)
