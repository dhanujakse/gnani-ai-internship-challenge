"""Tamil number words <-> integers, used for number accuracy.

Covers standard and common colloquial forms (ரெண்டு, நாலு, அஞ்சு ...), fused compounds
(இருபத்தைந்து = 25, தொண்ணூற்றொன்பது = 99, இரண்டாயிரம் = 2000) and spaced phrases
(இருபத்தி ஐந்து, ஆயிரத்து ஐநூறு, இரண்டு லட்சம் ஐம்பது ஆயிரம்).
Not handled: fractions (அரை, கால்), ordinals (ஐந்தாம்) and words with case suffixes (பத்துக்கு).
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from kuralcheck.text.normalize import normalize

PULLI = "்"  # ் (virama)
VOWEL_SIGNS = {
    "அ": "", "ஆ": "ா", "இ": "ி", "ஈ": "ீ", "உ": "ு", "ஊ": "ூ",
    "எ": "ெ", "ஏ": "ே", "ஐ": "ை", "ஒ": "ொ", "ஓ": "ோ", "ஔ": "ௌ",
}  # fmt: skip

UNITS: dict[int, list[str]] = {
    1: ["ஒன்று", "ஒண்ணு", "ஒன்னு"],
    2: ["இரண்டு", "ரெண்டு"],
    3: ["மூன்று", "மூணு"],
    4: ["நான்கு", "நாலு"],
    5: ["ஐந்து", "அஞ்சு", "அஞ்சி"],
    6: ["ஆறு"],
    7: ["ஏழு"],
    8: ["எட்டு"],
    9: ["ஒன்பது", "ஒம்போது", "ஒம்பது"],
}
TEENS: dict[int, list[str]] = {
    10: ["பத்து"],
    11: ["பதினொன்று", "பதினொண்ணு", "பதினொன்னு"],
    12: ["பன்னிரண்டு", "பன்னிரெண்டு", "பன்னெண்டு", "பனிரெண்டு", "பனிரண்டு"],
    13: ["பதிமூன்று", "பதின்மூன்று", "பதிமூணு"],
    14: ["பதினான்கு", "பதினாலு", "பதினாங்கு"],
    15: ["பதினைந்து", "பதினஞ்சு", "பதினஞ்சி"],
    16: ["பதினாறு"],
    17: ["பதினேழு"],
    18: ["பதினெட்டு"],
    19: ["பத்தொன்பது", "பத்தொம்பது"],
}
TENS: dict[int, list[str]] = {
    20: ["இருபது"],
    30: ["முப்பது"],
    40: ["நாற்பது", "நாப்பது"],
    50: ["ஐம்பது", "அம்பது"],
    60: ["அறுபது", "அறுவது"],
    70: ["எழுபது", "எழுவது"],
    80: ["எண்பது", "எம்பது"],
    90: ["தொண்ணூறு", "தொன்னூறு"],
}
HUNDREDS: dict[int, list[str]] = {
    100: ["நூறு"],
    200: ["இருநூறு"],
    300: ["முந்நூறு", "முன்னூறு"],
    400: ["நானூறு", "நாநூறு"],
    500: ["ஐநூறு", "ஐந்நூறு"],
    600: ["அறுநூறு"],
    700: ["எழுநூறு"],
    800: ["எண்ணூறு"],
    900: ["தொள்ளாயிரம்"],
}
MULTIPLIERS: dict[int, list[str]] = {
    1000: ["ஆயிரம்"],
    100_000: ["லட்சம்", "இலட்சம்"],
    10_000_000: ["கோடி"],
}

Kind = Literal["small", "mult", "abs"]


@dataclass(frozen=True)
class NumToken:
    value: int
    kind: Kind  # small: < 1000; mult: ஆயிரம்/லட்சம்/கோடி; abs: fused like இரண்டாயிரம்
    open: bool  # ends in a connector (இருபத்தி, நூற்று, ஆயிரத்து) and expects more


def _stem(word: str) -> str | None:
    """Combining stem ending in pulli: இருபது -> இருபத், நூறு -> நூற், ஆயிரம் -> ஆயிரத்."""
    if word.endswith("ு"):
        return word[:-1] + PULLI
    if word.endswith("ம" + PULLI):
        return word[:-2] + "த" + PULLI
    return None


def _connectors(stem: str) -> list[str]:
    """இருபத் -> இருபத்து, இருபத்தி (the consonant doubles before the connector vowel)."""
    consonant = stem[-2]
    return [stem + consonant + "ு", stem + consonant + "ி"]


def _doubled(stem: str) -> str:
    """இருபத் -> இருபத்த்: the consonant doubles when tens/hundreds fuse with what follows."""
    return stem + stem[-2] + PULLI


def _join(stem: str, word: str) -> str:
    """Vowel sandhi: இருபத் + ஐந்து -> இருபத்தைந்து. Consonant-initial words just concatenate."""
    if word and word[0] in VOWEL_SIGNS:
        return stem[:-1] + VOWEL_SIGNS[word[0]] + word[1:]
    return stem + word


@lru_cache(maxsize=1)
def lexicon() -> dict[str, NumToken]:
    lex: dict[str, NumToken] = {}

    def add(word: str, value: int, kind: Kind = "small", open_: bool = False) -> None:
        lex.setdefault(word, NumToken(value, kind, open_))

    below_100: dict[str, int] = {}
    for table in (UNITS, TEENS, TENS):
        for value, words in table.items():
            for w in words:
                below_100[w] = value

    # 21-99: tens + unit, fused or with connector.
    for tens_value, tens_words in TENS.items():
        for tw in tens_words:
            stem = _stem(tw)
            assert stem
            for conn in _connectors(stem):
                add(conn, tens_value, open_=True)
            for unit_value, unit_words in UNITS.items():
                for uw in unit_words:
                    below_100[_join(_doubled(stem), uw)] = tens_value + unit_value
                    for conn in _connectors(stem):
                        below_100[conn + uw] = tens_value + unit_value

    for w, v in below_100.items():
        add(w, v)

    # 100-999: hundreds alone, with connector, or fused with 1-99.
    for h_value, h_words in HUNDREDS.items():
        for hw in h_words:
            add(hw, h_value)
            stem = _stem(hw)
            assert stem
            for conn in _connectors(stem):
                add(conn, h_value, open_=True)
            for w, v in below_100.items():
                add(_join(_doubled(stem), w), h_value + v)
                for conn in _connectors(stem):
                    add(conn + w, h_value + v)

    # Multipliers, alone or with connector (ஆயிரத்து).
    for m_value, m_words in MULTIPLIERS.items():
        for mw in m_words:
            add(mw, m_value, "mult")
            stem = _stem(mw)
            if stem:
                for conn in _connectors(stem):
                    add(conn, m_value, "mult", open_=True)

    # Fused thousands: இரண்டாயிரம் (2000), பத்தாயிரம் (10000), plus irregular forms.
    for w, v in below_100.items():
        stem = _stem(w)
        if stem:
            add(_join(stem, "ஆயிரம்"), v * 1000, "abs")
            for conn in _connectors(_join(stem, "ஆயிரத்")):
                add(conn, v * 1000, "abs", open_=True)
    for w, v in {"மூவாயிரம்": 3000, "ஐயாயிரம்": 5000}.items():
        add(w, v, "abs")
        for conn in _connectors(w[:-2] + "த" + PULLI):
            add(conn, v, "abs", open_=True)

    return lex


def parse_number_word(word: str) -> int | None:
    """Value of a single token (digits or Tamil number word), else None."""
    w = normalize(word)
    if w.isdigit():
        return int(w)
    tok = lexicon().get(w)
    return tok.value if tok else None


def _continues(prev: NumToken, nxt: NumToken, last_mult: int, current: int) -> bool:
    if prev.open:
        return True
    if prev.kind == "small":  # "இரண்டு ஆயிரம்", not "பத்து முப்பது"
        return nxt.kind == "mult" and nxt.value > current
    # after ஆயிரம்/லட்சம் or a fused thousand: a smaller part may follow
    return nxt.value < last_mult  # "லட்சம் ஐம்பதாயிரம்", "ஆயிரம் ஐநூறு"


def extract_numbers(text: str) -> list[int]:
    """All numbers in a sentence, in order, from digits or Tamil number words."""
    lex = lexicon()
    out: list[int] = []
    total = current = last_mult = 0
    prev: NumToken | None = None

    def flush() -> None:
        nonlocal total, current, last_mult, prev
        if prev is not None:
            out.append(total + current)
        total = current = last_mult = 0
        prev = None

    for token in normalize(text).split():
        if token.isdigit():
            flush()
            out.append(int(token))
            continue
        tok = lex.get(token)
        if tok is None:
            flush()
            continue
        if prev is not None and not _continues(prev, tok, last_mult, current):
            flush()
        if tok.kind == "small":
            current += tok.value
        elif tok.kind == "mult":
            total += (current or 1) * tok.value
            current, last_mult = 0, tok.value
        else:  # abs
            total += current + tok.value
            current, last_mult = 0, 1000
        prev = tok
    flush()
    return out


def number_words(max_value: int = 99) -> dict[int, list[str]]:
    """All single-word spellings for values up to max_value (handy for building variants)."""
    out: dict[int, list[str]] = {}
    for w, tok in lexicon().items():
        if tok.kind == "small" and not tok.open and tok.value <= max_value:
            out.setdefault(tok.value, []).append(w)
    return dict(sorted(out.items()))


__all__ = ["NumToken", "extract_numbers", "lexicon", "number_words", "parse_number_word"]
