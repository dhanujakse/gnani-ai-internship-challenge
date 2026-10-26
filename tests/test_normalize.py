import unicodedata

from kuralcheck.text.normalize import normalize

ZWJ = "‍"
ZWNJ = "‌"


def test_identical_tamil_unchanged() -> None:
    s = "நான் நாளைக்கு கடைக்கு வருவேன்"
    assert normalize(s) == s


def test_strips_punctuation() -> None:
    assert normalize("வணக்கம், எப்படி இருக்கீங்க?") == "வணக்கம் எப்படி இருக்கீங்க"
    assert normalize("“சரி!” — போலாம்...") == "சரி போலாம்"


def test_strips_zero_width_chars() -> None:
    assert normalize(f"க்{ZWJ}ஷ") == "க்ஷ"
    assert normalize(f"கடை{ZWNJ}க்கு﻿") == "கடைக்கு"


def test_collapses_and_trims_spaces() -> None:
    assert normalize("  ஒரு   டீ \t\n வேணும் ") == "ஒரு டீ வேணும்"


def test_lowercases_latin_only() -> None:
    assert normalize("UPI Payment பண்ணுங்க") == "upi payment பண்ணுங்க"


def test_nfc_composes_tamil_vowel_signs() -> None:
    decomposed = "கொ"  # க + ெ + ா  (should become கொ)
    assert normalize(decomposed) == unicodedata.normalize("NFC", decomposed) == "கொ"


def test_keeps_digit_groups_together() -> None:
    assert normalize("₹1,500 கொடுங்க") == "1500 கொடுங்க"
    assert normalize("10:30 மணிக்கு") == "10 30 மணிக்கு"


def test_apostrophe_is_dropped_not_split() -> None:
    assert normalize("don't") == "dont"


def test_empty() -> None:
    assert normalize("") == ""
    assert normalize(" ?! ") == ""
