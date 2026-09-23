"""Parses the OpenScriptures Strong's Hebrew and Greek dictionary XML
files into a unified {number: entry} dict.

Numbers are normalized to a canonical unpadded form (e.g. 'H430',
'G2424') since the dictionary and the OSIS verse-tagging source use
different, inconsistent zero-padding conventions.
"""
import re
from html import unescape


def normalize_strong(raw: str) -> str:
    raw = raw.strip()
    return raw[0].upper() + (raw[1:].lstrip("0") or "0")


def _strip_tags(s: str) -> str:
    text = unescape(re.sub(r"<[^>]+>", "", s)).strip()
    # cross-reference tags (<strongsref .../>) resolve to nothing useful
    # once stripped; clean up the empty parens/commas they leave behind
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\(\s*,", "(", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_greek(xml_text: str) -> dict[str, dict]:
    entries = {}
    for m in re.finditer(r'<entry strongs="(\d+)">(.*?)</entry>', xml_text, re.S):
        number = normalize_strong("G" + m.group(1))
        body = m.group(2)

        greek = re.search(r'<greek[^>]*unicode="([^"]*)"[^>]*translit="([^"]*)"', body)
        if not greek:
            greek = re.search(r'<greek[^>]*translit="([^"]*)"[^>]*unicode="([^"]*)"', body)
            original, translit = (greek.group(2), greek.group(1)) if greek else ("", "")
        else:
            original, translit = greek.group(1), greek.group(2)

        pron = re.search(r'<pronunciation strongs="([^"]*)"', body)
        deriv = re.search(r"<strongs_derivation>(.*?)</strongs_derivation>", body, re.S)
        defin = re.search(r"<strongs_def>(.*?)</strongs_def>", body, re.S)
        kjv = re.search(r"<kjv_def>(.*?)</kjv_def>", body, re.S)

        entries[number] = {
            "original_word": original,
            "transliteration": translit,
            "pronunciation": pron.group(1) if pron else "",
            "derivation": _strip_tags(deriv.group(1)) if deriv else "",
            "definition": _strip_tags(defin.group(1)) if defin else "",
            "kjv_translations": _strip_tags(kjv.group(1)).lstrip(":-").strip() if kjv else "",
        }
    return entries


def parse_hebrew(xml_text: str) -> dict[str, dict]:
    entries = {}
    for m in re.finditer(r'<div type="entry"[^>]*>(.*?)</div>', xml_text, re.S):
        body = m.group(1)
        w = re.search(r'<w\b[^>]*\bID="(H\d+)"[^>]*\blemma="([^"]*)"[^>]*\bxlit="([^"]*)"', body)
        if not w:
            w = re.search(r'<w\b[^>]*\blemma="([^"]*)"[^>]*\bxlit="([^"]*)"[^>]*\bID="(H\d+)"', body)
            if not w:
                continue
            lemma, xlit, id_ = w.group(1), w.group(2), w.group(3)
        else:
            id_, lemma, xlit = w.group(1), w.group(2), w.group(3)

        number = normalize_strong(id_)

        items = re.findall(r"<item>(.*?)</item>", body, re.S)
        explanation = re.search(r'<note type="explanation">(.*?)</note>', body, re.S)
        translation = re.search(r'<note type="translation">(.*?)</note>', body, re.S)
        exegesis = re.search(r'<note type="exegesis">(.*?)</note>', body, re.S)

        definition = "; ".join(_strip_tags(i) for i in items) if items else (
            _strip_tags(explanation.group(1)) if explanation else ""
        )

        entries[number] = {
            "original_word": lemma,
            "transliteration": xlit,
            "pronunciation": "",
            "derivation": _strip_tags(exegesis.group(1)) if exegesis else "",
            "definition": definition,
            "kjv_translations": _strip_tags(translation.group(1)) if translation else "",
        }
    return entries
