"""Keep replies GSM-7 friendly and within two SMS segments.

Segment maths (GSM-7):
  * a single SMS holds 160 characters;
  * a concatenated (multi-part) SMS holds 153 characters per segment because
    of the user data header. Two segments therefore hold 306 characters, not
    320. NURU defaults to 306 so a reply really is billed as 2 SMS.
  * characters from the GSM-7 extension table ({ } [ ] ~ ^ \\ | and the euro
    sign) cost 2 septets each.

Any non GSM-7 character forces UCS-2 encoding (70 / 67 characters per
segment), which more than doubles cost, so we transliterate common offenders
(smart quotes, long dashes, ellipsis, accented letters) and drop the rest.
"""

from __future__ import annotations

import re
import unicodedata

GSM7_BASIC = set(
    "@\u00a3$\u00a5\u00e8\u00e9\u00f9\u00ec\u00f2\u00c7\n\u00d8\u00f8\r\u00c5\u00e5"
    "\u0394_\u03a6\u0393\u039b\u03a9\u03a0\u03a8\u03a3\u0398\u039e\u00c6\u00e6\u00df\u00c9"
    " !\"#\u00a4%&'()*+,-./0123456789:;<=>?"
    "\u00a1ABCDEFGHIJKLMNOPQRSTUVWXYZ\u00c4\u00d6\u00d1\u00dc\u00a7"
    "\u00bfabcdefghijklmnopqrstuvwxyz\u00e4\u00f6\u00f1\u00fc\u00e0"
)
GSM7_EXTENDED = set("^{}\\[~]|\u20ac")

_TRANSLITERATE = {
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"',
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2015": "-",
    "\u2026": "...", "\u00a0": " ", "\u2022": "-", "\u00b7": "-",
    "\t": " ",
}

SINGLE_SEGMENT = 160
MULTI_SEGMENT = 153


def to_gsm7(text: str) -> str:
    """Transliterate or drop characters that are not in the GSM-7 alphabet."""
    out: list[str] = []
    for ch in text:
        if ch in GSM7_BASIC or ch in GSM7_EXTENDED:
            out.append(ch)
            continue
        if ch in _TRANSLITERATE:
            out.append(_TRANSLITERATE[ch])
            continue
        base = unicodedata.normalize("NFKD", ch)
        base = "".join(c for c in base if not unicodedata.combining(c))
        if base and all(c in GSM7_BASIC for c in base):
            out.append(base)
        # anything else (emoji, unsupported scripts) is dropped
    return re.sub(r"[ ]{2,}", " ", "".join(out)).strip()


def septet_length(text: str) -> int:
    return sum(2 if ch in GSM7_EXTENDED else 1 for ch in text)


def is_gsm7(text: str) -> bool:
    return all(ch in GSM7_BASIC or ch in GSM7_EXTENDED for ch in text)


def segment_count(text: str) -> int:
    """Number of SMS segments the text will be billed as (GSM-7 assumed)."""
    length = septet_length(text)
    if length <= SINGLE_SEGMENT:
        return 1
    return -(-length // MULTI_SEGMENT)


def fit_sms(text: str, max_chars: int = 2 * MULTI_SEGMENT) -> str:
    """Return GSM-7 text no longer than max_chars septets.

    Cuts at the last full sentence that fits, then at the last word, so a
    reply never ends mid-word.
    """
    text = to_gsm7(text)
    if septet_length(text) <= max_chars:
        return text

    # Reserve no ellipsis: an ellipsis on a health message reads as "there is
    # more you are missing". We prefer a clean, complete sentence.
    budget = text
    while septet_length(budget) > max_chars:
        budget = budget[:-1]

    sentence_end = max(budget.rfind(". "), budget.rfind("! "), budget.rfind("? "))
    if budget.endswith((".", "!", "?")):
        return budget.strip()
    if sentence_end >= max_chars // 3:
        return budget[: sentence_end + 1].strip()

    word_end = budget.rfind(" ")
    if word_end > 0:
        return budget[:word_end].rstrip(" ,;:-") + "."
    return budget
