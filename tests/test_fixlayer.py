from pathlib import Path

import pytest

from kuralcheck.fixlayer.bias import load_bias_words
from kuralcheck.fixlayer.lexicon import Lexicon, Rule, load_lexicon


def lex(*rules: tuple[str, str]) -> Lexicon:
    return Lexicon([Rule(p, r, "test") for p, r in rules])


def test_replaces_whole_words_only() -> None:
    lx = lex(("அவங்க", "அவர்கள்"))
    assert lx.apply("அவங்க வந்தாங்க") == "அவர்கள் வந்தாங்க"
    # must not fire inside a longer Tamil word (vowel signs and pulli count as part of the word)
    assert lx.apply("அவங்களுக்கு சொல்லு") == "அவங்களுக்கு சொல்லு"
    assert lx.apply("இவங்க") == "இவங்க"


def test_tamil_vowel_sign_is_part_of_word() -> None:
    lx = lex(("போன", "போன்"))
    assert lx.apply("போனா வா") == "போனா வா"  # ா follows, so no match
    assert lx.apply("போன மாசம்") == "போன் மாசம்"


def test_longest_match_first() -> None:
    lx = lex(("கஸ்டமர்", "customer"), ("கஸ்டமர் கேர்", "customer care"))
    assert lx.apply("கஸ்டமர் கேர் நம்பர்") == "customer care நம்பர்"
    assert lx.apply("கஸ்டமர் வந்தாங்க") == "customer வந்தாங்க"


def test_single_pass_no_chaining() -> None:
    lx = lex(("a", "b"), ("b", "c"))
    assert lx.apply("a b") == "b c"  # "a" becomes "b" but is not turned into "c"


def test_latin_case_insensitive_and_punctuation_boundary() -> None:
    lx = lex(("phone", "போன்"))
    assert lx.apply("My Phone, please") == "My போன், please"


def test_empty_replacement_removes_word_cleanly() -> None:
    lx = lex(("அது வந்து", ""))
    assert lx.apply("அது வந்து நாளைக்கு வா") == "நாளைக்கு வா"


def test_hits_are_reported() -> None:
    lx = lex(("அவங்க", "அவர்கள்"))
    text, hits = lx.apply_with_hits("அவங்க அவங்க")
    assert text == "அவர்கள் அவர்கள்" and hits == ["அவங்க", "அவங்க"]


def test_empty_lexicon_is_identity() -> None:
    assert Lexicon([]).apply("அப்படியே") == "அப்படியே"


def test_load_lexicon_csv(tmp_path: Path) -> None:
    p = tmp_path / "variants.csv"
    p.write_text(
        "pattern,replacement,category\n# comment row,,\nரெண்டு,இரண்டு,numbers\nசார்ஜர்,charger,code_mixed\n",
        encoding="utf-8",
    )
    lx = load_lexicon(p)
    assert len(lx.rules) == 2
    assert lx.apply("ரெண்டு சார்ஜர்") == "இரண்டு charger"


def test_duplicate_pattern_rejected(tmp_path: Path) -> None:
    p = tmp_path / "v.csv"
    p.write_text("pattern,replacement,category\nஅ,ஆ,x\nஅ,இ,x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_lexicon(p)


def test_repo_lexicon_and_bias_files_load() -> None:
    load_lexicon()
    load_bias_words()


def test_bias_words_file(tmp_path: Path) -> None:
    p = tmp_path / "bias.txt"
    p.write_text("# dialect words\nஅவங்க\n\nவாங்க\nஅவங்க\n", encoding="utf-8")
    assert load_bias_words(p) == ("அவங்க", "வாங்க")


def test_bias_words_invalid_fails(tmp_path: Path) -> None:
    p = tmp_path / "bias.txt"
    p.write_text("இரண்டு வார்த்தை\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_bias_words(p)
