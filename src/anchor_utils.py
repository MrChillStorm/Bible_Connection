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


def _find_nth(haystack: str, needle: str, n: int) -> int:
    """Index of the (n+1)-th occurrence of needle in haystack (0-indexed
    n), or -1 if there aren't that many."""
    idx = -1
    search_from = 0
    for _ in range(n + 1):
        idx = haystack.find(needle, search_from)
        if idx == -1:
            return -1
        search_from = idx + 1
    return idx


def resolve_anchor(plain_text: str, catchword: str, occurrence: int = 0) -> int:
    """Char offset right after the catchword phrase in plain_text, or
    len(plain_text) (attach at verse end) if it can't be located.

    `occurrence` (0-indexed) picks which match to use when the phrase
    appears more than once. Callers resolving several notes for the
    same verse should track how many times each distinct catchword
    *string* has already been resolved and pass that count here --
    scoped per catchword, not a single cursor shared across every note
    in the verse, since two different catchwords in the same verse
    aren't guaranteed to be listed in left-to-right text order (seen
    directly in Esther 1:19: 'from him' is listed after 'unto...' in
    the notes despite occurring earlier in the verse). Per-catchword
    counting still correctly separates a phrase that legitimately
    repeats within one verse (the KJV translators sometimes attach the
    same marginal note to more than one occurrence of an idiom, e.g.
    Ezekiel 44:5's two "mark well") into its own successive matches,
    without that logic ever touching unrelated catchwords."""
    cw = catchword.rstrip("… .").strip()
    if not cw:
        return len(plain_text)
    norm_text = _normalize(plain_text)
    norm_cw = _normalize(cw)
    idx = _find_nth(norm_text, norm_cw, occurrence)
    if idx == -1:
        idx = _find_nth(norm_text.lower(), norm_cw.lower(), occurrence)
    if idx == -1:
        return len(plain_text)
    return idx + len(cw)
