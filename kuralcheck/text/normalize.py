"""Text normalisation applied to references and hypotheses before scoring.

Steps (see the project notes "Definitions"): Unicode NFC, drop zero-width and other format
characters, strip punctuation and symbols, lowercase Latin letters, collapse spaces.
Thousands separators inside numbers ("1,500") are removed so the number stays whole.
"""

import re
import unicodedata

_DIGIT_COMMA = re.compile(r"(?<=\d),(?=\d)")
_APOSTROPHES = re.compile(r"['’ʼ]")
_SPACES = re.compile(r"\s+")


def _is_latin(ch: str) -> bool:
    return ch.isascii() or unicodedata.name(ch, "").startswith("LATIN")


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFC", text)
    # Zero-width joiner/non-joiner, BOM, soft hyphen etc. are all category Cf.
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Cf")
    t = _DIGIT_COMMA.sub("", t)
    t = _APOSTROPHES.sub("", t)  # "don't" -> "dont", not "don t"
    # Punctuation (P*) and symbols (S*, e.g. ₹ + %) become spaces. Tamil vowel signs are M*, kept.
    t = "".join(" " if unicodedata.category(ch)[0] in "PS" else ch for ch in t)
    t = "".join(ch.lower() if _is_latin(ch) else ch for ch in t)
    return _SPACES.sub(" ", t).strip()
