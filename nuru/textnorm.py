"""Shared text normalisation for Kiswahili and English SMS input."""

from __future__ import annotations

import re
import unicodedata

_NON_WORD = re.compile(r"[^a-z0-9\s]")
_SPACES = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Lowercase, strip accents and punctuation, collapse whitespace.

    SMS users write in many ways ("Mjamzito!!", "MJAMZITO", "mjamzito.").
    Apostrophes are dropped so "ng'ombe" and "ngombe" match the same rules.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("'", "").replace("\u2019", "")
    text = _NON_WORD.sub(" ", text)
    return _SPACES.sub(" ", text).strip()
